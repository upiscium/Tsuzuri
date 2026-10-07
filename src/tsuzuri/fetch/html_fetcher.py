"""HTML fetcher using httpx and trafilatura extraction."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
import hashlib

import httpx
import trafilatura

from tsuzuri.fetch.validators import FetchValidationError, validate_extracted_text
from tsuzuri.schemas import ExtractedDocument, FailedFetch, FilteredUrl

Extractor = Callable[[str], str | None]
FallbackFetcher = Callable[[FilteredUrl], Awaitable[str | None]]


class HtmlFetcher:
    """Fetch and extract HTML documents with diagnostics."""

    def __init__(
        self,
        *,
        timeout_sec: float,
        min_chars: int,
        allowed_languages: set[str],
        user_agent: str,
        client: httpx.AsyncClient | None = None,
        extractor: Extractor | None = None,
        fallback_fetcher: FallbackFetcher | None = None,
    ) -> None:
        self._timeout = httpx.Timeout(timeout_sec)
        self._min_chars = min_chars
        self._allowed_languages = allowed_languages
        self._user_agent = user_agent
        self._client = client
        self._extractor = extractor or _extract_with_trafilatura
        self._fallback_fetcher = fallback_fetcher

    async def fetch(self, item: FilteredUrl) -> ExtractedDocument | FailedFetch:
        """Fetch one URL and return either an extracted document or diagnostics."""
        response: httpx.Response | None = None
        extracted: str | None = None
        try:
            response = await self._download(item)
            content_type = _content_type(response)
            if content_type == "application/pdf":
                return self._failure(
                    item,
                    "unexpected_pdf_content_type",
                    content_type,
                    response=response,
                )
            if content_type and not _is_textual_content_type(content_type):
                return self._failure(
                    item,
                    "unsupported_content_type",
                    content_type,
                    response=response,
                )

            html = response.text
            try:
                extracted = self._extractor(html)
            except Exception as error:
                return self._failure(
                    item,
                    "html_extraction_failed",
                    str(error),
                    response=response,
                    raw_chars=len(html),
                )

            content = validate_extracted_text(
                extracted,
                min_chars=self._min_chars,
                allowed_languages=self._allowed_languages,
            )
            return self._document(
                item,
                content,
                response=response,
                raw_chars=len(html),
                extraction_method="httpx_trafilatura",
            )
        except FetchValidationError as error:
            if self._fallback_fetcher is None:
                return self._failure(
                    item,
                    error.reason,
                    error.detail,
                    response=response,
                    raw_chars=_response_text_length(response),
                    extracted_chars=len(extracted or ""),
                )
            return await self._fetch_with_fallback(
                item,
                error,
                response=response,
                raw_chars=_response_text_length(response),
            )
        except httpx.HTTPStatusError as error:
            return self._failure(
                item,
                "http_status_error",
                str(error.response.status_code),
                response=error.response,
            )
        except httpx.HTTPError as error:
            return self._failure(item, "html_download_failed", str(error))

    async def _download(self, item: FilteredUrl) -> httpx.Response:
        if self._client is not None:
            response = await self._client.get(
                str(item.url),
                headers={"User-Agent": self._user_agent},
                follow_redirects=True,
            )
        else:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    str(item.url),
                    headers={"User-Agent": self._user_agent},
                    follow_redirects=True,
                )
        response.raise_for_status()
        return response

    async def _fetch_with_fallback(
        self,
        item: FilteredUrl,
        original_error: FetchValidationError,
        *,
        response: httpx.Response | None,
        raw_chars: int | None,
    ) -> ExtractedDocument | FailedFetch:
        if self._fallback_fetcher is None:
            return self._failure(
                item,
                original_error.reason,
                original_error.detail,
                response=response,
                raw_chars=raw_chars,
            )
        try:
            fallback_text = await self._fallback_fetcher(item)
            content = validate_extracted_text(
                fallback_text,
                min_chars=self._min_chars,
                allowed_languages=self._allowed_languages,
            )
            return self._document(
                item,
                content,
                response=response,
                raw_chars=raw_chars,
                extraction_method="playwright_trafilatura",
            )
        except FetchValidationError as error:
            return self._failure(
                item,
                error.reason,
                error.detail,
                response=response,
                raw_chars=raw_chars,
                extracted_chars=len(fallback_text or ""),
            )
        except Exception as error:
            return self._failure(
                item,
                "playwright_failed",
                str(error),
                response=response,
                raw_chars=raw_chars,
            )

    def _document(
        self,
        item: FilteredUrl,
        content: str,
        *,
        response: httpx.Response | None,
        raw_chars: int | None,
        extraction_method: str,
    ) -> ExtractedDocument:
        return ExtractedDocument.model_validate(
            {
                "doc_id": _doc_id_for_item(item),
                "url": item.url,
                "final_url": _final_url(response),
                "normalized_url": item.normalized_url,
                "document_type": "html",
                "title": item.title or item.domain,
                "content": content,
                "estimated_tokens": max(1, len(content.split())),
                "domain": item.domain,
                "extraction_method": extraction_method,
                "status_code": response.status_code if response is not None else None,
                "content_type": _content_type(response),
                "response_bytes": len(response.content)
                if response is not None
                else None,
                "raw_chars": raw_chars,
                "content_hash": hashlib.sha256(content.encode("utf-8")).hexdigest(),
                "fetched_at": datetime.now(UTC),
                "source_query": item.query,
                "search_rank": item.rank,
                "published_hint": item.published_hint,
                "retrieval_score": item.retrieval_score,
                "query_hits": item.query_hits,
                "engine_hits": item.engine_hits,
            }
        )

    def _failure(
        self,
        item: FilteredUrl,
        reason: str,
        detail: str | None = None,
        *,
        response: httpx.Response | None = None,
        raw_chars: int | None = None,
        extracted_chars: int | None = None,
    ) -> FailedFetch:
        return FailedFetch.model_validate(
            {
                "url": item.url,
                "final_url": _final_url(response),
                "normalized_url": item.normalized_url,
                "document_type": item.document_type,
                "domain": item.domain,
                "source_query": item.query,
                "search_rank": item.rank,
                "reason": reason,
                "detail": detail,
                "status_code": response.status_code if response is not None else None,
                "content_type": _content_type(response),
                "response_bytes": len(response.content)
                if response is not None
                else None,
                "raw_chars": raw_chars,
                "extracted_chars": extracted_chars,
                "failed_at": datetime.now(UTC),
            }
        )


def _extract_with_trafilatura(html: str) -> str | None:
    return trafilatura.extract(html, include_comments=False, include_tables=False)


def _doc_id_for_item(item: FilteredUrl) -> str:
    if item.search_id.startswith("Source-"):
        return item.search_id
    return f"Source-{item.rank}"


def _content_type(response: httpx.Response | None) -> str | None:
    if response is None:
        return None
    value = response.headers.get("content-type")
    if not value:
        return None
    return value.split(";", maxsplit=1)[0].strip().lower()


def _is_textual_content_type(content_type: str) -> bool:
    return content_type.startswith("text/") or content_type in {
        "application/xhtml+xml",
        "application/xml",
    }


def _final_url(response: httpx.Response | None) -> str | None:
    if response is None:
        return None
    value = str(response.url)
    return value or None


def _response_text_length(response: httpx.Response | None) -> int | None:
    if response is None:
        return None
    try:
        return len(response.text)
    except Exception:
        return None
