from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from statistics import median

from anton.schemas import MediaItem, PostFinding


def safe_rate(numerator: int | None, denominator: int | None) -> float | None:
    if numerator is None or not denominator:
        return None
    return round(numerator / denominator * 100, 2)


def media_metrics(item: MediaItem) -> tuple[dict, dict]:
    insights = item.insights
    metrics = {
        "views": insights.views if insights else None,
        "reach": insights.reach if insights else None,
        "likes": (insights.likes if insights and insights.likes is not None else item.like_count),
        "comments": (
            insights.comments if insights and insights.comments is not None else item.comments_count
        ),
        "shares": insights.shares if insights else None,
        "saved": insights.saved if insights else None,
        "total_interactions": insights.total_interactions if insights else None,
    }
    interactions = metrics["total_interactions"]
    if interactions is None:
        known = [metrics[key] for key in ("likes", "comments", "shares", "saved")]
        interactions = sum(value for value in known if isinstance(value, int))
        metrics["total_interactions"] = interactions
    rates = {
        "interaction_rate_by_reach": safe_rate(interactions, metrics["reach"]),
        "save_rate_by_reach": safe_rate(metrics["saved"], metrics["reach"]),
        "share_rate_by_reach": safe_rate(metrics["shares"], metrics["reach"]),
        "view_to_reach_ratio": safe_rate(metrics["views"], metrics["reach"]),
    }
    return metrics, rates


def account_metrics(findings: Iterable[PostFinding]) -> dict:
    posts = list(findings)
    by_type = Counter(post.media_type for post in posts)

    def values(metric: str) -> list[float]:
        return [
            float(post.metrics[metric])
            for post in posts
            if isinstance(post.metrics.get(metric), (int, float))
        ]

    def med(metric: str) -> float | None:
        found = values(metric)
        return round(median(found), 2) if found else None

    ranked = sorted(
        posts,
        key=lambda post: (
            post.metrics.get("total_interactions") or 0,
            post.metrics.get("reach") or 0,
        ),
        reverse=True,
    )
    return {
        "analyzed_posts": len(posts),
        "formats": dict(by_type),
        "median_reach": med("reach"),
        "median_views": med("views"),
        "median_interactions": med("total_interactions"),
        "top_media_ids": [post.media_id for post in ranked[:5]],
        "posts_with_reach": len(values("reach")),
        "posts_with_saves": len(values("saved")),
        "posts_with_shares": len(values("shares")),
    }
