import asyncio
from datetime import UTC, datetime
from typing import Any

from tsuzuri.llm.map_summarizer import MapSummarizer
from tsuzuri.schemas import ExtractedDocument


class FakeChatClient:
    def __init__(self, responses: list[str]) -> None:
        self.responses = responses
        self.prompts: list[str] = []
        self.schemas: list[dict[str, Any] | None] = []

    async def chat(
        self,
        prompt: str,
        *,
        response_schema: dict[str, Any] | None = None,
    ) -> str:
        self.prompts.append(prompt)
        self.schemas.append(response_schema)
        return self.responses.pop(0)


def _document() -> ExtractedDocument:
    return ExtractedDocument(
        doc_id="Source-1",
        url="https://example.com/news",
        normalized_url="https://example.com/news",
        document_type="html",
        title="Example",
        content="The regulator announced an AI policy update.",
        estimated_tokens=7,
        domain="example.com",
        extraction_method="httpx_trafilatura",
        content_hash="hash",
        fetched_at=datetime(2026, 1, 1, tzinfo=UTC),
        source_query="AI regulation",
        search_rank=1,
    )


def test_map_summarizer_parses_json_summary() -> None:
    async def run() -> None:
        client = FakeChatClient(
            [
                """
                {
                  "doc_id": "Source-1",
                  "title": "Example",
                  "document_type": "html",
                  "language": "en",
                  "relevance_score": 4,
                  "is_news_like": true,
                  "is_search_noise": false,
                  "topic_tags": ["AI regulation"],
                  "entities": ["Regulator"],
                  "event_date": null,
                  "published_date": null,
                  "key_facts": ["A regulator announced an AI policy update."],
                  "claims": [],
                  "uncertainties": [],
                  "conflicting_points": [],
                  "short_summary": "A regulator announced an AI policy update."
                }
                """
            ]
        )

        summary = await MapSummarizer(client).summarize(_document())

        assert summary.doc_id == "Source-1"
        assert summary.relevance_score == 4
        assert "https://example.com/news" not in client.prompts[0]
        assert "Search Query: AI regulation" in client.prompts[0]
        assert "Relevance scoring rubric:" in client.prompts[0]
        assert '"relevance_score": 1' not in client.prompts[0]
        assert client.schemas[0] is not None
        assert client.schemas[0]["title"] == "MapSummary"

    asyncio.run(run())


def test_map_summarizer_retries_with_repair_prompt() -> None:
    async def run() -> None:
        client = FakeChatClient(
            [
                "not json",
                """
                {
                  "doc_id": "Source-1",
                  "title": "Example",
                  "document_type": "html",
                  "language": "en",
                  "relevance_score": 3,
                  "is_news_like": true,
                  "is_search_noise": false,
                  "topic_tags": [],
                  "entities": [],
                  "event_date": null,
                  "published_date": null,
                  "key_facts": [],
                  "claims": [],
                  "uncertainties": [],
                  "conflicting_points": [],
                  "short_summary": "Repaired summary."
                }
                """,
            ]
        )

        summary = await MapSummarizer(client).summarize(_document())

        assert summary.short_summary == "Repaired summary."
        assert len(client.prompts) == 2
        assert "Repair the following invalid JSON response" in client.prompts[1]
        assert all(schema is not None for schema in client.schemas)

    asyncio.run(run())
