from __future__ import annotations

import json

from anton.analyzer import compact_finding
from anton.llm import LlamaClient
from anton.metrics import account_metrics
from anton.prompts import SYNTHESIS_SYSTEM_PROMPT, synthesis_user_prompt
from anton.schemas import Account, AccountInsight, AccountSynthesis, PostFinding


async def synthesize_account(
    llm: LlamaClient,
    account: Account,
    account_insights: list[AccountInsight],
    findings: list[PostFinding],
    language: str,
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
    }
    synthesis = await llm.synthesize(
        SYNTHESIS_SYSTEM_PROMPT,
        synthesis_user_prompt(json.dumps(payload, ensure_ascii=False), language),
        AccountSynthesis,
    )
    return synthesis, aggregates
