import asyncio

import httpx

from tsuzuri.fetch.html_fetcher import HtmlFetcher
from tsuzuri.schemas import ExtractedDocument, FailedFetch, FilteredUrl


def _item() -> FilteredUrl:
    return FilteredUrl.model_validate(
        {
            "search_id": "search-1",
            "query": "AI regulation",
            "url": "https://example.com/news",
            "normalized_url": "https://example.com/news",
            "title": "Example Article",
            "domain": "example.com",
            "rank": 7,
            "document_type": "html",
        }
    )


def test_html_fetcher_returns_extracted_document() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == "Tsuzuri/0.1"
        return httpx.Response(200, text="<html>ok</html>", request=request)

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            fetcher = HtmlFetcher(
                timeout_sec=10,
                min_chars=20,
                allowed_languages={"en", "ja"},
                user_agent="Tsuzuri/0.1",
                client=client,
                extractor=lambda html: "This is a useful extracted article body.",
            )
            result = await fetcher.fetch(_item())

        assert isinstance(result, ExtractedDocument)
        assert result.doc_id == "Source-7"
        assert result.extraction_method == "httpx_trafilatura"
        assert result.content == "This is a useful extracted article body."

    asyncio.run(run())


def test_html_fetcher_uses_assigned_source_id() -> None:
    assigned_item = _item().model_copy(update={"search_id": "Source-42"})

    async def run() -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, text="<html>ok</html>", request=request)
        )
        async with httpx.AsyncClient(transport=transport) as client:
            fetcher = HtmlFetcher(
                timeout_sec=10,
                min_chars=20,
                allowed_languages={"en"},
                user_agent="Tsuzuri/0.1",
                client=client,
                extractor=lambda html: "This is a useful extracted article body.",
            )
            result = await fetcher.fetch(assigned_item)

        assert isinstance(result, ExtractedDocument)
        assert result.doc_id == "Source-42"

    asyncio.run(run())


def test_html_fetcher_returns_failed_fetch_for_http_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(403, request=request)

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as client:
            fetcher = HtmlFetcher(
                timeout_sec=10,
                min_chars=20,
                allowed_languages={"en"},
                user_agent="Tsuzuri/0.1",
                client=client,
                extractor=lambda html: "unused",
            )
            result = await fetcher.fetch(_item())

        assert isinstance(result, FailedFetch)
        assert result.reason == "http_status_error"
        assert result.detail == "403"

    asyncio.run(run())


def test_html_fetcher_uses_fallback_after_invalid_extraction() -> None:
    async def fallback(item: FilteredUrl) -> str:
        return "Fallback extraction produced a useful article body."

    async def run() -> None:
        transport = httpx.MockTransport(
            lambda request: httpx.Response(200, text="<html>ok</html>", request=request)
        )
        async with httpx.AsyncClient(transport=transport) as client:
            fetcher = HtmlFetcher(
                timeout_sec=10,
                min_chars=20,
                allowed_languages={"en"},
                user_agent="Tsuzuri/0.1",
                client=client,
                extractor=lambda html: "too short",
                fallback_fetcher=fallback,
            )
            result = await fetcher.fetch(_item())

        assert isinstance(result, ExtractedDocument)
        assert result.extraction_method == "playwright_trafilatura"
        assert result.status_code == 200

    asyncio.run(run())
