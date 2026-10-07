"""Map summarization for extracted documents."""

import json
from typing import Any, Protocol

from pydantic import ValidationError

from tsuzuri.llm.prompts import build_map_prompt, build_repair_prompt
from tsuzuri.schemas import ExtractedDocument, MapSummary


class ChatClient(Protocol):
    async def chat(
        self,
        prompt: str,
        *,
        response_schema: dict[str, Any] | None = None,
    ) -> str: ...


class MapSummarizer:
    """Create one structured summary per extracted document."""

    def __init__(self, client: ChatClient) -> None:
        self._client = client

    async def summarize(self, document: ExtractedDocument) -> MapSummary:
        """Summarize one document, retrying once with a JSON repair prompt."""
        schema = MapSummary.model_json_schema()
        raw = await self._client.chat(
            build_map_prompt(document),
            response_schema=schema,
        )
        try:
            return _parse_summary(raw)
        except (json.JSONDecodeError, ValidationError) as error:
            repaired = await self._client.chat(
                build_repair_prompt(raw, str(error)),
                response_schema=schema,
            )
            return _parse_summary(repaired)


def _parse_summary(raw: str) -> MapSummary:
    data = json.loads(_strip_code_fence(raw))
    return MapSummary.model_validate(data)


def _strip_code_fence(raw: str) -> str:
    stripped = raw.strip()
    if not stripped.startswith("\x60\x60\x60"):
        return stripped
    lines = stripped.splitlines()
    if lines and lines[0].startswith("\x60\x60\x60"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "\x60\x60\x60":
        lines = lines[:-1]
    return "\n".join(lines).strip()
