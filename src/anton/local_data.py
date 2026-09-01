from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from anton.config import Settings
from anton.db import Database, Job


def snapshot_path(settings: Settings, db: Database, order_id: str) -> Path:
    job = db.get_job(order_id)
    if job and job.snapshot_path:
        configured = Path(job.snapshot_path)
        if configured.exists():
            return configured
    return settings.data_directory / "orders" / order_id / "instagram-snapshot.json"


def _job_payload(job: Job | None) -> dict[str, Any] | None:
    if job is None:
        return None
    return {
        "orderId": job.order_id,
        "stage": job.stage,
        "backendStatus": job.backend_status,
        "snapshotPath": job.snapshot_path,
        "reportPath": job.report_path,
        "reportUrl": job.report_url,
        "attempts": job.attempts,
        "lastError": job.last_error,
        "createdAt": job.created_at.isoformat(),
        "updatedAt": job.updated_at.isoformat(),
    }


def export_order_data(
    settings: Settings,
    db: Database,
    order_id: str,
    output_path: Path | None = None,
) -> Path:
    """Export the locally persisted order payload and derived AI artifacts as JSON."""
    source_path = snapshot_path(settings, db, order_id)
    if not source_path.exists():
        raise FileNotFoundError(f"No local Instagram snapshot found for order {order_id}")

    instagram_data = json.loads(source_path.read_text(encoding="utf-8"))
    job = db.get_job(order_id)
    synthesis = json.loads(job.synthesis_json) if job and job.synthesis_json else None
    analyses = []
    for row in db.media_results(order_id):
        analyses.append(
            {
                "mediaId": row.media_id,
                "fingerprint": row.fingerprint,
                "analysis": json.loads(row.result_json),
                "createdAt": row.created_at.isoformat(),
                "updatedAt": row.updated_at.isoformat(),
            }
        )

    media_directory = settings.data_directory / "orders" / order_id / "media"
    local_media = [
        {
            "name": path.name,
            "relativePath": str(path.relative_to(settings.data_directory)),
            "bytes": path.stat().st_size,
        }
        for path in sorted(media_directory.glob("*"))
        if path.is_file()
    ]
    endpoint_directory = settings.data_directory / "orders" / order_id / "endpoint-responses"
    endpoint_responses = [
        {
            "file": path.name,
            "payload": json.loads(path.read_text(encoding="utf-8")),
        }
        for path in sorted(endpoint_directory.glob("instagram-data-page-*.json"))
    ]
    bundle = {
        "schemaVersion": 1,
        "exportedAt": datetime.now(UTC).isoformat(),
        "orderId": order_id,
        "notice": (
            "Contains customer Instagram data, captions and media URLs. It contains no "
            "Instagram access token."
        ),
        "localJob": _job_payload(job),
        "endpointResponses": endpoint_responses,
        "instagramData": instagram_data,
        "accountSynthesis": synthesis,
        "mediaAnalyses": analyses,
        "localMediaFiles": local_media,
    }

    destination = output_path or settings.data_directory / "exports" / f"{order_id}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(destination)
    return destination
