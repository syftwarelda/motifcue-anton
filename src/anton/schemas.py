from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class InstagramConnection(BaseModel):
    id: str
    username: str
    connectedAt: datetime | None = None
    tokenExpiresAt: datetime | None = None
    revokedAt: datetime | None = None


class OrderUser(BaseModel):
    id: str
    name: str | None = None
    email: str | None = None
    igHandle: str | None = None
    instagramConnection: InstagramConnection | None = None


class ClaimedOrder(BaseModel):
    id: str
    status: str
    createdAt: datetime
    processingStartedAt: datetime | None = None
    user: OrderUser


class ClaimResponse(BaseModel):
    order: ClaimedOrder
    resumed: bool = False


class Account(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    username: str
    followers_count: int | None = None
    follows_count: int | None = None
    media_count: int | None = None
    name: str | None = None
    biography: str | None = None


class InsightValue(BaseModel):
    model_config = ConfigDict(extra="allow")

    value: int | float | dict[str, Any] | None = None
    end_time: datetime | None = None


class AccountInsight(BaseModel):
    model_config = ConfigDict(extra="allow")

    name: str
    period: str | None = None
    values: list[InsightValue] = Field(default_factory=list)


class MediaInsights(BaseModel):
    model_config = ConfigDict(extra="allow")

    views: int | None = None
    reach: int | None = None
    likes: int | None = None
    comments: int | None = None
    shares: int | None = None
    saved: int | None = None
    total_interactions: int | None = None


class MediaItem(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    caption: str | None = None
    media_type: str
    media_url: str | None = None
    thumbnail_url: str | None = None
    permalink: str | None = None
    timestamp: datetime
    like_count: int | None = None
    comments_count: int | None = None
    insights: MediaInsights | None = None
    insightsError: str | None = None
    children: list[MediaItem] = Field(default_factory=list)


class Paging(BaseModel):
    nextCursor: str | None = None
    hasNextPage: bool = False


class InstagramDataPage(BaseModel):
    orderId: str
    account: Account
    accountInsights: list[AccountInsight] = Field(default_factory=list)
    accountInsightsRange: dict[str, Any] | None = None
    media: list[MediaItem] = Field(default_factory=list)
    paging: Paging


class VisualAnalysis(BaseModel):
    summary: str
    subjects: list[str] = Field(default_factory=list)
    setting: str | None = None
    composition: str | None = None
    visible_text: list[str] = Field(default_factory=list)
    human_presence: bool = False
    opening_frame_clarity: Literal["low", "medium", "high"] = "medium"
    hook_type: str | None = None
    content_intent: str | None = None
    emotional_tone: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    topic_tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)


class PostFinding(BaseModel):
    media_id: str
    media_type: str
    timestamp: datetime
    caption_excerpt: str | None = None
    thumbnail_path: str | None = None
    metrics: dict[str, float | int | None]
    rates: dict[str, float | None]
    visual: VisualAnalysis


class AccountSynthesis(BaseModel):
    account_positioning: str
    executive_summary: list[str] = Field(min_length=3, max_length=5)
    audience_response_patterns: list[str] = Field(default_factory=list)
    content_pillars: list[str] = Field(default_factory=list)
    format_patterns: list[str] = Field(default_factory=list)
    visual_identity: list[str] = Field(default_factory=list)
    keep: list[str] = Field(default_factory=list)
    change: list[str] = Field(default_factory=list)
    tests: list[str] = Field(default_factory=list)
    thirty_day_plan: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
