"""Global reduce summarization over validated map summaries."""

import json
from typing import Any, Protocol

from pydantic import ValidationError

from tsuzuri.llm.prompts import build_reduce_prompt, build_repair_prompt
from tsuzuri.schemas import MapSummary, ReportSynthesis


class ChatClient(Protocol):
    async def chat(
        self,
        prompt: str,
        *,
        response_schema: dict[str, Any] | None = None,
    ) -> str: ...


class ReduceSummarizer:
    """Synthesize multiple map summaries into a cited report structure."""

    def __init__(self, client: ChatClient) -> None:
        self._client = client

    async def summarize(
        self,
        *,
        query: str,
        summaries: list[MapSummary],
    ) -> ReportSynthesis:
        schema = ReportSynthesis.model_json_schema()
        raw = await self._client.chat(
            build_reduce_prompt(query, summaries),
            response_schema=schema,
        )
        try:
            synthesis = _parse_synthesis(raw)
        except (json.JSONDecodeError, ValidationError) as error:
            repaired = await self._client.chat(
                build_repair_prompt(raw, str(error)),
                response_schema=schema,
            )
            synthesis = _parse_synthesis(repaired)

        _validate_source_ids(synthesis, summaries)
        return synthesis


def _parse_synthesis(raw: str) -> ReportSynthesis:
    return ReportSynthesis.model_validate(json.loads(_strip_code_fence(raw)))


def _strip_code_fence(raw: str) -> str:
    stripped = raw.strip()
    fence = chr(96) * 3
    if not stripped.startswith(fence):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith(fence):
        lines = lines[1:]
    if lines and lines[-1].strip() == fence:
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _validate_source_ids(
    synthesis: ReportSynthesis,
    summaries: list[MapSummary],
) -> None:
    known_ids = {summary.doc_id for summary in summaries}
    cited_ids = {
        source_id
        for section in (
            synthesis.executive_summary,
            synthesis.key_developments,
            synthesis.uncertainties,
        )
        for point in section
        for source_id in point.source_ids
    }
    unknown = sorted(cited_ids - known_ids)
    if unknown:
        raise ValueError(f"Reduce output cited unknown source IDs: {unknown}")
