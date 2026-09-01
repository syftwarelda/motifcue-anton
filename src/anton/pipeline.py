from __future__ import annotations

import logging
import shutil
from pathlib import Path
from time import perf_counter

from anton.analyzer import ContentAnalyzer, write_snapshot
from anton.backend import BackendClient, InstagramReconnectRequired
from anton.config import Settings
from anton.db import Database, LocalStage
from anton.knowledge import KnowledgeService
from anton.local_data import snapshot_path
from anton.metrics import account_metrics, media_metrics
from anton.report import build_report
from anton.schemas import AccountSynthesis, InstagramDataPage, PostFinding, VisualAnalysis
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

    async def _knowledge_context(self, account, findings: list[PostFinding]) -> list[dict]:
        limit = self.settings.knowledge_context_chunks
        if limit == 0:
            return []
        context = await KnowledgeService(self.db, embedder=self.llm).report_context(
            account, findings, limit
        )
        logger.info("● Approved knowledge context selected · excerpts=%d", len(context))
        return context

    def _snapshot_path(self, order_id: str) -> Path:
        return self.settings.data_directory / "orders" / order_id / "instagram-snapshot.json"

    async def _load_or_collect(self, order_id: str) -> InstagramDataPage:
        path = self._snapshot_path(order_id)
        if path.exists():
            logger.info("✓ Using saved Instagram snapshot · %s", path)
            return InstagramDataPage.model_validate_json(path.read_text(encoding="utf-8"))
        data = await self.backend.collect_instagram_data(
            order_id,
            self.settings.media_page_size,
            self.settings.max_media_items,
            self.settings.data_directory / "orders" / order_id / "endpoint-responses",
        )
        write_snapshot(path, data.model_dump(mode="json"))
        self.db.update_job(order_id, stage=LocalStage.DATA_COLLECTED, snapshot_path=str(path))
        return data

    async def regenerate_local(
        self,
        order_id: str,
        output_path: Path | None = None,
        language: str | None = None,
    ) -> Path:
        """Build a new PDF using only locally persisted order data."""
        path = snapshot_path(self.settings, self.db, order_id)
        if not path.exists():
            raise FileNotFoundError(f"No local Instagram snapshot found for order {order_id}")
        data = InstagramDataPage.model_validate_json(path.read_text(encoding="utf-8"))
        findings = self._local_findings(order_id, data)

        job = self.db.get_job(order_id)
        if job and job.synthesis_json:
            synthesis = AccountSynthesis.model_validate_json(job.synthesis_json)
            logger.info("✓ Using saved account synthesis")
        else:
            logger.info("● No saved synthesis; generating one with the local text model")
            synthesis, _ = await synthesize_account(
                self.llm,
                data.account,
                data.accountInsights,
                findings,
                language or self.settings.report_language,
                await self._knowledge_context(data.account, findings),
            )

        aggregates = account_metrics(findings)
        destination = output_path or self.settings.report_directory / f"{order_id}-local.pdf"
        build_report(
            destination,
            self.settings.report_brand_name,
            language or self.settings.report_language,
            data.account,
            synthesis,
            findings,
            aggregates,
        )
        logger.info("✓ Local PDF rebuilt · %s", destination.resolve())
        return destination

    def _local_findings(self, order_id: str, data: InstagramDataPage) -> list[PostFinding]:
        """Reconstruct findings without network or model calls."""
        findings: list[PostFinding] = []
        cached_count = 0
        image_count = 0
        for item in data.media:
            image_path = (
                self.settings.data_directory / "orders" / order_id / "media" / f"{item.id}.jpg"
            )
            if not image_path.exists():
                image_path = None
            else:
                image_count += 1

            cached = self.db.get_latest_media_result(order_id, item.id)
            if cached:
                visual = VisualAnalysis.model_validate_json(cached)
                cached_count += 1
            else:
                visual = ContentAnalyzer._text_only_analysis(item)
            metrics, rates = media_metrics(item)
            findings.append(
                PostFinding(
                    media_id=item.id,
                    media_type=item.media_type,
                    timestamp=item.timestamp,
                    caption_excerpt=(item.caption or "")[:240] or None,
                    thumbnail_path=str(image_path) if image_path else None,
                    metrics=metrics,
                    rates=rates,
                    visual=visual,
                )
            )

        logger.info(
            "● Rebuilding from local data · order=%s · posts=%d · analyses=%d · images=%d",
            order_id,
            len(findings),
            cached_count,
            image_count,
        )
        return findings

    async def reanalyze_local(
        self,
        order_id: str,
        output_path: Path | None = None,
        language: str | None = None,
        *,
        refresh_images: bool = False,
    ) -> Path:
        """Create a fresh local AI analysis without touching the remote order."""
        path = snapshot_path(self.settings, self.db, order_id)
        if not path.exists():
            raise FileNotFoundError(f"No local Instagram snapshot found for order {order_id}")
        data = InstagramDataPage.model_validate_json(path.read_text(encoding="utf-8"))

        if refresh_images:
            logger.info(
                "● Refreshing saved thumbnails and visual analyses · order=%s · posts=%d",
                order_id,
                len(data.media),
            )
            findings = await self.analyzer.analyze_all(
                order_id,
                data.media,
                force_visual=True,
                refresh_media=True,
            )
        else:
            findings = self._local_findings(order_id, data)

        report_language = language or self.settings.report_language
        logger.info("● Generating a fresh account synthesis · language=%s", report_language)
        synthesis, aggregates = await synthesize_account(
            self.llm,
            data.account,
            data.accountInsights,
            findings,
            report_language,
            await self._knowledge_context(data.account, findings),
        )
        if self.db.get_job(order_id) is None:
            raise LookupError(f"No local job found for order {order_id}")
        self.db.update_job(order_id, synthesis_json=synthesis.model_dump_json())

        destination = output_path or self.settings.report_directory / f"{order_id}-reanalyzed.pdf"
        build_report(
            destination,
            self.settings.report_brand_name,
            report_language,
            data.account,
            synthesis,
            findings,
            aggregates,
        )
        logger.info(
            "✓ Fresh local analysis and PDF completed · order=%s · %s",
            order_id,
            destination.resolve(),
        )
        return destination

    async def process_claim(self, claim) -> None:
        started = perf_counter()
        order = claim.order
        order_id = order.id
        job = self.db.get_or_create_job(order_id, order.status)
        logger.info("╭─ Starting report pipeline · order=%s", order_id)

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
            logger.info("✓ Using saved account synthesis")
            synthesis = AccountSynthesis.model_validate_json(current.synthesis_json)
            aggregates = account_metrics(findings)
        else:
            logger.info("● Finding account-wide patterns with the local text model")
            synthesis, aggregates = await synthesize_account(
                self.llm,
                data.account,
                data.accountInsights,
                findings,
                self.settings.report_language,
                await self._knowledge_context(data.account, findings),
            )
            self.db.update_job(
                order_id,
                stage=LocalStage.SYNTHESIZED,
                synthesis_json=synthesis.model_dump_json(),
            )
            logger.info("✓ Account synthesis completed")

        report_path = self.settings.report_directory / f"{order_id}.pdf"
        logger.info("● Building creator report · language=%s", self.settings.report_language)
        build_report(
            report_path,
            self.settings.report_brand_name,
            self.settings.report_language,
            data.account,
            synthesis,
            findings,
            aggregates,
        )
        logger.info("✓ PDF created · %s", report_path.resolve())
        self.db.update_job(order_id, stage=LocalStage.REPORT_CREATED, report_path=str(report_path))
        report_url = self.storage.publish(order_id, report_path)
        self.db.update_job(order_id, report_url=report_url)
        await self.backend.report_generated(order_id, report_url)
        self.db.update_job(order_id, stage=LocalStage.COMPLETED, backend_status="AWAITING_REVIEW")
        elapsed = perf_counter() - started
        logger.info("╰─ Report pipeline completed · order=%s · %.1f s", order_id, elapsed)

        if self.settings.cleanup_media_after_success:
            media_directory = self.settings.data_directory / "orders" / order_id / "media"
            shutil.rmtree(media_directory, ignore_errors=True)
            logger.debug("Cleaned temporary media · %s", media_directory)
