import httpx
import pytest
import respx

from anton.backend import BackendClient


@pytest.mark.asyncio
@respx.mock
async def test_local_report_completion_sends_no_filesystem_path() -> None:
    route = respx.post(
        "https://motifcue.example.com/api/internal/orders/order-1/report-generated"
    ).mock(return_value=httpx.Response(200, json={"status": "AWAITING_REVIEW"}))
    client = BackendClient("https://motifcue.example.com", "secret", 10, "vercel-bypass")

    try:
        await client.report_generated("order-1", None)
    finally:
        await client.close()

    assert route.called
    assert route.calls.last.request.content == b'{"storageMode":"LOCAL"}'
    assert route.calls.last.request.headers["x-vercel-protection-bypass"] == "vercel-bypass"


@pytest.mark.asyncio
@respx.mock
async def test_collection_saves_each_raw_endpoint_page(tmp_path) -> None:
    first = {
        "orderId": "order-1",
        "account": {"id": "ig-1", "username": "creator"},
        "media": [
            {
                "id": "one",
                "media_type": "IMAGE",
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ],
        "paging": {"nextCursor": "next", "hasNextPage": True},
    }
    second = {
        "orderId": "order-1",
        "account": {"id": "ig-1", "username": "creator"},
        "media": [
            {
                "id": "two",
                "media_type": "VIDEO",
                "timestamp": "2026-01-02T00:00:00Z",
            }
        ],
        "paging": {"nextCursor": None, "hasNextPage": False},
    }
    route = respx.get(
        "https://motifcue.example.com/api/internal/orders/order-1/instagram-data"
    ).mock(side_effect=[httpx.Response(200, json=first), httpx.Response(200, json=second)])
    client = BackendClient("https://motifcue.example.com", "secret", 10)

    try:
        data = await client.collect_instagram_data("order-1", 1, 10, tmp_path)
    finally:
        await client.close()

    assert route.call_count == 2
    assert [item.id for item in data.media] == ["one", "two"]
    assert (tmp_path / "instagram-data-page-001.json").read_text().find('"one"') > 0
    assert (tmp_path / "instagram-data-page-002.json").read_text().find('"two"') > 0
