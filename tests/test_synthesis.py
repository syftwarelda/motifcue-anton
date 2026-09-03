from datetime import UTC, datetime

from anton.schemas import (
    AccountSynthesis,
    ExperimentPlan,
    GrowthOpportunity,
    PostFinding,
    ProductionIdea,
    VisualAnalysis,
)
from anton.synthesis import normalize_strategy_metrics


def test_strategy_uses_only_available_metrics_and_removes_follow_ask() -> None:
    synthesis = AccountSynthesis(
        account_positioning="A practical travel account.",
        executive_summary=["One.", "Two.", "Three."],
        growth_opportunities=[
            GrowthOpportunity(
                objective="conversion",
                opportunity="Turn questions into a useful community loop.",
                evidence="Comments are available.",
                play="Reply with a tip and invite followers to the next post.",
                primary_metric="follows from post",
            )
        ],
        primary_experiment=ExperimentPlan(
            hypothesis="A question hook will increase non-follower reach.",
            control="Current opening.",
            variant="Question-led opening.",
            primary_metric="non-follower reach",
            secondary_metrics=["average watch time", "saves"],
            duration="Four comparable posts",
            decision_rule="Adopt when comments are 3 higher.",
        ),
        production_ideas=[
            ProductionIdea(
                title="A useful idea",
                format="video",
                opening="What would you choose?",
                build="Show two options and explain the tradeoff.",
                response_prompt="Which option fits you?",
                primary_metric="profile visits",
            )
        ],
        thirty_day_plan=["Reply with a local tip and a follow invitation."],
    )
    finding = PostFinding(
        media_id="one",
        media_type="VIDEO",
        timestamp=datetime.now(UTC),
        metrics={"reach": 100, "comments": 4, "saved": 3},
        rates={"interaction_rate_by_reach": 7.0},
        visual=VisualAnalysis(summary="A clear travel scene."),
    )

    normalized = normalize_strategy_metrics(
        synthesis,
        [],
        [finding],
        [
            {
                "title": "Official community guidance",
                "context": "community",
                "guidance": "Use specific questions to create useful comment conversations.",
            }
        ],
    )

    assert normalized.growth_opportunities[0].primary_metric == "comments per 100 reached"
    assert "follow" not in normalized.growth_opportunities[0].play.lower()
    assert normalized.primary_experiment.primary_metric == "reach"
    assert "non-follower" not in normalized.primary_experiment.hypothesis.lower()
    assert normalized.primary_experiment.secondary_metrics == ["saves"]
    assert "3 higher" not in normalized.primary_experiment.decision_rule
    assert normalized.production_ideas[0].primary_metric == "reach"
    assert "follow invitation" not in normalized.thirty_day_plan[0]
    assert normalized.growth_opportunities[0].evidence_media_ids == ["one"]
    assert normalized.growth_opportunities[0].confidence == "low"
    assert normalized.growth_opportunities[0].reference_sources == ["Official community guidance"]
