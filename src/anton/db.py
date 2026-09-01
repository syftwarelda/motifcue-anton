from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


def utcnow() -> datetime:
    return datetime.now(UTC)


class LocalStage(StrEnum):
    CLAIMED = "CLAIMED"
    VALIDATED = "VALIDATED"
    DATA_COLLECTED = "DATA_COLLECTED"
    ANALYZING = "ANALYZING"
    SYNTHESIZED = "SYNTHESIZED"
    REPORT_CREATED = "REPORT_CREATED"
    COMPLETED = "COMPLETED"
    NEEDS_RECONNECT = "NEEDS_RECONNECT"
    FAILED = "FAILED"


class Base(DeclarativeBase):
    pass


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    stage: Mapped[str] = mapped_column(String(32), default=LocalStage.CLAIMED)
    backend_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    snapshot_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    synthesis_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    report_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class MediaAnalysisRecord(Base):
    __tablename__ = "media_analyses"
    __table_args__ = (UniqueConstraint("order_id", "media_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[str] = mapped_column(String(128), index=True)
    media_id: Mapped[str] = mapped_column(String(128))
    fingerprint: Mapped[str] = mapped_column(String(64))
    result_json: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class Database:
    def __init__(self, url: str) -> None:
        connect_args: dict[str, Any] = (
            {"check_same_thread": False} if url.startswith("sqlite") else {}
        )
        self.engine = create_engine(url, connect_args=connect_args)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def get_or_create_job(self, order_id: str, backend_status: str) -> Job:
        with self.sessions.begin() as session:
            job = session.scalar(select(Job).where(Job.order_id == order_id))
            if job is None:
                job = Job(order_id=order_id, backend_status=backend_status)
                session.add(job)
            else:
                job.backend_status = backend_status
                job.attempts += 1
            session.flush()
            return job

    def get_job(self, order_id: str) -> Job | None:
        with self.sessions() as session:
            return session.scalar(select(Job).where(Job.order_id == order_id))

    def update_job(self, order_id: str, **values: Any) -> Job:
        with self.sessions.begin() as session:
            job = session.scalar(select(Job).where(Job.order_id == order_id))
            if job is None:
                raise LookupError(f"Unknown order {order_id}")
            for key, value in values.items():
                setattr(job, key, value)
            job.updated_at = utcnow()
            session.flush()
            return job

    def get_media_result(self, order_id: str, media_id: str, fingerprint: str) -> str | None:
        with self.sessions() as session:
            row = session.scalar(
                select(MediaAnalysisRecord).where(
                    MediaAnalysisRecord.order_id == order_id,
                    MediaAnalysisRecord.media_id == media_id,
                    MediaAnalysisRecord.fingerprint == fingerprint,
                )
            )
            return row.result_json if row else None

    def get_latest_media_result(self, order_id: str, media_id: str) -> str | None:
        """Return the saved analysis without requiring the original media fingerprint."""
        with self.sessions() as session:
            row = session.scalar(
                select(MediaAnalysisRecord).where(
                    MediaAnalysisRecord.order_id == order_id,
                    MediaAnalysisRecord.media_id == media_id,
                )
            )
            return row.result_json if row else None

    def media_results(self, order_id: str) -> list[MediaAnalysisRecord]:
        with self.sessions() as session:
            return list(
                session.scalars(
                    select(MediaAnalysisRecord)
                    .where(MediaAnalysisRecord.order_id == order_id)
                    .order_by(MediaAnalysisRecord.media_id)
                )
            )

    def save_media_result(
        self, order_id: str, media_id: str, fingerprint: str, result_json: str
    ) -> None:
        with self.sessions.begin() as session:
            row = session.scalar(
                select(MediaAnalysisRecord).where(
                    MediaAnalysisRecord.order_id == order_id,
                    MediaAnalysisRecord.media_id == media_id,
                )
            )
            if row is None:
                session.add(
                    MediaAnalysisRecord(
                        order_id=order_id,
                        media_id=media_id,
                        fingerprint=fingerprint,
                        result_json=result_json,
                    )
                )
            else:
                row.fingerprint = fingerprint
                row.result_json = result_json
                row.updated_at = utcnow()

    def recent_jobs(self, limit: int = 20) -> list[Job]:
        with self.sessions() as session:
            return list(session.scalars(select(Job).order_by(Job.updated_at.desc()).limit(limit)))
