import json
from pathlib import Path

from tsuzuri.config import RuntimeConfig
from tsuzuri.pipeline import MinimalPipeline
from tsuzuri.schemas import (
    CitedPoint,
    ExtractedDocument,
    FilteredUrl,
    MapSummary,
    ReportSynthesis,
    SearchResult,
)
from tsuzuri.storage import ArtifactStore
from tsuzuri.storage.nextcloud_webdav import WebdavUploadResult


class FakeSearchClient:
    async def search(self, query: str, *, max_results: int) -> list[SearchResult]:
        return [
            SearchResult.model_validate(
                {
                    "search_id": f"{query}-1",
                    "query": query,
                    "url": "https://example.com/news",
                    "normalized_url": "https://example.com/news",
                    "title": "Example AI regulation update",
                    "snippet": "A regulator announced an AI policy update.",
                    "rank": 1,
                }
            )
        ]


class FakeHtmlFetcher:
    async def fetch(self, item: FilteredUrl) -> ExtractedDocument:
        return ExtractedDocument.model_validate(
            {
                "doc_id": item.search_id,
                "url": item.url,
                "normalized_url": item.normalized_url,
                "document_type": "html",
                "title": item.title or "Example",
                "content": "This is extracted content from an AI regulation test article.",
                "estimated_tokens": 10,
                "domain": item.domain,
                "extraction_method": "httpx_trafilatura",
                "content_hash": "hash",
                "fetched_at": "2026-01-01T00:00:00Z",
                "source_query": item.query,
                "search_rank": item.rank,
                "retrieval_score": item.retrieval_score,
                "query_hits": item.query_hits,
                "engine_hits": item.engine_hits,
            }
        )


class FakeWebdavUploader:
    def __init__(self) -> None:
        self.remote_paths: list[str] = []

    async def upload_bytes(
        self, *, content: bytes, remote_path: str, content_type: str | None = None
    ) -> WebdavUploadResult:
        self.remote_paths.append(remote_path)
        return WebdavUploadResult(
            uploaded=False, skipped=False, warning="upload warning"
        )


class FakeMapSummarizer:
    async def summarize(self, document: ExtractedDocument) -> MapSummary:
        return MapSummary(
            doc_id=document.doc_id,
            title=document.title,
            document_type=document.document_type,
            language="en",
            relevance_score=4,
            is_news_like=True,
            is_search_noise=False,
            topic_tags=["AI regulation"],
            entities=["Example"],
            key_facts=["A regulator announced an AI policy update."],
            claims=[],
            uncertainties=[],
            conflicting_points=[],
            short_summary="A regulator announced an AI policy update.",
        )


class FakeReduceSummarizer:
    async def summarize(
        self, *, query: str, summaries: list[MapSummary]
    ) -> ReportSynthesis:
        assert query == "AI regulation"
        assert [summary.doc_id for summary in summaries] == ["Source-1"]
        return ReportSynthesis(
            headline="AI regulation brief",
            executive_summary=[
                CitedPoint(
                    text="A regulator announced an AI policy update.",
                    source_ids=["Source-1"],
                )
            ],
            key_developments=[
                CitedPoint(
                    text="The policy update is the main development.",
                    source_ids=["Source-1"],
                )
            ],
            uncertainties=[],
        )


def test_minimal_pipeline_saves_ranked_selected_and_synthesis_artifacts(
    tmp_path: Path,
) -> None:
    async def run_pipeline() -> None:
        uploader = FakeWebdavUploader()
        pipeline = MinimalPipeline(
            RuntimeConfig(
                searxng_base_url="https://search.example",
                output_dir=str(tmp_path),
                max_generated_queries=1,
                per_query_results=1,
            ),
            search_client=FakeSearchClient(),
            html_fetcher=FakeHtmlFetcher(),
            map_summarizer=FakeMapSummarizer(),
            reduce_summarizer=FakeReduceSummarizer(),
            artifact_store=ArtifactStore(tmp_path, run_id="run-1"),
            webdav_uploader=uploader,
        )

        result = await pipeline.run("AI regulation")

        assert result.run_id == "run-1"
        assert result.search_result_count == 1
        assert result.filtered_url_count == 1
        assert result.extracted_document_count == 1
        assert result.failed_fetch_count == 0
        assert result.map_summary_count == 1
        assert result.final_report_path == tmp_path / "run-1" / "final_report.md"
        assert result.warnings == ["upload warning"] * 13
        assert "run-1/summary.json" in uploader.remote_paths
        assert "run-1/warnings.json" in uploader.remote_paths
        assert "run-1/final_report.md" in uploader.remote_paths

    import asyncio

    asyncio.run(run_pipeline())

    summary = json.loads((tmp_path / "run-1" / "summary.json").read_text())
    assert summary["query"] == "AI regulation"
    assert summary["map_summary_count"] == 1
    assert summary["final_report"] == "final_report.md"
    assert summary["warnings"] == ["upload warning"] * 13
    assert (tmp_path / "run-1" / "ranked_search_results.json").exists()
    assert (tmp_path / "run-1" / "selected_documents.json").exists()
    assert (tmp_path / "run-1" / "report_synthesis.json").exists()

    final_report = (tmp_path / "run-1" / "final_report.md").read_text()
    assert "# AI regulation brief" in final_report
    assert "[Source-1]" in final_report
    assert (tmp_path / "run-1" / "warnings.json").exists()
