import httpx
import pytest
import respx

from anton.llm import LlamaClient


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
    )
    try:
        with respx.mock:
            route = respx.post("http://127.0.0.1:11434/v1/embeddings").mock(
                return_value=httpx.Response(
                    200,
                    json={"data": [{"index": 0, "embedding": [0.1, 0.2]}]},
                )
            )
            result = await client.embed(["creator strategy"])
        assert route.called
        assert result == [[0.1, 0.2]]
    finally:
        await client.close()
