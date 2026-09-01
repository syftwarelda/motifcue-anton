from __future__ import annotations

import logging
import shutil
from pathlib import Path

from anton.analyzer import ContentAnalyzer, write_snapshot
from anton.backend import BackendClient, InstagramReconnectRequired
from anton.config import Settings
from anton.db import Database, LocalStage
from anton.report import build_report
from anton.schemas import AccountSynthesis, InstagramDataPage
from anton.storage import ReportStorage
from anton.synthesis import synthesize_account

logger = logging.getLogger(__name__)


class Pipeline:
    def __init__(
        self,
        settings: Settings,
        db: Database,
        backend: BackendClient,
        analyzer: ContentAnalyzer,
        storage: ReportStorage,
        llm,
    ) -> None:
        self.settings = settings
        self.db = db
        self.backend = backend
        self.analyzer = analyzer
        self.storage = storage
        self.llm = llm

    def _snapshot_path(self, order_id: str) -> Path:
        return self.settings.data_directory / "orders" / order_id / "instagram-snapshot.json"

    async def _load_or_collect(self, order_id: str) -> InstagramDataPage:
        path = self._snapshot_path(order_id)
        if path.exists():
            return InstagramDataPage.model_validate_json(path.read_text(encoding="utf-8"))
        data = await self.backend.collect_instagram_data(
            order_id, self.settings.media_page_size, self.settings.max_media_items
        )
        write_snapshot(path, data.model_dump(mode="json"))
        self.db.update_job(order_id, stage=LocalStage.DATA_COLLECTED, snapshot_path=str(path))
        return data

    async def process_claim(self, claim) -> None:
        order = claim.order
        order_id = order.id
        job = self.db.get_or_create_job(order_id, order.status)
        logger.info("job_started order_id=%s resumed=%s", order_id, claim.resumed)

        if job.report_url:
            await self.backend.report_generated(order_id, job.report_url)
            self.db.update_job(order_id, stage=LocalStage.COMPLETED)
            return

        if order.status == "VALIDATING":
            try:
                await self.backend.validate_instagram(order_id)
            except InstagramReconnectRequired:
                self.db.update_job(
                    order_id,
                    stage=LocalStage.NEEDS_RECONNECT,
                    backend_status="NEEDS_RECONNECT",
                )
                logger.info("instagram_reconnect_required order_id=%s", order_id)
                return
            self.db.update_job(
                order_id, stage=LocalStage.VALIDATED, backend_status="GENERATING_REPORT"
            )
        elif order.status != "GENERATING_REPORT":
            raise RuntimeError(f"Unsupported claimed order state: {order.status}")

        data = await self._load_or_collect(order_id)
        self.db.update_job(order_id, stage=LocalStage.ANALYZING)
        findings = await self.analyzer.analyze_all(order_id, data.media)

        current = self.db.get_job(order_id)
        if current and current.synthesis_json:
            synthesis = AccountSynthesis.model_validate_json(current.synthesis_json)
            from anton.metrics import account_metrics

            aggregates = account_metrics(findings)
        else:
            synthesis, aggregates = await synthesize_account(
                self.llm,
                data.account,
                data.accountInsights,
                findings,
                self.settings.report_language,
            )
            self.db.update_job(
                order_id,
                stage=LocalStage.SYNTHESIZED,
                synthesis_json=synthesis.model_dump_json(),
            )

        report_path = self.settings.report_directory / f"{order_id}.pdf"
        build_report(
            report_path,
            self.settings.report_brand_name,
            self.settings.report_language,
            data.account,
            synthesis,
            findings,
            aggregates,
        )
        self.db.update_job(order_id, stage=LocalStage.REPORT_CREATED, report_path=str(report_path))
        report_url = self.storage.publish(order_id, report_path)
        self.db.update_job(order_id, report_url=report_url)
        await self.backend.report_generated(order_id, report_url)
        self.db.update_job(order_id, stage=LocalStage.COMPLETED, backend_status="AWAITING_REVIEW")
        logger.info("job_completed order_id=%s", order_id)

        if self.settings.cleanup_media_after_success:
            media_directory = self.settings.data_directory / "orders" / order_id / "media"
            shutil.rmtree(media_directory, ignore_errors=True)
