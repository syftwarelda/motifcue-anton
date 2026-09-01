from __future__ import annotations

import hashlib
import json
import logging
import math
import re
from collections.abc import Iterable
from dataclasses import dataclass
from html.parser import HTMLParser

import httpx

from anton.db import Database
from anton.knowledge_catalog import OFFICIAL_SOURCES
from anton.schemas import Account, PostFinding

logger = logging.getLogger(__name__)

_TOKEN_PATTERN = re.compile(r"[a-zA-ZÀ-ÖØ-öø-ÿ0-9][\wÀ-ÖØ-öø-ÿ-]{2,}", re.UNICODE)
_SPACE_PATTERN = re.compile(r"[ \t]+")
_STOPWORDS = {
    "and",
    "are",
    "for",
    "from",
    "instagram",
    "the",
    "this",
    "that",
    "with",
    "para",
    "por",
    "con",
    "del",
    "las",
    "los",
    "una",
    "que",
}


class _ReadableHtml(HTMLParser):
    ignored_tags = {"script", "style", "svg", "noscript", "nav", "footer"}
    block_tags = {
        "article",
        "br",
        "div",
        "h1",
        "h2",
        "h3",
        "h4",
        "li",
        "main",
        "p",
        "section",
        "td",
        "th",
    }

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in self.ignored_tags:
            self.ignored_depth += 1
        elif tag in self.block_tags and self.ignored_depth == 0:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self.ignored_tags and self.ignored_depth:
            self.ignored_depth -= 1
        elif tag in self.block_tags and self.ignored_depth == 0:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self.ignored_depth == 0:
            self.parts.append(data)

    def text(self) -> str:
        lines = []
        for line in "".join(self.parts).splitlines():
            normalized = _SPACE_PATTERN.sub(" ", line).strip()
            if normalized:
                lines.append(normalized)
        return "\n".join(lines)


@dataclass(frozen=True)
class KnowledgeSearchResult:
    source_id: str
    title: str
    url: str
    source_type: str
    context: str
    content: str
    score: float

    def as_prompt_context(self) -> dict:
        return {
            "title": self.title,
            "url": self.url,
            "source_type": self.source_type,
            "context": self.context,
            "guidance": self.content,
        }


class KnowledgeService:
    def __init__(self, db: Database, timeout: float = 45, embedder=None) -> None:
        self.db = db
        self.timeout = timeout
        self.embedder = embedder
        self.embedding_model = getattr(embedder, "embedding_model", None)

    def register_catalog(self) -> None:
        for source in OFFICIAL_SOURCES:
            self.db.upsert_knowledge_source(
                id=source["id"],
                title=source["title"],
                url=source["url"],
                source_type=source["source_type"],
                context=source["context"],
                tags_json=json.dumps(source["tags"]),
                status="approved",
                refresh_days=source["refresh_days"],
            )

    @staticmethod
    def _chunks(content: str, target_size: int = 1400, overlap: int = 180) -> list[str]:
        paragraphs = content.splitlines()
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            candidate = f"{current}\n{paragraph}".strip()
            if current and len(candidate) > target_size:
                chunks.append(current)
                current = f"{current[-overlap:]}\n{paragraph}".strip()
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks

    async def sync(self) -> dict[str, int]:
        self.register_catalog()
        summary = {
            "activated": 0,
            "pending": 0,
            "unchanged": 0,
            "failed": 0,
            "indexed": 0,
        }
        headers = {"User-Agent": "MotifCue-Anton-Knowledge/0.1 (+https://motifcue.vercel.app)"}
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout), follow_redirects=True, headers=headers
        ) as client:
            for source in self.db.knowledge_sources():
                if source.status != "approved":
                    continue
                try:
                    response = await client.get(source.url)
                    response.raise_for_status()
                    if len(response.content) > 5 * 1024 * 1024:
                        raise ValueError("SOURCE_TOO_LARGE")
                    parser = _ReadableHtml()
                    parser.feed(response.text)
                    content = parser.text()
                    if len(content) < 300:
                        raise ValueError("SOURCE_CONTENT_TOO_SHORT")
                    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
                    existing = self.db.knowledge_revision_by_hash(source.id, content_hash)
                    if existing:
                        self.db.mark_knowledge_checked(source.id)
                        summary["unchanged"] += 1
                        logger.info("  Knowledge unchanged · source=%s", source.id)
                        continue
                    activate = source.active_revision_id is None
                    self.db.save_knowledge_revision(
                        source.id,
                        content_hash,
                        content,
                        activate=activate,
                        chunks=self._chunks(content),
                    )
                    state = "activated" if activate else "pending"
                    summary[state] += 1
                    logger.info("  Knowledge %s · source=%s", state, source.id)
                except (httpx.HTTPError, ValueError) as exc:
                    error_code = exc.args[0] if isinstance(exc, ValueError) else type(exc).__name__
                    self.db.mark_knowledge_error(source.id, str(error_code))
                    summary["failed"] += 1
                    logger.warning("  Knowledge sync failed · source=%s", source.id)
        if self.embedder and self.embedding_model:
            try:
                summary["indexed"] = await self.index()
            except (httpx.HTTPError, KeyError, RuntimeError, TypeError, ValueError):
                logger.warning("Knowledge embedding index failed; lexical search remains available")
        return summary

    async def index(self, batch_size: int = 16) -> int:
        if not self.embedder or not self.embedding_model:
            return 0
        indexed = 0
        while True:
            chunks = self.db.knowledge_chunks_without_embedding(
                self.embedding_model, limit=batch_size
            )
            if not chunks:
                break
            embeddings = await self.embedder.embed(
                [chunk.content for chunk in chunks], task="search_document"
            )
            for chunk, embedding in zip(chunks, embeddings, strict=True):
                self.db.save_knowledge_embedding(
                    chunk.id,
                    self.embedding_model,
                    json.dumps(embedding, separators=(",", ":")),
                )
                indexed += 1
            logger.info("  Knowledge embeddings indexed · total=%d", indexed)
        return indexed

    def approve(self, source_id: str) -> None:
        self.db.approve_knowledge_source(source_id)

    @staticmethod
    def _tokens(value: str) -> set[str]:
        return {
            token.lower()
            for token in _TOKEN_PATTERN.findall(value)
            if token.lower() not in _STOPWORDS
        }

    def search(self, query: str, limit: int = 6) -> list[KnowledgeSearchResult]:
        query_tokens = self._tokens(query)
        if not query_tokens:
            return []
        scored: list[KnowledgeSearchResult] = []
        lowered_query = query.lower().strip()
        for source, chunk in self.db.active_knowledge_chunks():
            tags = " ".join(json.loads(source.tags_json))
            title_tokens = self._tokens(f"{source.title} {tags} {source.context}")
            content_tokens = self._tokens(chunk.content)
            title_overlap = len(query_tokens & title_tokens)
            content_overlap = len(query_tokens & content_tokens)
            if title_overlap == 0 and content_overlap == 0:
                continue
            score = (title_overlap * 4) + content_overlap
            if lowered_query and lowered_query in chunk.content.lower():
                score += 5
            scored.append(
                KnowledgeSearchResult(
                    source_id=source.id,
                    title=source.title,
                    url=source.url,
                    source_type=source.source_type,
                    context=source.context,
                    content=chunk.content,
                    score=float(score),
                )
            )
        scored.sort(key=lambda result: (-result.score, result.source_id))
        results: list[KnowledgeSearchResult] = []
        per_source: dict[str, int] = {}
        for result in scored:
            if per_source.get(result.source_id, 0) >= 2:
                continue
            results.append(result)
            per_source[result.source_id] = per_source.get(result.source_id, 0) + 1
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _cosine(left: list[float], right: list[float]) -> float:
        if len(left) != len(right) or not left:
            return 0.0
        dot = sum(a * b for a, b in zip(left, right, strict=True))
        left_norm = math.sqrt(sum(value * value for value in left))
        right_norm = math.sqrt(sum(value * value for value in right))
        if left_norm == 0 or right_norm == 0:
            return 0.0
        return dot / (left_norm * right_norm)

    async def semantic_search(self, query: str, limit: int = 6) -> list[KnowledgeSearchResult]:
        if not self.embedder or not self.embedding_model:
            return self.search(query, limit)
        candidates = []
        for source, chunk in self.db.active_knowledge_chunks():
            if chunk.embedding_model != self.embedding_model or not chunk.embedding_json:
                continue
            candidates.append((source, chunk, json.loads(chunk.embedding_json)))
        if not candidates:
            return self.search(query, limit)
        try:
            query_vector = (await self.embedder.embed([query], task="search_query"))[0]
        except (httpx.HTTPError, KeyError, IndexError, RuntimeError, TypeError, ValueError):
            logger.warning("Knowledge semantic search failed; using lexical fallback")
            return self.search(query, limit)

        query_tokens = self._tokens(query)
        scored = []
        for source, chunk, vector in candidates:
            semantic_score = self._cosine(query_vector, vector)
            tags = " ".join(json.loads(source.tags_json))
            metadata_overlap = len(query_tokens & self._tokens(f"{source.title} {tags}"))
            score = semantic_score + (metadata_overlap * 0.03)
            scored.append(
                KnowledgeSearchResult(
                    source_id=source.id,
                    title=source.title,
                    url=source.url,
                    source_type=source.source_type,
                    context=source.context,
                    content=chunk.content,
                    score=round(score, 4),
                )
            )
        scored.sort(key=lambda result: (-result.score, result.source_id))
        results = []
        per_source: dict[str, int] = {}
        for result in scored:
            if per_source.get(result.source_id, 0) >= 2:
                continue
            results.append(result)
            per_source[result.source_id] = per_source.get(result.source_id, 0) + 1
            if len(results) >= limit:
                break
        return results

    async def report_context(
        self, account: Account, findings: Iterable[PostFinding], limit: int
    ) -> list[dict]:
        parts = ["Instagram creator content strategy engagement reach"]
        if account.biography:
            parts.append(account.biography[:300])
        media_types: set[str] = set()
        topic_tags: set[str] = set()
        intents: set[str] = set()
        for finding in findings:
            media_types.add(finding.media_type)
            topic_tags.update(finding.visual.topic_tags[:3])
            if finding.visual.content_intent:
                intents.add(finding.visual.content_intent)
        parts.extend(sorted(media_types))
        parts.extend(sorted(topic_tags)[:15])
        parts.extend(sorted(intents))
        results = await self.semantic_search(" ".join(parts), limit)
        return [result.as_prompt_context() for result in results]

    def status_rows(self) -> list[dict]:
        rows = []
        for source in self.db.knowledge_sources():
            pending = self.db.pending_knowledge_revision(source.id)
            rows.append(
                {
                    "id": source.id,
                    "active": bool(source.active_revision_id),
                    "pending": bool(pending),
                    "checked": source.last_checked_at,
                    "error": source.last_error,
                }
            )
        return rows
