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


class KnowledgeSourceRecord(Base):
    __tablename__ = "knowledge_sources"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str] = mapped_column(Text, unique=True)
    source_type: Mapped[str] = mapped_column(String(64))
    context: Mapped[str] = mapped_column(String(64), default="general")
    tags_json: Mapped[str] = mapped_column(Text, default="[]")
    status: Mapped[str] = mapped_column(String(32), default="approved")
    refresh_days: Mapped[int] = mapped_column(Integer, default=7)
    active_revision_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeRevisionRecord(Base):
    __tablename__ = "knowledge_revisions"
    __table_args__ = (UniqueConstraint("source_id", "content_hash"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[str] = mapped_column(String(128), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    content: Mapped[str] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(32), default="pending")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class KnowledgeChunkRecord(Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (UniqueConstraint("revision_id", "chunk_index"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    revision_id: Mapped[int] = mapped_column(Integer, index=True)
    source_id: Mapped[str] = mapped_column(String(128), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(128), nullable=True)


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

    def upsert_knowledge_source(self, **values: Any) -> KnowledgeSourceRecord:
        with self.sessions.begin() as session:
            row = session.get(KnowledgeSourceRecord, values["id"])
            if row is None:
                row = KnowledgeSourceRecord(**values)
                session.add(row)
            else:
                for key, value in values.items():
                    if key != "id":
                        setattr(row, key, value)
                row.updated_at = utcnow()
            session.flush()
            return row

    def knowledge_source(self, source_id: str) -> KnowledgeSourceRecord | None:
        with self.sessions() as session:
            return session.get(KnowledgeSourceRecord, source_id)

    def knowledge_sources(self) -> list[KnowledgeSourceRecord]:
        with self.sessions() as session:
            return list(
                session.scalars(select(KnowledgeSourceRecord).order_by(KnowledgeSourceRecord.id))
            )

    def knowledge_revision_by_hash(
        self, source_id: str, content_hash: str
    ) -> KnowledgeRevisionRecord | None:
        with self.sessions() as session:
            return session.scalar(
                select(KnowledgeRevisionRecord).where(
                    KnowledgeRevisionRecord.source_id == source_id,
                    KnowledgeRevisionRecord.content_hash == content_hash,
                )
            )

    def save_knowledge_revision(
        self,
        source_id: str,
        content_hash: str,
        content: str,
        *,
        activate: bool,
        chunks: list[str],
    ) -> KnowledgeRevisionRecord:
        now = utcnow()
        with self.sessions.begin() as session:
            source = session.get(KnowledgeSourceRecord, source_id)
            if source is None:
                raise LookupError(f"Unknown knowledge source {source_id}")
            revision = KnowledgeRevisionRecord(
                source_id=source_id,
                content_hash=content_hash,
                content=content,
                review_status="approved" if activate else "pending",
                fetched_at=now,
            )
            session.add(revision)
            session.flush()
            for index, chunk in enumerate(chunks):
                session.add(
                    KnowledgeChunkRecord(
                        revision_id=revision.id,
                        source_id=source_id,
                        chunk_index=index,
                        content=chunk,
                    )
                )
            if activate:
                source.active_revision_id = revision.id
            source.last_checked_at = now
            source.last_changed_at = now
            source.last_error = None
            source.updated_at = now
            session.flush()
            return revision

    def mark_knowledge_checked(self, source_id: str) -> None:
        with self.sessions.begin() as session:
            source = session.get(KnowledgeSourceRecord, source_id)
            if source:
                source.last_checked_at = utcnow()
                source.last_error = None

    def mark_knowledge_error(self, source_id: str, error_code: str) -> None:
        with self.sessions.begin() as session:
            source = session.get(KnowledgeSourceRecord, source_id)
            if source:
                source.last_checked_at = utcnow()
                source.last_error = error_code[:128]

    def pending_knowledge_revision(self, source_id: str) -> KnowledgeRevisionRecord | None:
        with self.sessions() as session:
            return session.scalar(
                select(KnowledgeRevisionRecord)
                .where(
                    KnowledgeRevisionRecord.source_id == source_id,
                    KnowledgeRevisionRecord.review_status == "pending",
                )
                .order_by(KnowledgeRevisionRecord.fetched_at.desc())
            )

    def knowledge_review_pair(
        self, source_id: str
    ) -> tuple[KnowledgeRevisionRecord | None, KnowledgeRevisionRecord | None]:
        with self.sessions() as session:
            source = session.get(KnowledgeSourceRecord, source_id)
            if source is None:
                raise LookupError(f"Unknown knowledge source {source_id}")
            active = (
                session.get(KnowledgeRevisionRecord, source.active_revision_id)
                if source.active_revision_id
                else None
            )
            pending = session.scalar(
                select(KnowledgeRevisionRecord)
                .where(
                    KnowledgeRevisionRecord.source_id == source_id,
                    KnowledgeRevisionRecord.review_status == "pending",
                )
                .order_by(KnowledgeRevisionRecord.fetched_at.desc())
            )
            return active, pending

    def approve_knowledge_source(self, source_id: str) -> KnowledgeRevisionRecord:
        with self.sessions.begin() as session:
            source = session.get(KnowledgeSourceRecord, source_id)
            if source is None:
                raise LookupError(f"Unknown knowledge source {source_id}")
            revision = session.scalar(
                select(KnowledgeRevisionRecord)
                .where(
                    KnowledgeRevisionRecord.source_id == source_id,
                    KnowledgeRevisionRecord.review_status == "pending",
                )
                .order_by(KnowledgeRevisionRecord.fetched_at.desc())
            )
            if revision is None:
                raise LookupError(f"No pending revision for knowledge source {source_id}")
            if source.active_revision_id:
                previous = session.get(KnowledgeRevisionRecord, source.active_revision_id)
                if previous:
                    previous.review_status = "superseded"
            revision.review_status = "approved"
            source.active_revision_id = revision.id
            source.updated_at = utcnow()
            session.flush()
            return revision

    def active_knowledge_chunks(self) -> list[tuple[KnowledgeSourceRecord, KnowledgeChunkRecord]]:
        with self.sessions() as session:
            rows = session.execute(
                select(KnowledgeSourceRecord, KnowledgeChunkRecord).where(
                    KnowledgeSourceRecord.status == "approved",
                    KnowledgeSourceRecord.active_revision_id == KnowledgeChunkRecord.revision_id,
                )
            )
            return list(rows.tuples())

    def knowledge_chunks_without_embedding(
        self, embedding_model: str, limit: int = 100
    ) -> list[KnowledgeChunkRecord]:
        with self.sessions() as session:
            return list(
                session.scalars(
                    select(KnowledgeChunkRecord)
                    .where(
                        (KnowledgeChunkRecord.embedding_json.is_(None))
                        | (KnowledgeChunkRecord.embedding_model != embedding_model)
                    )
                    .order_by(KnowledgeChunkRecord.id)
                    .limit(limit)
                )
            )

    def save_knowledge_embedding(
        self, chunk_id: int, embedding_model: str, embedding_json: str
    ) -> None:
        with self.sessions.begin() as session:
            chunk = session.get(KnowledgeChunkRecord, chunk_id)
            if chunk is None:
                raise LookupError(f"Unknown knowledge chunk {chunk_id}")
            chunk.embedding_model = embedding_model
            chunk.embedding_json = embedding_json
