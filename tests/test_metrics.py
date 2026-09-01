from datetime import UTC, datetime

from anton.metrics import account_metrics, media_metrics, safe_rate
from anton.schemas import MediaInsights, MediaItem, PostFinding, VisualAnalysis


def test_safe_rate_handles_missing_denominator() -> None:
    assert safe_rate(10, 0) is None
    assert safe_rate(10, None) is None
    assert safe_rate(10, 200) == 5.0


def test_media_metrics_prefers_insights_and_derives_rates() -> None:
    item = MediaItem(
        id="post-1",
        media_type="VIDEO",
        timestamp=datetime.now(UTC),
        like_count=2,
        insights=MediaInsights(
            views=1000,
            reach=500,
            likes=20,
            comments=5,
            shares=10,
            saved=15,
            total_interactions=50,
        ),
    )
    metrics, rates = media_metrics(item)
    assert metrics["likes"] == 20
    assert rates["interaction_rate_by_reach"] == 10.0
    assert rates["save_rate_by_reach"] == 3.0


def test_account_metrics_ranks_by_interactions() -> None:
    findings = []
    for media_id, interactions in (("a", 4), ("b", 18), ("c", 9)):
        findings.append(
            PostFinding(
                media_id=media_id,
                media_type="IMAGE",
                timestamp=datetime.now(UTC),
                metrics={"reach": 100, "views": 120, "total_interactions": interactions},
                rates={},
                visual=VisualAnalysis(summary="An image"),
            )
        )
    summary = account_metrics(findings)
    assert summary["top_media_ids"] == ["b", "c", "a"]
    assert summary["median_interactions"] == 9
    assert summary["total_reach"] == 300
    assert summary["total_views"] == 360
    assert summary["total_interactions"] == 31
    assert summary["posts_with_reach"] == 3
    assert summary["format_metrics"]["IMAGE"] == {
        "count": 3,
        "median_reach": 100,
        "median_views": 120,
        "median_interactions": 9,
        "median_interaction_rate": None,
    }
