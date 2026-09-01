import json

import httpx
import pytest
import respx

from anton.db import Database
from anton.knowledge import KnowledgeService


class FakeEmbedder:
    embedding_model = "test-embedding"
    tasks = []

    async def embed(self, texts, *, task=None):
        self.tasks.append(task)
        return [
            [
                float("visual" in text.lower()),
                float("policy" in text.lower()),
                0.25,
            ]
            for text in texts
        ]


def _database(tmp_path) -> Database:
    db = Database(f"sqlite:///{tmp_path / 'knowledge.db'}")
    db.create_schema()
    return db


@pytest.mark.asyncio
async def test_sync_requires_review_before_replacing_active_knowledge(
    tmp_path, monkeypatch
) -> None:
    source = {
        "id": "official-test",
        "title": "Official creator guidance",
        "url": "https://official.example.com/guidance",
        "source_type": "meta_official",
        "context": "organic",
        "tags": ["reels", "retention"],
        "refresh_days": 7,
    }
    monkeypatch.setattr("anton.knowledge.OFFICIAL_SOURCES", [source])
    db = _database(tmp_path)
    service = KnowledgeService(db)

    first_html = (
        "<main><h1>Reels guidance</h1><p>" + ("Original retention advice. " * 20) + "</p></main>"
    )
    with respx.mock:
        route = respx.get(source["url"])
        route.mock(return_value=httpx.Response(200, text=first_html))
        first = await service.sync()

    assert first["activated"] == 1
    assert service.search("reels retention")[0].source_id == "official-test"
    active_revision = db.knowledge_source("official-test").active_revision_id

    changed_html = (
        "<main><h1>Reels guidance</h1><p>" + ("Updated sharing advice. " * 20) + "</p></main>"
    )
    with respx.mock:
        respx.get(source["url"]).mock(return_value=httpx.Response(200, text=changed_html))
        second = await service.sync()

    status = service.status_rows()[0]
    assert second["pending"] == 1
    assert status["pending"] is True
    assert db.knowledge_source("official-test").active_revision_id == active_revision

    service.approve("official-test")

    assert db.knowledge_source("official-test").active_revision_id != active_revision
    assert service.search("updated sharing")[0].source_id == "official-test"


def test_search_returns_only_approved_active_chunks(tmp_path) -> None:
    db = _database(tmp_path)
    db.upsert_knowledge_source(
        id="source-1",
        title="Reels experiments",
        url="https://example.com/reels",
        source_type="curated",
        context="organic",
        tags_json=json.dumps(["reels", "experiments"]),
        status="approved",
        refresh_days=30,
    )
    db.save_knowledge_revision(
        "source-1",
        "a" * 64,
        "Test one creative variable at a time.",
        activate=True,
        chunks=["Test one creative variable at a time and compare the result."],
    )
    service = KnowledgeService(db)

    results = service.search("reels creative experiments")

    assert len(results) == 1
    assert results[0].context == "organic"


@pytest.mark.asyncio
async def test_semantic_search_uses_local_embeddings(tmp_path) -> None:
    db = _database(tmp_path)
    db.upsert_knowledge_source(
        id="source-visual",
        title="Creative composition",
        url="https://example.com/visual",
        source_type="curated",
        context="organic",
        tags_json="[]",
        status="approved",
        refresh_days=30,
    )
    db.save_knowledge_revision(
        "source-visual",
        "b" * 64,
        "Visual hierarchy guidance.",
        activate=True,
        chunks=["Visual hierarchy makes the main subject easier to understand."],
    )
    embedder = FakeEmbedder()
    embedder.tasks = []
    service = KnowledgeService(db, embedder=embedder)
    assert await service.index() == 1

    results = await service.semantic_search("improve the visual presentation")

    assert results[0].source_id == "source-visual"
    assert results[0].score > 0
    assert embedder.tasks == ["search_document", "search_query"]
