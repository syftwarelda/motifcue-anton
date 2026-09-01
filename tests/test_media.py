from datetime import UTC, datetime

import httpx
import pytest
import respx

from anton.media import MediaDownloadError, MediaManager
from anton.schemas import MediaItem


@pytest.mark.asyncio
async def test_failed_refresh_preserves_existing_local_image(tmp_path) -> None:
    manager = MediaManager(tmp_path, max_bytes=1024, timeout=5)
    item = MediaItem(
        id="post-1",
        media_type="IMAGE",
        media_url="https://cdn.example.com/expired.jpg",
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )
    existing = manager.local_image_path("order-1", item)
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"previous-image")

    try:
        with respx.mock:
            respx.get(item.media_url).mock(return_value=httpx.Response(403))
            with pytest.raises(MediaDownloadError):
                await manager.representative_image("order-1", item, refresh=True)
    finally:
        await manager.close()

    assert existing.read_bytes() == b"previous-image"
    assert not existing.with_name("post-1.refresh.source").exists()
    assert not existing.with_name("post-1.refresh.jpg").exists()
