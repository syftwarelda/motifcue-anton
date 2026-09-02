from datetime import UTC, datetime

from anton.report import build_report
from anton.schemas import (
    Account,
    AccountSynthesis,
    ExperimentPlan,
    GrowthOpportunity,
    PostFinding,
    ProductionIdea,
    VisualAnalysis,
)


def test_experiment_replaces_unsupported_percentage_target() -> None:
    experiment = ExperimentPlan(
        hypothesis="The variant will improve reach by 20%.",
        control="Current opening.",
        variant="Question-led opening.",
        primary_metric="reach",
        duration="Four comparable posts",
        decision_rule="Adopt if reach rises 20%.",
    )

    assert "%" not in experiment.hypothesis
    assert "%" not in experiment.decision_rule
    assert "relative to the control" in experiment.hypothesis


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
        growth_thesis="Turn useful topics into a repeatable discovery and retention system.",
        growth_opportunities=[
            GrowthOpportunity(
                objective="Discovery",
                opportunity="Make the promise visible in the opening frame.",
                evidence="Useful topics lead the available results.",
                play="Publish new variants of proven topics with a concrete opening promise.",
                primary_metric="Reach from non-followers",
            ),
            GrowthOpportunity(
                objective="Retention",
                opportunity="Build a clear narrative sequence.",
                evidence="Direct framing already makes the subject easy to understand.",
                play="Use a problem, process, and payoff sequence in each new carousel.",
                primary_metric="Saves per 100 reached",
            ),
            GrowthOpportunity(
                objective="Community",
                opportunity="Invite a specific response tied to the topic.",
                evidence="Practical posts lead the available results.",
                play="End each new post with one answerable question about the viewer's context.",
                primary_metric="Comments per 100 reached",
            ),
        ],
        primary_experiment=ExperimentPlan(
            hypothesis="A concrete opening promise will increase discovery without reducing depth.",
            control="Current descriptive opening frame.",
            variant="A result-led promise in the opening frame.",
            constants=["topic", "format", "publishing window"],
            primary_metric="Reach from non-followers",
            secondary_metrics=["retention", "saves per 100 reached"],
            duration="Six comparable posts",
            decision_rule=(
                "Adopt when the variant wins on reach in four of six posts without lower saves."
            ),
        ),
        production_ideas=[
            ProductionIdea(
                title="The detail most visitors miss",
                format="Short video",
                opening="What does everyone miss in this place?",
                build="Show the landmark, reveal the detail, then explain why it matters.",
                response_prompt="What detail should we investigate next?",
                primary_metric="reach",
            )
        ],
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
