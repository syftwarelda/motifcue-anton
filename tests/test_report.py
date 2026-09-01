from datetime import UTC, datetime

from anton.report import build_report
from anton.schemas import Account, AccountSynthesis, PostFinding, VisualAnalysis


def test_build_report_smoke(tmp_path) -> None:
    synthesis = AccountSynthesis(
        account_positioning="Clear, useful ideas delivered with a recognizable point of view.",
        executive_summary=[
            "Strong visual clarity.",
            "Useful topics earn attention.",
            "Hooks can improve.",
        ],
        audience_response_patterns=["Practical posts lead the available results."],
        content_pillars=["Education", "Process"],
        format_patterns=["Short video and carousels"],
        visual_identity=["Warm light", "Direct framing"],
        keep=["Lead with a useful promise."],
        change=["Make the opening frame more specific."],
        tests=["Compare two hook styles on the same topic."],
        thirty_day_plan=["Week 1: publish the first controlled test."],
    )
    finding = PostFinding(
        media_id="one",
        media_type="VIDEO",
        timestamp=datetime.now(UTC),
        metrics={"reach": 500, "total_interactions": 40},
        rates={"interaction_rate_by_reach": 8.0},
        visual=VisualAnalysis(summary="A clear subject fills the opening frame."),
    )
    output = build_report(
        tmp_path / "report.pdf",
        "MotifCue",
        "en",
        Account(id="ig", username="creator", followers_count=1200),
        synthesis,
        [finding],
        {
            "analyzed_posts": 1,
            "median_reach": 500,
            "median_interactions": 40,
        },
    )
    assert output.exists()
    assert output.stat().st_size > 1000
