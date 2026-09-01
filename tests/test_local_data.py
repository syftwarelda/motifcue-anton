import json
from datetime import UTC, datetime

import pytest

from anton.analyzer import write_snapshot
from anton.config import Settings
from anton.db import Database, LocalStage
from anton.local_data import export_order_data
from anton.pipeline import Pipeline
from anton.schemas import (
    Account,
    AccountSynthesis,
    InstagramDataPage,
    MediaItem,
    Paging,
    VisualAnalysis,
)


def _settings(tmp_path) -> Settings:
    return Settings(
        motifcue_api_base_url="https://motifcue.example.com",
        anton_internal_api_key="test-secret",
        data_directory=tmp_path / "data",
        report_directory=tmp_path / "reports",
        database_url=f"sqlite:///{tmp_path / 'anton.db'}",
    )


def _seed_order(settings: Settings, db: Database, order_id: str) -> None:
    snapshot = InstagramDataPage(
        orderId=order_id,
        account=Account(id="ig-1", username="creator", followers_count=1200),
        media=[
            MediaItem(
                id="post-1",
                caption="A useful post",
                media_type="IMAGE",
                timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                like_count=20,
                comments_count=3,
            )
        ],
        paging=Paging(),
    )
    path = settings.data_directory / "orders" / order_id / "instagram-snapshot.json"
    write_snapshot(path, snapshot.model_dump(mode="json"))
    endpoint_path = (
        settings.data_directory
        / "orders"
        / order_id
        / "endpoint-responses"
        / "instagram-data-page-001.json"
    )
    write_snapshot(endpoint_path, {"rawMarker": "exact-endpoint-response"})
    db.get_or_create_job(order_id, "GENERATING_REPORT")
    synthesis = AccountSynthesis(
        account_positioning="A creator with a clear point of view.",
        executive_summary=["Clear topic.", "Recognizable voice.", "A testable next step."],
        audience_response_patterns=["Useful content earns attention."],
        content_pillars=["Education", "Process"],
        format_patterns=["Images explain one useful idea."],
        visual_identity=["Direct framing"],
        keep=["Keep the clear subject."],
        change=["Sharpen the opening."],
        tests=["Test two opening styles."],
        thirty_day_plan=["Publish one controlled test each week."],
    )
    db.update_job(
        order_id,
        stage=LocalStage.SYNTHESIZED,
        snapshot_path=str(path),
        synthesis_json=synthesis.model_dump_json(),
    )
    visual = VisualAnalysis(summary="A clear image with one main subject.")
    db.save_media_result(order_id, "post-1", "fingerprint", visual.model_dump_json())


def test_export_order_data_contains_saved_endpoint_payload(tmp_path) -> None:
    settings = _settings(tmp_path)
    db = Database(settings.database_url)
    db.create_schema()
    _seed_order(settings, db, "order-1")

    output = export_order_data(settings, db, "order-1")
    exported = json.loads(output.read_text(encoding="utf-8"))

    assert exported["orderId"] == "order-1"
    assert exported["instagramData"]["account"]["username"] == "creator"
    assert exported["instagramData"]["media"][0]["caption"] == "A useful post"
    assert exported["accountSynthesis"]["content_pillars"] == ["Education", "Process"]
    assert exported["mediaAnalyses"][0]["mediaId"] == "post-1"
    assert exported["endpointResponses"][0]["payload"]["rawMarker"] == ("exact-endpoint-response")
    assert "accessToken" not in output.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_regenerate_local_uses_snapshot_and_cache_without_backend(tmp_path) -> None:
    settings = _settings(tmp_path)
    db = Database(settings.database_url)
    db.create_schema()
    _seed_order(settings, db, "order-2")
    pipeline = Pipeline(
        settings,
        db,
        backend=object(),
        analyzer=object(),
        storage=object(),
        llm=object(),
    )

    output = await pipeline.regenerate_local("order-2")

    assert output == settings.report_directory / "order-2-local.pdf"
    assert output.exists()
    assert output.stat().st_size > 1000
