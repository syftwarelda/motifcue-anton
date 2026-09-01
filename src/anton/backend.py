from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from time import perf_counter
from typing import Any

import httpx

from anton.schemas import ClaimResponse, InstagramDataPage

logger = logging.getLogger(__name__)


class NoWorkAvailable(Exception):
    pass


class InstagramReconnectRequired(Exception):
    pass


class BackendClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float,
        vercel_bypass_secret: str | None = None,
    ) -> None:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Cache-Control": "no-store",
        }
        if vercel_bypass_secret:
            headers["x-vercel-protection-bypass"] = vercel_bypass_secret
        self.client = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(timeout),
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(3):
            started = perf_counter()
            try:
                logger.debug("→ Backend %s %s (attempt %d/3)", method, path, attempt + 1)
                response = await self.client.request(method, path, **kwargs)
                elapsed_ms = round((perf_counter() - started) * 1000)
                logger.debug(
                    "← Backend %s %s · %d · %d ms",
                    method,
                    path,
                    response.status_code,
                    elapsed_ms,
                )
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
        logger.info("◇ Looking for the oldest order ready to process")
        response = await self._request("POST", "/api/internal/orders/claim")
        if response.status_code == 204:
            raise NoWorkAvailable
        response.raise_for_status()
        claim = ClaimResponse.model_validate(response.json())
        logger.info(
            "◆ Claimed order %s · status=%s · resumed=%s",
            claim.order.id,
            claim.order.status,
            claim.resumed,
        )
        return claim

    async def validate_instagram(self, order_id: str) -> None:
        logger.info("● Checking Instagram connection · order=%s", order_id)
        response = await self._request("POST", f"/api/internal/orders/{order_id}/validation")
        if response.status_code == 422:
            raise InstagramReconnectRequired
        if response.status_code == 409:
            status = await self.inspect(order_id)
            if status.get("order", {}).get("status") == "GENERATING_REPORT":
                return
        response.raise_for_status()
        logger.info("✓ Instagram connection is valid · order=%s", order_id)

    async def instagram_page(
        self, order_id: str, limit: int, cursor: str | None = None
    ) -> InstagramDataPage:
        page, _ = await self._instagram_page_payload(order_id, limit, cursor)
        return page

    async def _instagram_page_payload(
        self, order_id: str, limit: int, cursor: str | None = None
    ) -> tuple[InstagramDataPage, dict[str, Any]]:
        params: dict[str, str | int] = {"limit": limit}
        if cursor:
            params["after"] = cursor
        response = await self._request(
            "GET", f"/api/internal/orders/{order_id}/instagram-data", params=params
        )
        response.raise_for_status()
        payload = response.json()
        return InstagramDataPage.model_validate(payload), payload

    async def collect_instagram_data(
        self,
        order_id: str,
        page_size: int,
        max_items: int,
        raw_pages_directory: Path | None = None,
    ) -> InstagramDataPage:
        logger.info("● Collecting authorized Instagram data · limit=%d", max_items)
        cursor: str | None = None
        first: InstagramDataPage | None = None
        all_media = []
        page_number = 0
        while len(all_media) < max_items:
            page, raw_payload = await self._instagram_page_payload(order_id, page_size, cursor)
            page_number += 1
            if raw_pages_directory:
                raw_pages_directory.mkdir(parents=True, exist_ok=True)
                destination = raw_pages_directory / f"instagram-data-page-{page_number:03d}.json"
                temporary = destination.with_suffix(".tmp")
                temporary.write_text(
                    json.dumps(raw_payload, ensure_ascii=False, indent=2), encoding="utf-8"
                )
                temporary.replace(destination)
            if first is None:
                first = page
            all_media.extend(page.media[: max_items - len(all_media)])
            logger.info("  Collected %d media items", len(all_media))
            if not page.paging.hasNextPage or not page.paging.nextCursor:
                break
            cursor = page.paging.nextCursor
        if first is None:
            raise RuntimeError("Instagram returned no data page")
        first.media = all_media
        first.paging.nextCursor = cursor
        first.paging.hasNextPage = len(all_media) >= max_items
        logger.info("✓ Instagram data collected · media=%d", len(all_media))
        return first

    async def report_generated(self, order_id: str, report_url: str | None) -> None:
        logger.info("● Notifying MotifCue that the report is ready · order=%s", order_id)
        payload = {"reportUrl": report_url} if report_url else {"storageMode": "LOCAL"}
        response = await self._request(
            "POST",
            f"/api/internal/orders/{order_id}/report-generated",
            json=payload,
        )
        response.raise_for_status()
        logger.info("✓ MotifCue accepted the completed report · order=%s", order_id)

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
