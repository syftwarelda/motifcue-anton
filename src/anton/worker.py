from __future__ import annotations

import asyncio
import logging

from anton.analyzer import ContentAnalyzer
from anton.backend import BackendClient, NoWorkAvailable
from anton.config import Settings
from anton.db import Database
from anton.llm import LlamaClient
from anton.media import MediaManager
from anton.pipeline import Pipeline
from anton.storage import ReportStorage

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, settings: Settings, db: Database) -> None:
        self.settings = settings
        self.db = db
        self.backend = BackendClient(
            str(settings.motifcue_api_base_url),
            settings.anton_internal_api_key.get_secret_value(),
            settings.request_timeout_seconds,
            (
                settings.vercel_automation_bypass_secret.get_secret_value()
                if settings.vercel_automation_bypass_secret
                else None
            ),
        )
        self.llm = LlamaClient(
            str(settings.llm_base_url),
            settings.llm_api_key.get_secret_value(),
            settings.llm_text_model,
            settings.llm_vision_model,
            settings.llm_timeout_seconds,
            settings.llm_max_retries,
        )
        self.media = MediaManager(
            settings.data_directory,
            settings.max_media_bytes,
            settings.request_timeout_seconds,
        )
        self.pipeline = Pipeline(
            settings,
            db,
            self.backend,
            ContentAnalyzer(db, self.media, self.llm, settings.media_analysis_concurrency),
            ReportStorage(settings),
            self.llm,
        )

    async def close(self) -> None:
        await self.backend.close()
        await self.llm.close()
        await self.media.close()

    async def once(self) -> bool:
        try:
            claim = await self.backend.claim()
        except NoWorkAvailable:
            logger.info("○ No orders are waiting")
            return False
        except Exception:
            logger.exception("✗ Could not claim an order from MotifCue")
            raise
        try:
            await self.pipeline.process_claim(claim)
        except Exception:
            # Do not fail a paid order when Anton or local infrastructure is temporarily down.
            # The active backend order remains resumable; checkpoints avoid duplicate work.
            logger.exception("✗ Report pipeline interrupted · order=%s", claim.order.id)
            self.db.update_job(claim.order.id, last_error="LOCAL_PIPELINE_ERROR")
            raise
        return True

    async def run_forever(self) -> None:
        logger.info("Anton is online")
        logger.info(
            "Configuration · poll=%.0fs · media=%d · concurrency=%d · storage=%s",
            self.settings.poll_interval_seconds,
            self.settings.max_media_items,
            self.settings.media_analysis_concurrency,
            self.settings.report_storage_driver,
        )
        logger.info(
            "Models · text=%s · vision=%s",
            self.settings.llm_text_model,
            self.settings.llm_vision_model,
        )
        try:
            while True:
                try:
                    worked = await self.once()
                except Exception:
                    worked = True
                    await asyncio.sleep(min(60, self.settings.poll_interval_seconds * 2))
                if not worked:
                    await asyncio.sleep(self.settings.poll_interval_seconds)
        finally:
            await self.close()
