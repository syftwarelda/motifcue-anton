from __future__ import annotations

import asyncio
import base64
import json
import logging
import re
from pathlib import Path
from time import perf_counter
from typing import TypeVar

import httpx
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)


class LlamaClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        text_model: str,
        vision_model: str,
        embedding_model: str,
        timeout: float,
        max_retries: int,
    ) -> None:
        self.text_model = text_model
        self.vision_model = vision_model
        self.embedding_model = embedding_model
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=httpx.Timeout(timeout),
        )

    async def close(self) -> None:
        await self.client.aclose()

    @staticmethod
    def _extract_json(text: str) -> dict:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start, end = cleaned.find("{"), cleaned.rfind("}")
            if start < 0 or end <= start:
                raise
            return json.loads(cleaned[start : end + 1])

    async def _structured_completion(self, model: str, messages: list[dict], schema: type[T]) -> T:
        error: Exception | None = None
        for attempt in range(self.max_retries + 1):
            started = perf_counter()
            try:
                logger.debug("→ Local AI request · model=%s · attempt=%d", model, attempt + 1)
                response = await self.client.post(
                    "/chat/completions",
                    json={
                        "model": model,
                        "messages": messages,
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"},
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                result = schema.model_validate(self._extract_json(content))
                logger.debug(
                    "← Local AI response · model=%s · %.1f s",
                    model,
                    perf_counter() - started,
                )
                return result
            except (
                httpx.HTTPError,
                KeyError,
                IndexError,
                json.JSONDecodeError,
                ValidationError,
            ) as exc:
                error = exc
                if attempt == self.max_retries:
                    raise RuntimeError(
                        "The local model did not return valid structured data"
                    ) from exc
                logger.warning(
                    "Local AI response failed validation; retrying · model=%s · attempt=%d",
                    model,
                    attempt + 1,
                )
                await asyncio.sleep(2**attempt)
        raise RuntimeError("Unreachable") from error

    async def analyze_image(
        self, image_path: Path, system_prompt: str, user_prompt: str, schema: type[T]
    ) -> T:
        mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{encoded}"},
                    },
                ],
            },
        ]
        return await self._structured_completion(self.vision_model, messages, schema)

    async def synthesize(self, system_prompt: str, user_prompt: str, schema: type[T]) -> T:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        return await self._structured_completion(self.text_model, messages, schema)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Create local embeddings through the OpenAI-compatible Ollama endpoint."""
        if not texts:
            return []
        response = await self.client.post(
            "/embeddings",
            json={"model": self.embedding_model, "input": texts},
        )
        response.raise_for_status()
        rows = sorted(response.json()["data"], key=lambda row: row["index"])
        embeddings = [row["embedding"] for row in rows]
        if len(embeddings) != len(texts):
            raise RuntimeError("Embedding endpoint returned an unexpected number of vectors")
        return embeddings
