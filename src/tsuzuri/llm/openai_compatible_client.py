"""OpenAI-compatible chat completions client."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any, Literal

import httpx

JsonObject = Mapping[str, Any]
StructuredOutputMode = Literal["auto", "json_schema", "json_object", "prompt"]


class OpenAICompatibleClient:
    """Small async client for OpenAI-compatible /v1/chat/completions APIs."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None,
        timeout_sec: float,
        temperature: float,
        max_tokens: int,
        retry_count: int,
        structured_output: StructuredOutputMode = "auto",
        client: httpx.AsyncClient | None = None,
        retry_delay_sec: float = 1.0,
    ) -> None:
        self._chat_url = f"{base_url.rstrip('/')}/chat/completions"
        self._model = model
        self._api_key = api_key
        self._timeout = httpx.Timeout(timeout_sec)
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._retry_count = retry_count
        self._structured_output = structured_output
        self._client = client
        self._retry_delay_sec = retry_delay_sec

    async def chat(
        self,
        prompt: str,
        *,
        response_schema: dict[str, Any] | None = None,
    ) -> str:
        """Send a chat completion request and return assistant message content."""
        if self._client is not None:
            return await self._chat_with_capability_fallback(
                self._client, prompt, response_schema
            )

        headers = self._headers()
        async with httpx.AsyncClient(timeout=self._timeout, headers=headers) as client:
            return await self._chat_with_capability_fallback(
                client, prompt, response_schema
            )

    async def _chat_with_capability_fallback(
        self,
        client: httpx.AsyncClient,
        prompt: str,
        response_schema: dict[str, Any] | None,
    ) -> str:
        modes = _structured_output_attempts(
            self._structured_output, has_schema=response_schema is not None
        )
        last_error: httpx.HTTPStatusError | None = None

        for mode in modes:
            response_format = _response_format(mode, response_schema)
            try:
                return await self._chat_with_retry(
                    client,
                    prompt,
                    response_format=response_format,
                )
            except httpx.HTTPStatusError as error:
                last_error = error
                if (
                    self._structured_output == "auto"
                    and mode != "prompt"
                    and error.response.status_code in {400, 404, 415, 422}
                ):
                    continue
                raise

        if last_error is not None:
            raise last_error
        raise RuntimeError("OpenAI-compatible capability fallback exhausted")

    async def _chat_with_retry(
        self,
        client: httpx.AsyncClient,
        prompt: str,
        *,
        response_format: dict[str, Any] | None,
    ) -> str:
        attempts = self._retry_count + 1
        for attempt in range(attempts):
            try:
                response = await client.post(
                    self._chat_url,
                    headers=self._headers(),
                    json=self._request_body(
                        prompt,
                        response_format=response_format,
                    ),
                )
                response.raise_for_status()
                data = response.json()
                if not isinstance(data, Mapping):
                    raise ValueError("OpenAI-compatible response must be a JSON object")
                return _message_content(data)
            except httpx.HTTPStatusError as error:
                if error.response.status_code < 500 or attempt == attempts - 1:
                    raise
                await asyncio.sleep(self._retry_delay_sec)
            except (httpx.TransportError, ValueError):
                if attempt == attempts - 1:
                    raise
                await asyncio.sleep(self._retry_delay_sec)

        raise RuntimeError("OpenAI-compatible retry loop exited unexpectedly")

    def _request_body(
        self,
        prompt: str,
        *,
        response_format: dict[str, Any] | None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
        }
        if response_format is not None:
            body["response_format"] = response_format
        return body

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            return {}
        return {"Authorization": f"Bearer {self._api_key}"}


def _structured_output_attempts(
    mode: StructuredOutputMode, *, has_schema: bool
) -> list[StructuredOutputMode]:
    if not has_schema:
        return ["prompt"]
    if mode == "auto":
        return ["json_schema", "json_object", "prompt"]
    return [mode]


def _response_format(
    mode: StructuredOutputMode,
    response_schema: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if mode == "prompt" or response_schema is None:
        return None
    if mode == "json_object":
        return {"type": "json_object"}
    return {
        "type": "json_schema",
        "json_schema": {
            "name": "tsuzuri_response",
            "strict": True,
            "schema": response_schema,
        },
    }


def _message_content(data: JsonObject) -> str:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("OpenAI-compatible response missing choices")

    first_choice = choices[0]
    if not isinstance(first_choice, Mapping):
        raise ValueError("OpenAI-compatible response contains invalid choice")

    message = first_choice.get("message")
    if not isinstance(message, Mapping):
        raise ValueError("OpenAI-compatible response missing message object")

    content = message.get("content")
    if not isinstance(content, str):
        raise ValueError("OpenAI-compatible response missing message content")
    return content
