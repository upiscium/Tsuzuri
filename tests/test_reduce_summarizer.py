import asyncio
from typing import Any

import pytest

from tsuzuri.llm.reduce_summarizer import ReduceSummarizer
from tsuzuri.schemas import MapSummary


class FakeChatClient:
    def __init__(self, response: str) -> None:
        self.response = response
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
        return self.response


def _summary() -> MapSummary:
    return MapSummary(
        doc_id="Source-1",
        title="Example",
        document_type="html",
        language="en",
        relevance_score=4,
        is_news_like=True,
        is_search_noise=False,
        topic_tags=["AI regulation"],
        entities=["Regulator"],
        key_facts=["A regulator announced a policy update."],
        claims=[],
        uncertainties=[],
        conflicting_points=[],
        short_summary="A regulator announced a policy update.",
    )


def test_reduce_summarizer_returns_cited_synthesis() -> None:
    async def run() -> None:
        client = FakeChatClient(
            """
            {
              "headline": "AI regulation update",
              "executive_summary": [
                {"text": "A regulator announced a policy update.", "source_ids": ["Source-1"]}
              ],
              "key_developments": [
                {"text": "The policy update is the main development.", "source_ids": ["Source-1"]}
              ],
              "uncertainties": []
            }
            """
        )

        result = await ReduceSummarizer(client).summarize(
            query="AI regulation",
            summaries=[_summary()],
        )

        assert result.headline == "AI regulation update"
        assert result.executive_summary[0].source_ids == ["Source-1"]
        assert client.schemas[0] is not None
        assert "https://" not in client.prompts[0]

    asyncio.run(run())


def test_reduce_summarizer_rejects_unknown_source_ids() -> None:
    async def run() -> None:
        client = FakeChatClient(
            """
            {
              "headline": "AI regulation update",
              "executive_summary": [
                {"text": "Unsupported point.", "source_ids": ["Source-999"]}
              ],
              "key_developments": [],
              "uncertainties": []
            }
            """
        )

        with pytest.raises(ValueError, match="unknown source IDs"):
            await ReduceSummarizer(client).summarize(
                query="AI regulation",
                summaries=[_summary()],
            )

    asyncio.run(run())
