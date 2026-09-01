from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageOps

from anton.schemas import MediaItem


class MediaDownloadError(Exception):
    pass


class MediaManager:
    def __init__(self, data_directory: Path, max_bytes: int, timeout: float) -> None:
        self.data_directory = data_directory
        self.max_bytes = max_bytes
        self.client = httpx.AsyncClient(timeout=httpx.Timeout(timeout), follow_redirects=True)

    async def close(self) -> None:
        await self.client.aclose()

    @staticmethod
    def representative_url(item: MediaItem) -> str | None:
        if item.media_type.upper() == "VIDEO":
            return item.thumbnail_url or item.media_url
        return item.media_url or item.thumbnail_url

    async def representative_image(self, order_id: str, item: MediaItem) -> Path | None:
        url = self.representative_url(item)
        if not url:
            return None
        parsed = urlparse(url)
        if parsed.scheme != "https":
            raise MediaDownloadError("Only HTTPS media URLs are accepted")
        directory = self.data_directory / "orders" / order_id / "media"
        directory.mkdir(parents=True, exist_ok=True)
        raw_path = directory / f"{item.id}.source"
        image_path = directory / f"{item.id}.jpg"
        if image_path.exists():
            return image_path

        size = 0
        try:
            async with self.client.stream("GET", url) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "")
                if not content_type.startswith("image/"):
                    return None
                with raw_path.open("wb") as output:
                    async for chunk in response.aiter_bytes():
                        size += len(chunk)
                        if size > self.max_bytes:
                            raise MediaDownloadError("Media exceeds configured byte limit")
                        output.write(chunk)
            with Image.open(raw_path) as source:
                normalized = ImageOps.exif_transpose(source).convert("RGB")
                normalized.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                normalized.save(image_path, "JPEG", quality=88, optimize=True)
            raw_path.unlink(missing_ok=True)
            return image_path
        except (httpx.HTTPError, OSError) as exc:
            raw_path.unlink(missing_ok=True)
            raise MediaDownloadError("Unable to prepare representative image") from exc

    @staticmethod
    def fingerprint(item: MediaItem, image_path: Path | None) -> str:
        digest = hashlib.sha256()
        digest.update(item.id.encode())
        digest.update(item.media_type.encode())
        digest.update((item.caption or "").encode())
        digest.update(item.timestamp.isoformat().encode())
        if image_path and image_path.exists():
            with image_path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
        return digest.hexdigest()
