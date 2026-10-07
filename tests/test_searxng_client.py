import asyncio

import httpx
import pytest

from tsuzuri.search.searxng_client import (
    SearxngClient,
    SearxngUnavailableError,
)


def test_searxng_client_parses_results_and_request_params() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://Example.com/news?utm_source=x#section",
                        "title": "Example",
                        "content": "Snippet",
                        "engine": "engine-a",
                        "engines": ["engine-a", "engine-b"],
                        "score": 4.0,
                        "category": "news",
                        "publishedDate": "2026-01-01",
                    }
                ]
            },
        )

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            transport=transport, base_url="https://searx.example"
        ) as http_client:
            client = SearxngClient(
                base_url="https://searx.example",
                language="en",
                categories=["news", "general"],
                timeout_sec=10,
                retry_count=0,
                client=http_client,
            )
            results = await client.search("AI regulation", max_results=10)

        assert len(results) == 1
        assert results[0].normalized_url == "https://example.com/news"
        assert results[0].title == "Example"
        assert results[0].snippet == "Snippet"
        assert results[0].engine == "engine-a"
        assert results[0].engine_hits == 2
        assert results[0].score == 4.0
        assert results[0].category == "news"
        assert results[0].published_hint == "2026-01-01"
        assert requests[0].url.params["q"] == "AI regulation"
        assert requests[0].url.params["format"] == "json"
        assert requests[0].url.params["language"] == "en"
        assert requests[0].url.params["categories"] == "news,general"

    asyncio.run(run())


def test_searxng_client_retries_http_errors() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(503, request=request)
        return httpx.Response(200, json={"results": []}, request=request)

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            transport=transport, base_url="https://searx.example"
        ) as http_client:
            client = SearxngClient(
                base_url="https://searx.example",
                language="en",
                categories=["news"],
                timeout_sec=10,
                retry_count=1,
                client=http_client,
                retry_delay_sec=0,
            )
            assert await client.search("AI regulation", max_results=10) == []

    asyncio.run(run())
    assert call_count == 2


def test_searxng_client_retries_empty_results_when_engines_are_unresponsive() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(
                200,
                json={
                    "results": [],
                    "unresponsive_engines": [["brave", "too many requests"]],
                },
                request=request,
            )
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "url": "https://example.com/news",
                        "title": "Recovered result",
                        "content": "AI regulation update",
                    }
                ]
            },
            request=request,
        )

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            transport=transport, base_url="https://searx.example"
        ) as http_client:
            client = SearxngClient(
                base_url="https://searx.example",
                language="en",
                categories=["news"],
                timeout_sec=10,
                retry_count=1,
                client=http_client,
                retry_delay_sec=0,
            )
            results = await client.search("AI regulation", max_results=10)
            assert len(results) == 1

    asyncio.run(run())
    assert call_count == 2


def test_searxng_client_surfaces_engine_outage_after_retry_exhaustion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "results": [],
                "unresponsive_engines": [
                    ["brave", "too many requests"],
                    ["duckduckgo", "CAPTCHA"],
                ],
            },
            request=request,
        )

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(
            transport=transport, base_url="https://searx.example"
        ) as http_client:
            client = SearxngClient(
                base_url="https://searx.example",
                language="en",
                categories=["news"],
                timeout_sec=10,
                retry_count=0,
                client=http_client,
            )
            with pytest.raises(SearxngUnavailableError, match="too many requests"):
                await client.search("AI regulation", max_results=10)

    asyncio.run(run())
