from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta

from anton.analyzer import compact_finding
from anton.llm import LlamaClient
from anton.metrics import account_metrics
from anton.prompts import SYNTHESIS_SYSTEM_PROMPT, synthesis_user_prompt
from anton.schemas import Account, AccountInsight, AccountSynthesis, PostFinding

_WORD_PATTERN = re.compile(r"[a-zA-ZÀ-ÖØ-öø-ÿ0-9][\wÀ-ÖØ-öø-ÿ-]{2,}", re.UNICODE)
_EVIDENCE_STOPWORDS = {
    "and",
    "are",
    "for",
    "from",
    "into",
    "that",
    "the",
    "this",
    "with",
    "your",
    "para",
    "por",
    "que",
    "una",
}


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


def _tokens(value: str) -> set[str]:
    return {
        token.lower()
        for token in _WORD_PATTERN.findall(value)
        if token.lower() not in _EVIDENCE_STOPWORDS
    }


def _finding_supports_metric(finding: PostFinding, metric: str) -> bool:
    label = metric.lower()
    candidates = {
        "save": ("saved",),
        "share": ("shares",),
        "comment": ("comments",),
        "reach": ("reach",),
        "interaction": ("total_interactions", "interaction_rate_by_reach"),
        "view": ("views",),
    }
    for token, keys in candidates.items():
        if token in label:
            return any(
                finding.metrics.get(key) is not None or finding.rates.get(key) is not None
                for key in keys
            )
    return False


def _attach_evidence_metadata(
    synthesis: AccountSynthesis,
    findings: list[PostFinding],
    knowledge_context: list[dict] | None,
) -> None:
    if not findings:
        return
    latest_captured = max(finding.timestamp for finding in findings)
    valid_ids = {finding.media_id for finding in findings}
    for opportunity in synthesis.growth_opportunities:
        opportunity_tokens = _tokens(
            " ".join(
                [
                    opportunity.objective,
                    opportunity.opportunity,
                    opportunity.evidence,
                    opportunity.play,
                ]
            )
        )
        scored = []
        for finding in findings:
            haystack = " ".join(
                [
                    finding.caption_excerpt or "",
                    finding.visual.summary,
                    " ".join(finding.visual.topic_tags),
                    finding.visual.content_intent or "",
                    finding.media_type,
                ]
            )
            overlap = len(opportunity_tokens & _tokens(haystack))
            age_in_collection = max(0, (latest_captured - finding.timestamp).days)
            recency = 2 if age_in_collection <= 180 else 1 if age_in_collection <= 365 else 0
            metric_support = int(_finding_supports_metric(finding, opportunity.primary_metric))
            interactions = int(finding.metrics.get("total_interactions") or 0)
            scored.append(
                (
                    recency,
                    overlap,
                    metric_support,
                    interactions,
                    finding.timestamp,
                    finding.media_id,
                )
            )
        scored.sort(reverse=True)
        supplied_ids = [
            media_id for media_id in opportunity.evidence_media_ids if media_id in valid_ids
        ]
        selected_ids = list(dict.fromkeys(supplied_ids + [row[-1] for row in scored]))[:2]
        opportunity.evidence_media_ids = selected_ids

        selected = [finding for finding in findings if finding.media_id in selected_ids]
        newest_evidence = max((finding.timestamp for finding in selected), default=latest_captured)
        age_days = (datetime.now(UTC) - newest_evidence).days
        metric_coverage = sum(
            _finding_supports_metric(finding, opportunity.primary_metric) for finding in findings
        ) / len(findings)
        if len(selected) >= 2 and age_days <= 180 and metric_coverage >= 0.5:
            opportunity.confidence = "high"
        elif len(selected) >= 2 and age_days <= 365 and metric_coverage >= 0.25:
            opportunity.confidence = "medium"
        else:
            opportunity.confidence = "low"

        if knowledge_context:
            objective = opportunity.objective.lower()
            preferred_contexts = (
                {"experimentation", "organic"}
                if "discovery" in objective
                else {"measurement"}
                if "retention" in objective
                else {"community"}
            )
            sources = sorted(
                knowledge_context,
                key=lambda source: (
                    source.get("context") in preferred_contexts,
                    len(
                        opportunity_tokens
                        & _tokens(f"{source.get('title', '')} {source.get('guidance', '')}")
                    ),
                ),
                reverse=True,
            )
            opportunity.reference_sources = [
                source["title"]
                for source in sources
                if source.get("title")
                and (
                    source.get("context") in preferred_contexts
                    or opportunity_tokens & _tokens(source.get("guidance", ""))
                )
            ][:1]


def normalize_strategy_metrics(
    synthesis: AccountSynthesis,
    account_insights: list[AccountInsight],
    findings: list[PostFinding],
    knowledge_context: list[dict] | None = None,
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
    _attach_evidence_metadata(synthesis, findings, knowledge_context)
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
    latest_captured = max((finding.timestamp for finding in findings), default=datetime.now(UTC))
    recent_cutoff = latest_captured - timedelta(days=180)
    recent_findings = sorted(
        (finding for finding in findings if finding.timestamp >= recent_cutoff),
        key=lambda finding: finding.timestamp,
        reverse=True,
    )[:30]
    recent_ids = {finding.media_id for finding in recent_findings}
    historical_findings = sorted(
        (finding for finding in findings if finding.media_id not in recent_ids),
        key=lambda finding: (
            finding.metrics.get("total_interactions") or 0,
            finding.metrics.get("reach") or 0,
        ),
        reverse=True,
    )[:6]

    # Every post contributes compact evidence. Strong posts retain more detail.
    payload = {
        "account": account.model_dump(mode="json", exclude_none=True),
        "account_insights": [item.model_dump(mode="json") for item in account_insights],
        "aggregates": aggregates,
        "evidence_scope": {
            "recent_window": "180 days ending at the newest captured post",
            "recent_post_count": len(recent_findings),
            "historical_reference_count": len(historical_findings),
        },
        "recent_posts": [compact_finding(item) for item in recent_findings],
        "historical_reference_posts": [compact_finding(item) for item in historical_findings],
        "approved_reference_knowledge": knowledge_context or [],
    }
    synthesis = await llm.synthesize(
        SYNTHESIS_SYSTEM_PROMPT,
        synthesis_user_prompt(json.dumps(payload, ensure_ascii=False), language),
        AccountSynthesis,
    )
    synthesis = normalize_strategy_metrics(synthesis, account_insights, findings, knowledge_context)
    return synthesis, aggregates
