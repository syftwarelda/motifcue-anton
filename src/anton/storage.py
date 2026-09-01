from __future__ import annotations

from pathlib import Path
from urllib.parse import quote

import boto3

from anton.config import Settings


class StorageConfigurationError(Exception):
    pass


class ReportStorage:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def publish(self, order_id: str, report_path: Path) -> str:
        if self.settings.report_storage_driver == "local":
            base = (self.settings.report_public_base_url or "").rstrip("/")
            if not base.startswith("https://"):
                raise StorageConfigurationError(
                    "REPORT_PUBLIC_BASE_URL must be an HTTPS URL for local storage"
                )
            return f"{base}/{quote(report_path.name)}"

        bucket = self.settings.s3_bucket
        public_base = (self.settings.s3_public_base_url or "").rstrip("/")
        if not bucket or not public_base.startswith("https://"):
            raise StorageConfigurationError("S3_BUCKET and HTTPS S3_PUBLIC_BASE_URL are required")
        key = f"reports/{order_id}.pdf"
        client = boto3.client(
            "s3",
            region_name=self.settings.s3_region or None,
            endpoint_url=self.settings.s3_endpoint_url or None,
            aws_access_key_id=(
                self.settings.s3_access_key_id.get_secret_value()
                if self.settings.s3_access_key_id
                else None
            ),
            aws_secret_access_key=(
                self.settings.s3_secret_access_key.get_secret_value()
                if self.settings.s3_secret_access_key
                else None
            ),
        )
        client.upload_file(
            str(report_path),
            bucket,
            key,
            ExtraArgs={"ContentType": "application/pdf", "CacheControl": "private, max-age=0"},
        )
        return f"{public_base}/{quote(key)}"
