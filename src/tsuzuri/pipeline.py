"""Runnable research pipeline."""

import asyncio
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

from tsuzuri.config import RuntimeConfig
from tsuzuri.fetch import HtmlFetcher, PdfFetcher
from tsuzuri.filtering import (
    filter_search_results,
    rank_search_results,
    select_documents,
)
from tsuzuri.llm import MapSummarizer, OpenAICompatibleClient, ReduceSummarizer
from tsuzuri.report import render_news_brief, render_synthesized_report
from tsuzuri.schemas import (
    ExtractedDocument,
    FailedFetch,
    FilteredUrl,
    FinalReport,
    MapSummary,
    ReportSynthesis,
    SearchResult,
)
from tsuzuri.search import SearxngClient, build_queries
from tsuzuri.storage import ArtifactStore, WebdavUploader

ProgressCallback = Callable[["PipelineProgress"], Awaitable[None]]


@dataclass(frozen=True)
class PipelineProgress:
    """Coarse-grained progress emitted while a run is executing."""

    step: str
    progress: int
    search_result_count: int = 0
    filtered_url_count: int = 0
    extracted_document_count: int = 0
    failed_fetch_count: int = 0
    map_summary_count: int = 0
    warnings: list[str] | None = None


@dataclass(frozen=True)
class PipelineRunResult:
    """Summary returned by the pipeline."""

    run_id: str
    run_dir: Path
    search_result_count: int
    filtered_url_count: int
    extracted_document_count: int
    failed_fetch_count: int
    map_summary_count: int
    final_report_path: Path | None
    warnings: list[str]


class MinimalPipeline:
    """Search, rank, fetch, summarize, synthesize, and persist research artifacts."""

    def __init__(
        self,
        config: RuntimeConfig,
        *,
        search_client: SearxngClient | None = None,
        html_fetcher: HtmlFetcher | None = None,
        pdf_fetcher: PdfFetcher | None = None,
        map_summarizer: MapSummarizer | None = None,
        reduce_summarizer: ReduceSummarizer | None = None,
        artifact_store: ArtifactStore | None = None,
        webdav_uploader: WebdavUploader | None = None,
    ) -> None:
        self._config = config
        self._search_client = search_client or SearxngClient(
            base_url=config.searxng_base_url,
            language=config.search_language,
            categories=config.search_categories,
            timeout_sec=config.query_timeout_s,
            retry_count=config.search_retry_count,
        )
        self._html_fetcher = html_fetcher or HtmlFetcher(
            timeout_sec=config.fetch_timeout_s,
            min_chars=config.min_success_chars,
            allowed_languages=set(config.allowed_languages),
            user_agent=config.user_agent,
        )
        self._pdf_fetcher = pdf_fetcher or PdfFetcher(
            timeout_sec=config.fetch_timeout_s,
            max_file_mb=config.pdf_max_file_mb,
            max_pages=config.pdf_max_pages,
            min_chars=config.min_success_chars,
            user_agent=config.user_agent,
        )

        llm_client = OpenAICompatibleClient(
            base_url=config.llm_base_url,
            model=config.llm_model,
            api_key=config.llm_api_key,
            timeout_sec=config.llm_timeout_s,
            temperature=config.llm_temperature,
            max_tokens=config.llm_max_tokens,
            reasoning_effort=config.llm_reasoning_effort,
            retry_count=config.llm_retry_count,
            structured_output=config.llm_structured_output,
        )
        self._map_summarizer = map_summarizer or MapSummarizer(llm_client)
        self._reduce_summarizer = reduce_summarizer or ReduceSummarizer(llm_client)
        self._artifact_store = artifact_store or ArtifactStore(config.output_dir)
        self._webdav_uploader = webdav_uploader or WebdavUploader(
            webdav_url=config.webdav_base_url,
            username=config.nextcloud_username,
            password=config.nextcloud_password,
            timeout_sec=config.upload_timeout_s,
        )

    async def run(
        self, query: str, progress_callback: ProgressCallback | None = None
    ) -> PipelineRunResult:
        """Run the research pipeline."""
        warnings: list[str] = []
        await _emit_progress(progress_callback, PipelineProgress("Preparing", 5))

        queries = build_queries(
            query, max_generated_queries=self._config.max_generated_queries
        )
        await _emit_progress(progress_callback, PipelineProgress("Searching", 15))
        search_results = await self._search_all(queries, warnings)

        ranked_results = rank_search_results(search_results, query=query)
        await _emit_progress(
            progress_callback,
            PipelineProgress(
                "Ranking and filtering",
                30,
                search_result_count=len(search_results),
                warnings=warnings,
            ),
        )
        filtered_urls = filter_search_results(
            ranked_results,
            blocked_domains=set(self._config.blocklisted_domains),
            blocked_extensions=set(self._config.blocklisted_extensions),
            max_urls_per_domain=self._config.max_urls_per_domain,
        )[: self._config.max_fetch_documents]
        filtered_urls = _assign_source_ids(filtered_urls)

        await _emit_progress(
            progress_callback,
            PipelineProgress(
                "Fetching documents",
                45,
                search_result_count=len(search_results),
                filtered_url_count=len(filtered_urls),
                warnings=warnings,
            ),
        )
        documents, failures = await self._fetch_documents(filtered_urls)
        selected_documents = select_documents(
            documents,
            query=query,
            max_documents=self._config.max_map_documents,
            max_per_domain=self._config.max_map_documents_per_domain,
        )

        await _emit_progress(
            progress_callback,
            PipelineProgress(
                "Summarizing documents",
                65,
                search_result_count=len(search_results),
                filtered_url_count=len(filtered_urls),
                extracted_document_count=len(documents),
                failed_fetch_count=len(failures),
                warnings=warnings,
            ),
        )
        map_summaries = await self._summarize_documents(selected_documents, warnings)
        useful_summaries = [
            summary
            for summary in map_summaries
            if not summary.is_search_noise
            and summary.relevance_score >= self._config.min_relevance_score
        ]

        await _emit_progress(
            progress_callback,
            PipelineProgress(
                "Synthesizing report",
                80,
                search_result_count=len(search_results),
                filtered_url_count=len(filtered_urls),
                extracted_document_count=len(documents),
                failed_fetch_count=len(failures),
                map_summary_count=len(map_summaries),
                warnings=warnings,
            ),
        )
        synthesis = await self._synthesize(query, useful_summaries, warnings)
        if synthesis is None:
            final_report = render_news_brief(
                query=query,
                summaries=map_summaries,
                documents=documents,
                min_relevance_score=self._config.min_relevance_score,
            )
        else:
            final_report = render_synthesized_report(
                query=query,
                synthesis=synthesis,
                documents=documents,
            )
        warnings.extend(final_report.warnings)

        artifact_paths = [
            self._artifact_store.save_json("queries.json", queries),
            self._artifact_store.save_json("search_results.json", search_results),
            self._artifact_store.save_json(
                "ranked_search_results.json", ranked_results
            ),
            self._artifact_store.save_json("filtered_urls.json", filtered_urls),
            self._artifact_store.save_json("extracted_documents.json", documents),
            self._artifact_store.save_json("failed_fetches.json", failures),
            self._artifact_store.save_json(
                "selected_documents.json", selected_documents
            ),
            self._artifact_store.save_json("map_summaries.json", map_summaries),
        ]
        if synthesis is not None:
            artifact_paths.append(
                self._artifact_store.save_json("report_synthesis.json", synthesis)
            )
        artifact_paths.extend(
            [
                self._artifact_store.save_json("final_report.json", final_report),
                self._artifact_store.save_text(
                    "final_report.md", final_report.markdown
                ),
            ]
        )

        await _emit_progress(
            progress_callback,
            PipelineProgress(
                "Uploading artifacts",
                92,
                search_result_count=len(search_results),
                filtered_url_count=len(filtered_urls),
                extracted_document_count=len(documents),
                failed_fetch_count=len(failures),
                map_summary_count=len(map_summaries),
                warnings=warnings,
            ),
        )
        warnings.extend(await self._upload_artifacts(artifact_paths))

        summary_path = self._save_summary(
            query=query,
            search_result_count=len(search_results),
            filtered_url_count=len(filtered_urls),
            extracted_document_count=len(documents),
            failed_fetch_count=len(failures),
            map_summary_count=len(map_summaries),
            final_report=final_report,
            warnings=warnings,
        )
        if warnings:
            warnings_path = self._artifact_store.save_json("warnings.json", warnings)
            warnings.extend(await self._upload_artifacts([summary_path, warnings_path]))
            self._save_summary(
                query=query,
                search_result_count=len(search_results),
                filtered_url_count=len(filtered_urls),
                extracted_document_count=len(documents),
                failed_fetch_count=len(failures),
                map_summary_count=len(map_summaries),
                final_report=final_report,
                warnings=warnings,
            )
            self._artifact_store.save_json("warnings.json", warnings)
        else:
            await self._upload_artifacts([summary_path])

        return PipelineRunResult(
            run_id=self._artifact_store.run_id,
            run_dir=self._artifact_store.run_dir,
            search_result_count=len(search_results),
            filtered_url_count=len(filtered_urls),
            extracted_document_count=len(documents),
            failed_fetch_count=len(failures),
            map_summary_count=len(map_summaries),
            final_report_path=self._artifact_store.run_dir / "final_report.md",
            warnings=warnings,
        )

    async def _search_all(
        self, queries: Iterable[str], warnings: list[str]
    ) -> list[SearchResult]:
        results: list[SearchResult] = []
        for query in queries:
            try:
                outcome = await self._search_client.search(
                    query, max_results=self._config.per_query_results
                )
            except Exception as error:
                warnings.append(f"Search failed for {query!r}: {error}")
                continue
            results.extend(outcome)
        return results

    async def _fetch_documents(
        self, filtered_urls: Iterable[FilteredUrl]
    ) -> tuple[list[ExtractedDocument], list[FailedFetch]]:
        semaphore = asyncio.Semaphore(max(1, self._config.max_concurrent_fetches))

        async def fetch_one(
            item: FilteredUrl,
        ) -> ExtractedDocument | FailedFetch:
            async with semaphore:
                if item.document_type == "pdf":
                    return await self._pdf_fetcher.fetch(item)

                result = await self._html_fetcher.fetch(item)
                if (
                    isinstance(result, FailedFetch)
                    and result.reason == "unexpected_pdf_content_type"
                ):
                    pdf_item = item.model_copy(update={"document_type": "pdf"})
                    return await self._pdf_fetcher.fetch(pdf_item)
                return result

        outcomes = await asyncio.gather(
            *[fetch_one(item) for item in filtered_urls],
            return_exceptions=True,
        )

        documents: list[ExtractedDocument] = []
        failures: list[FailedFetch] = []
        for item, outcome in zip(filtered_urls, outcomes, strict=True):
            if isinstance(outcome, BaseException):
                failures.append(
                    FailedFetch(
                        url=item.url,
                        normalized_url=item.normalized_url,
                        document_type=item.document_type,
                        domain=item.domain,
                        source_query=item.query,
                        search_rank=item.rank,
                        reason="fetch_unhandled_error",
                        detail=str(outcome),
                        failed_at=_utcnow(),
                    )
                )
            elif isinstance(outcome, ExtractedDocument):
                documents.append(outcome)
            else:
                failures.append(outcome)
        return documents, failures

    async def _summarize_documents(
        self, documents: Iterable[ExtractedDocument], warnings: list[str]
    ) -> list[MapSummary]:
        summaries: list[MapSummary] = []
        for document in documents:
            try:
                summary = await self._map_summarizer.summarize(document)
            except Exception as error:
                warnings.append(
                    f"Map summarization failed for {document.doc_id}: {error}"
                )
                continue
            if summary.doc_id != document.doc_id:
                warnings.append(
                    f"Map summarization returned mismatched doc_id for "
                    f"{document.doc_id}: {summary.doc_id}"
                )
                continue
            summaries.append(summary)
        return summaries

    async def _synthesize(
        self,
        query: str,
        summaries: list[MapSummary],
        warnings: list[str],
    ) -> ReportSynthesis | None:
        if not summaries:
            return None
        try:
            return await self._reduce_summarizer.summarize(
                query=query,
                summaries=summaries,
            )
        except Exception as error:
            warnings.append(f"Global reduce failed; using fallback report: {error}")
            return None

    async def _upload_artifacts(self, artifact_paths: Iterable[Path]) -> list[str]:
        warnings: list[str] = []
        for path in artifact_paths:
            remote_path = f"{self._artifact_store.run_id}/{path.name}"
            result = await self._webdav_uploader.upload_bytes(
                content=path.read_bytes(),
                remote_path=remote_path,
                content_type=_content_type_for_path(path),
            )
            if result.warning is not None:
                warnings.append(result.warning)
        return warnings

    def _save_summary(
        self,
        *,
        query: str,
        search_result_count: int,
        filtered_url_count: int,
        extracted_document_count: int,
        failed_fetch_count: int,
        map_summary_count: int,
        final_report: FinalReport,
        warnings: list[str],
    ) -> Path:
        return self._artifact_store.save_json(
            "summary.json",
            {
                "run_id": self._artifact_store.run_id,
                "query": query,
                "search_result_count": search_result_count,
                "filtered_url_count": filtered_url_count,
                "extracted_document_count": extracted_document_count,
                "failed_fetch_count": failed_fetch_count,
                "map_summary_count": map_summary_count,
                "final_report": "final_report.md",
                "final_report_source_count": final_report.source_count,
                "warnings": warnings,
            },
        )


def _content_type_for_path(path: Path) -> str:
    if path.suffix == ".md":
        return "text/markdown"
    return "application/json"


def _assign_source_ids(filtered_urls: list[FilteredUrl]) -> list[FilteredUrl]:
    return [
        item.model_copy(update={"search_id": f"Source-{index}"})
        for index, item in enumerate(filtered_urls, start=1)
    ]


async def _emit_progress(
    progress_callback: ProgressCallback | None, progress: PipelineProgress
) -> None:
    if progress_callback is None:
        return
    await progress_callback(progress)


def _utcnow():
    from datetime import UTC, datetime

    return datetime.now(UTC)
