from __future__ import annotations

import json
import re

from anton.analyzer import compact_finding
from anton.llm import LlamaClient
from anton.metrics import account_metrics
from anton.prompts import SYNTHESIS_SYSTEM_PROMPT, synthesis_user_prompt
from anton.schemas import Account, AccountInsight, AccountSynthesis, PostFinding


def _available_metrics(
    account_insights: list[AccountInsight], findings: list[PostFinding]
) -> set[str]:
    available = {
        key.lower()
        for finding in findings
        for key, value in {**finding.metrics, **finding.rates}.items()
        if value is not None
    }
    available.update(insight.name.lower() for insight in account_insights)
    return available


def _metric_is_available(metric: str, available: set[str]) -> bool:
    label = metric.lower()
    checks = {
        "non-follower": ("non_follower", "non-follower"),
        "follow": ("follow",),
        "profile visit": ("profile_visit", "profile visit"),
        "watch": ("watch",),
        "retention": ("retention",),
        "replay": ("replay",),
        "save": ("saved", "save"),
        "share": ("shares", "share"),
        "comment": ("comments", "comment"),
        "reach": ("reach",),
        "interaction": ("total_interactions", "interaction_rate_by_reach"),
        "view": ("views",),
    }
    matched = False
    for token, required in checks.items():
        if token not in label:
            continue
        matched = True
        if not any(any(value in item for value in required) for item in available):
            return False
    return matched


def _fallback_metric(objective: str, available: set[str]) -> str:
    objective = objective.lower()
    if "retention" in objective and "saved" in available and "reach" in available:
        return "saves per 100 reached"
    if (
        any(token in objective for token in ("community", "conversion"))
        and "comments" in available
        and "reach" in available
    ):
        return "comments per 100 reached"
    if "reach" in available:
        return "reach"
    if "total_interactions" in available:
        return "total interactions"
    return "posts completed"


def _replace_metric_terms(value: str, replacements: dict[str, str]) -> str:
    for source, target in replacements.items():
        value = re.sub(re.escape(source), target, value, flags=re.IGNORECASE)
    return value


def _canonical_metric_name(metric: str) -> str:
    label = metric.lower()
    for token, name in (
        ("save", "saves"),
        ("share", "shares"),
        ("comment", "comments"),
        ("reach", "reach"),
        ("interaction", "total interactions"),
        ("view", "views"),
    ):
        if token in label:
            return name
    return metric


def normalize_strategy_metrics(
    synthesis: AccountSynthesis,
    account_insights: list[AccountInsight],
    findings: list[PostFinding],
) -> AccountSynthesis:
    available = _available_metrics(account_insights, findings)
    replacements: dict[str, str] = {}
    if not any("non_follower" in item or "non-follower" in item for item in available):
        replacements["non-follower reach"] = _fallback_metric("discovery", available)
    if not any("follow" in item for item in available):
        replacements["follows from post"] = _fallback_metric("conversion", available)

    synthesis.growth_thesis = (
        _replace_metric_terms(synthesis.growth_thesis, replacements)
        if synthesis.growth_thesis
        else None
    )
    for field in (
        "executive_summary",
        "audience_response_patterns",
        "format_patterns",
        "keep",
        "change",
        "tests",
        "thirty_day_plan",
        "limitations",
    ):
        setattr(
            synthesis,
            field,
            [_replace_metric_terms(item, replacements) for item in getattr(synthesis, field)],
        )
    for opportunity in synthesis.growth_opportunities:
        opportunity.opportunity = _replace_metric_terms(opportunity.opportunity, replacements)
        opportunity.evidence = _replace_metric_terms(opportunity.evidence, replacements)
        opportunity.play = _replace_metric_terms(opportunity.play, replacements)
        if not _metric_is_available(opportunity.primary_metric, available):
            opportunity.primary_metric = _fallback_metric(opportunity.objective, available)
        lowered_play = opportunity.play.lower()
        if "invite" in lowered_play and "follow" in lowered_play:
            opportunity.play = (
                "Reply with a useful, specific answer and use recurring questions to shape the "
                "next original post."
            )
    synthesis.thirty_day_plan = [
        item.replace(
            "and a follow invitation",
            "and note recurring questions for the next original post",
        )
        for item in synthesis.thirty_day_plan
    ]
    experiment = synthesis.primary_experiment
    if experiment:
        experiment.hypothesis = _replace_metric_terms(experiment.hypothesis, replacements)
        experiment.control = _replace_metric_terms(experiment.control, replacements)
        experiment.variant = _replace_metric_terms(experiment.variant, replacements)
        experiment.constants = [
            _replace_metric_terms(item, replacements) for item in experiment.constants
        ]
        experiment.decision_rule = _replace_metric_terms(experiment.decision_rule, replacements)
    if experiment and not _metric_is_available(experiment.primary_metric, available):
        replacement = _fallback_metric("discovery", available)
        experiment.primary_metric = replacement
        experiment.hypothesis = (
            f"If the variant is used, {replacement} will improve relative to the control."
        )
        experiment.decision_rule = (
            f"Adopt if the variant wins on {replacement} in most comparable posts without "
            "weakening secondary metrics; iterate if results are mixed; stop if it performs lower."
        )
    if experiment:
        experiment.secondary_metrics = [
            _canonical_metric_name(metric)
            for metric in experiment.secondary_metrics
            if _metric_is_available(metric, available)
        ][:3]
        metric = experiment.primary_metric.rstrip(".")
        experiment.decision_rule = (
            f"Adopt if the variant wins on {metric} in most comparable posts without weakening "
            "secondary metrics; iterate if results are mixed; stop if it performs lower."
        )
    for idea in synthesis.production_ideas:
        idea.title = _replace_metric_terms(idea.title, replacements)
        idea.opening = _replace_metric_terms(idea.opening, replacements)
        idea.build = _replace_metric_terms(idea.build, replacements)
        idea.response_prompt = _replace_metric_terms(idea.response_prompt, replacements)
        if not _metric_is_available(idea.primary_metric, available):
            idea.primary_metric = _fallback_metric(idea.format, available)
    return synthesis


async def synthesize_account(
    llm: LlamaClient,
    account: Account,
    account_insights: list[AccountInsight],
    findings: list[PostFinding],
    language: str,
    knowledge_context: list[dict] | None = None,
) -> tuple[AccountSynthesis, dict]:
    aggregates = account_metrics(findings)
    top_ids = set(aggregates["top_media_ids"])
    top_findings = [finding for finding in findings if finding.media_id in top_ids]
    other_findings = [finding for finding in findings if finding.media_id not in top_ids]

    # Every post contributes compact evidence. Strong posts retain more detail.
    payload = {
        "account": account.model_dump(mode="json", exclude_none=True),
        "account_insights": [item.model_dump(mode="json") for item in account_insights],
        "aggregates": aggregates,
        "top_posts": [compact_finding(item) for item in top_findings],
        "remaining_posts": [
            {
                "media_id": item.media_id,
                "media_type": item.media_type,
                "timestamp": item.timestamp.isoformat(),
                "metrics": item.metrics,
                "rates": item.rates,
                "summary": item.visual.summary,
                "topic_tags": item.visual.topic_tags,
                "strengths": item.visual.strengths,
                "risks": item.visual.risks,
            }
            for item in other_findings
        ],
        "approved_reference_knowledge": knowledge_context or [],
    }
    synthesis = await llm.synthesize(
        SYNTHESIS_SYSTEM_PROMPT,
        synthesis_user_prompt(json.dumps(payload, ensure_ascii=False), language),
        AccountSynthesis,
    )
    synthesis = normalize_strategy_metrics(synthesis, account_insights, findings)
    return synthesis, aggregates
