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
