import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from fan_experience.api.app import create_app
from fan_experience.telemetry.metrics import snapshot_metric_events


@pytest.mark.asyncio
async def test_middleware_adds_request_id_and_uses_route_template():
    app = create_app()

    @app.get("/telemetry-test/{item_id}")
    async def telemetry_test(item_id: str):
        return {"item_id": item_id}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get("/telemetry-test/123")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"]
    http_request_metric = snapshot_metric_events("fan_http_requests_total")[-1]
    assert http_request_metric.attributes == {
        "method": "GET",
        "route": "/telemetry-test/{item_id}",
        "status_code": "200",
    }


@pytest.mark.asyncio
async def test_middleware_preserves_inbound_request_id():
    app = create_app()
    expected_request_id = str(uuid.uuid4())

    @app.get("/telemetry-request-id")
    async def telemetry_request_id():
        return {"ok": True}

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/telemetry-request-id",
            headers={"X-Request-ID": expected_request_id},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == expected_request_id

