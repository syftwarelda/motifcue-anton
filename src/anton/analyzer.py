from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from anton.db import Database
from anton.llm import LlamaClient
from anton.media import MediaDownloadError, MediaManager
from anton.metrics import media_metrics
from anton.prompts import VISUAL_SYSTEM_PROMPT, visual_user_prompt
from anton.schemas import MediaItem, PostFinding, VisualAnalysis

logger = logging.getLogger(__name__)


class ContentAnalyzer:
    def __init__(
        self,
        db: Database,
        media: MediaManager,
        llm: LlamaClient,
        concurrency: int,
    ) -> None:
        self.db = db
        self.media = media
        self.llm = llm
        self.semaphore = asyncio.Semaphore(concurrency)

    @staticmethod
    def _text_only_analysis(item: MediaItem) -> VisualAnalysis:
        return VisualAnalysis(
            summary="Visual asset unavailable; analysis uses the post metadata and caption only.",
            content_intent=None,
            topic_tags=[],
            risks=["The representative visual could not be inspected."],
            confidence=0.15,
        )

    async def analyze_one(self, order_id: str, item: MediaItem) -> PostFinding:
        async with self.semaphore:
            logger.debug("→ Preparing media %s · type=%s", item.id, item.media_type)
            image_path: Path | None = None
            try:
                image_path = await self.media.representative_image(order_id, item)
            except MediaDownloadError:
                logger.warning("media_prepare_failed order_id=%s media_id=%s", order_id, item.id)

            fingerprint = self.media.fingerprint(item, image_path)
            cached = self.db.get_media_result(order_id, item.id, fingerprint)
            if cached:
                logger.debug("  Using cached visual analysis · media=%s", item.id)
                visual = VisualAnalysis.model_validate_json(cached)
            elif image_path:
                logger.debug(
                    "  Sending representative image to local vision model · media=%s", item.id
                )
                visual = await self.llm.analyze_image(
                    image_path,
                    VISUAL_SYSTEM_PROMPT,
                    visual_user_prompt(item.media_type, item.caption),
                    VisualAnalysis,
                )
                self.db.save_media_result(order_id, item.id, fingerprint, visual.model_dump_json())
            else:
                logger.debug("  Falling back to metadata-only analysis · media=%s", item.id)
                visual = self._text_only_analysis(item)
                self.db.save_media_result(order_id, item.id, fingerprint, visual.model_dump_json())

            metrics, rates = media_metrics(item)
            return PostFinding(
                media_id=item.id,
                media_type=item.media_type,
                timestamp=item.timestamp,
                caption_excerpt=(item.caption or "")[:240] or None,
                thumbnail_path=str(image_path) if image_path else None,
                metrics=metrics,
                rates=rates,
                visual=visual,
            )

    async def analyze_all(self, order_id: str, items: list[MediaItem]) -> list[PostFinding]:
        logger.info("● Analyzing media with the local vision model · total=%d", len(items))
        tasks = [asyncio.create_task(self.analyze_one(order_id, item)) for item in items]
        results: list[PostFinding] = []
        for completed in asyncio.as_completed(tasks):
            results.append(await completed)
            logger.info(
                "  Visual analysis %d/%d · %d%%",
                len(results),
                len(items),
                round((len(results) / len(items)) * 100) if items else 100,
            )
        logger.info("✓ Visual analysis completed · total=%d", len(results))
        return sorted(results, key=lambda finding: finding.timestamp, reverse=True)


def compact_finding(finding: PostFinding) -> dict:
    data = finding.model_dump(mode="json")
    data.pop("thumbnail_path", None)
    return data


def write_snapshot(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
