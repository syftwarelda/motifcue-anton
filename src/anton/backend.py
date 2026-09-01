from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from anton.schemas import ClaimResponse, InstagramDataPage

logger = logging.getLogger(__name__)


class NoWorkAvailable(Exception):
    pass


class InstagramReconnectRequired(Exception):
    pass


class BackendClient:
    def __init__(self, base_url: str, api_key: str, timeout: float) -> None:
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Accept": "application/json",
                "Cache-Control": "no-store",
            },
            timeout=httpx.Timeout(timeout),
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = await self.client.request(method, path, **kwargs)
                if response.status_code >= 500:
                    response.raise_for_status()
                return response
            except (httpx.TransportError, httpx.HTTPStatusError) as error:
                last_error = error
                if attempt == 2:
                    raise
                await asyncio.sleep(2**attempt)
        raise RuntimeError("Unreachable") from last_error

    async def claim(self) -> ClaimResponse:
        response = await self._request("POST", "/api/internal/orders/claim")
        if response.status_code == 204:
            raise NoWorkAvailable
        response.raise_for_status()
        return ClaimResponse.model_validate(response.json())

    async def validate_instagram(self, order_id: str) -> None:
        response = await self._request("POST", f"/api/internal/orders/{order_id}/validation")
        if response.status_code == 422:
            raise InstagramReconnectRequired
        if response.status_code == 409:
            status = await self.inspect(order_id)
            if status.get("order", {}).get("status") == "GENERATING_REPORT":
                return
        response.raise_for_status()

    async def instagram_page(
        self, order_id: str, limit: int, cursor: str | None = None
    ) -> InstagramDataPage:
        params: dict[str, str | int] = {"limit": limit}
        if cursor:
            params["after"] = cursor
        response = await self._request(
            "GET", f"/api/internal/orders/{order_id}/instagram-data", params=params
        )
        response.raise_for_status()
        return InstagramDataPage.model_validate(response.json())

    async def collect_instagram_data(
        self, order_id: str, page_size: int, max_items: int
    ) -> InstagramDataPage:
        cursor: str | None = None
        first: InstagramDataPage | None = None
        all_media = []
        while len(all_media) < max_items:
            page = await self.instagram_page(order_id, page_size, cursor)
            if first is None:
                first = page
            all_media.extend(page.media[: max_items - len(all_media)])
            if not page.paging.hasNextPage or not page.paging.nextCursor:
                break
            cursor = page.paging.nextCursor
        if first is None:
            raise RuntimeError("Instagram returned no data page")
        first.media = all_media
        first.paging.nextCursor = cursor
        first.paging.hasNextPage = len(all_media) >= max_items
        return first

    async def report_generated(self, order_id: str, report_url: str) -> None:
        response = await self._request(
            "POST",
            f"/api/internal/orders/{order_id}/report-generated",
            json={"reportUrl": report_url},
        )
        response.raise_for_status()

    async def failed(self, order_id: str, error_code: str) -> None:
        response = await self._request(
            "POST", f"/api/internal/orders/{order_id}/failed", json={"errorCode": error_code}
        )
        if response.status_code not in (200, 409):
            response.raise_for_status()

    async def inspect(self, order_id: str) -> dict[str, Any]:
        response = await self._request("GET", f"/api/internal/orders/{order_id}")
        response.raise_for_status()
        return response.json()
