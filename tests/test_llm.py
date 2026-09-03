import json

import httpx
import pytest
import respx
from pydantic import BaseModel

from anton.llm import LlamaClient


class StructuredReply(BaseModel):
    ok: bool


def test_extract_json_accepts_fenced_response() -> None:
    assert LlamaClient._extract_json('```json\n{"ok": true}\n```') == {"ok": True}


def test_extract_json_finds_embedded_object() -> None:
    assert LlamaClient._extract_json('Here it is: {"count": 2}') == {"count": 2}


@pytest.mark.asyncio
async def test_embed_uses_local_openai_compatible_endpoint() -> None:
    client = LlamaClient(
        "http://127.0.0.1:11434/v1",
        "ollama",
        "text-model",
        "vision-model",
        "embedding-model",
        10,
        0,
        priority="motifcue",
        embedding_base_url="http://127.0.0.1:18083/v1",
        embedding_api_key="not-needed",
    )
    try:
        with respx.mock:
            route = respx.post("http://127.0.0.1:18083/v1/embeddings").mock(
                return_value=httpx.Response(
                    200,
                    json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]},
                )
            )
            result = await client.embed(["creator strategy"], task="search_document")
        assert route.called
        assert "x-anton-priority" not in route.calls.last.request.headers
        assert route.calls.last.request.headers["authorization"] == "Bearer not-needed"
        assert route.calls.last.request.read()
        assert route.calls.last.request.content
        assert b"search_document: creator strategy" in route.calls.last.request.content
        assert result == [[0.1, 0.2]]
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_synthesis_uses_low_reasoning_without_output_limit() -> None:
    client = LlamaClient(
        "http://127.0.0.1:11434/v1",
        "key",
        "text-model",
        "vision-model",
        "embedding-model",
        10,
        0,
    )
    try:
        with respx.mock:
            route = respx.post("http://127.0.0.1:11434/v1/chat/completions").mock(
                return_value=httpx.Response(
                    200,
                    json={"choices": [{"message": {"content": '{"ok": true}'}}]},
                )
            )
            result = await client.synthesize("system", "user", StructuredReply)
        payload = json.loads(route.calls.last.request.content)
        assert payload["reasoning_effort"] == "low"
        assert "max_tokens" not in payload
        assert result.ok is True
    finally:
        await client.close()
