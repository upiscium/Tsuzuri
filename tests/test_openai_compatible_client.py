import pytest
import asyncio
import json

import httpx

from tsuzuri.llm.openai_compatible_client import OpenAICompatibleClient


def test_openai_compatible_client_posts_chat_completion() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "result"}}]},
            request=request,
        )

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = OpenAICompatibleClient(
                base_url="https://llm.example/v1",
                model="local-9b",
                api_key="secret",
                timeout_sec=10,
                temperature=0.2,
                max_tokens=2048,
                retry_count=0,
                client=http_client,
            )

            assert await client.chat("Summarize") == "result"

        request = requests[0]
        body = json.loads(request.content)
        assert request.method == "POST"
        assert str(request.url) == "https://llm.example/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer secret"
        assert body["model"] == "local-9b"
        assert body["messages"] == [{"role": "user", "content": "Summarize"}]
        assert body["max_tokens"] == 2048

    asyncio.run(run())


def test_openai_compatible_client_uses_json_schema_when_available() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"value": 1}'}}]},
            request=request,
        )

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = OpenAICompatibleClient(
                base_url="https://llm.example/v1",
                model="local-4b",
                api_key=None,
                timeout_sec=10,
                temperature=0,
                max_tokens=128,
                retry_count=0,
                client=http_client,
            )
            result = await client.chat(
                "Return JSON",
                response_schema={
                    "type": "object",
                    "properties": {"value": {"type": "integer"}},
                    "required": ["value"],
                },
            )

        assert result == '{"value": 1}'
        body = json.loads(requests[0].content)
        assert body["response_format"]["type"] == "json_schema"
        assert body["response_format"]["json_schema"]["strict"] is True

    asyncio.run(run())


def test_openai_compatible_client_auto_falls_back_from_structured_output() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        body = json.loads(request.content)
        response_format = body.get("response_format")
        if response_format is not None:
            return httpx.Response(
                400, text="unsupported response_format", request=request
            )
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"value": 1}'}}]},
            request=request,
        )

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(transport=transport) as http_client:
            client = OpenAICompatibleClient(
                base_url="https://llm.example/v1",
                model="local-2b",
                api_key=None,
                timeout_sec=10,
                temperature=0,
                max_tokens=128,
                retry_count=0,
                structured_output="auto",
                client=http_client,
            )
            assert (
                await client.chat(
                    "Return JSON",
                    response_schema={"type": "object"},
                )
                == '{"value": 1}'
            )

        assert len(requests) == 3
        assert (
            json.loads(requests[0].content)["response_format"]["type"] == "json_schema"
        )
        assert (
            json.loads(requests[1].content)["response_format"]["type"] == "json_object"
        )
        assert "response_format" not in json.loads(requests[2].content)

    asyncio.run(run())


def test_openai_compatible_client_supports_standard_reasoning_effort_none() -> None:
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}
                ]
            },
            request=request,
        )

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = OpenAICompatibleClient(
                base_url="https://llm.example/v1",
                model="local-9b",
                api_key=None,
                timeout_sec=10,
                temperature=0,
                max_tokens=2048,
                retry_count=0,
                reasoning_effort="none",
                client=client,
            )
            assert await adapter.chat("Return JSON") == '{"ok":true}'

    asyncio.run(run())
    assert seen[0]["reasoning_effort"] == "none"


def test_openai_compatible_client_rejects_empty_truncated_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"content": "", "reasoning": "thinking"},
                        "finish_reason": "length",
                    }
                ]
            },
            request=request,
        )

    async def run() -> None:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            adapter = OpenAICompatibleClient(
                base_url="https://llm.example/v1",
                model="local-9b",
                api_key=None,
                timeout_sec=10,
                temperature=0,
                max_tokens=256,
                retry_count=0,
                client=client,
            )
            with pytest.raises(ValueError, match="exhausted max_tokens"):
                await adapter.chat("Return JSON")

    asyncio.run(run())
