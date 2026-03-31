import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from fan_experience.api.app import create_app
from fan_experience.db.models import Reservation, ReservationStatus


def _make_client(session):
    app = create_app()

    async def override_get_db():
        yield session

    from fan_experience.api.deps import get_db

    app.dependency_overrides[get_db] = override_get_db
    return app


@pytest.mark.asyncio
async def test_preview_and_confirm_flow(active_plan_db):
    session, plan_id = active_plan_db
    app = _make_client(session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        preview_response = await client.post(
            f"/plans/{plan_id}/reservations/preview",
            json={
                "action": "book",
                "candidate_id": "rest-001",
                "dining_time": "2026-07-01T17:30:00Z",
                "party_size": 2,
            },
        )
        assert preview_response.status_code == 200
        preview_data = preview_response.json()
        assert "idempotency_key" in preview_data
        assert preview_data["status"] == "PREVIEW_PENDING"

        confirm_response = await client.post(
            f"/plans/{plan_id}/reservations/confirm",
            json={"idempotency_key": preview_data["idempotency_key"]},
        )
        assert confirm_response.status_code == 200
        assert confirm_response.json()["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_confirm_unknown_key(active_plan_db):
    session, plan_id = active_plan_db
    app = _make_client(session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/plans/{plan_id}/reservations/confirm",
            json={"idempotency_key": "nonexistent"},
        )

    assert response.status_code == 400
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_confirm_wrong_state(active_plan_db):
    session, plan_id = active_plan_db

    # create a reservation already in CANCELLED state
    reservation = Reservation(
        plan_id=plan_id,
        restaurant_id="rest-001",
        restaurant_name="Bestia",
        status=ReservationStatus.CANCELLED,
        party_size=2,
        reservation_time=datetime(2026, 7, 1, 17, 30, tzinfo=timezone.utc),
        idempotency_key="cancelled-key",
    )
    session.add(reservation)
    session.commit()

    app = _make_client(session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/plans/{plan_id}/reservations/confirm",
            json={"idempotency_key": "cancelled-key"},
        )

    assert response.status_code == 400
    assert "Cannot confirm" in response.json()["detail"]


@pytest.mark.asyncio
async def test_confirm_idempotent(active_plan_db):
    session, plan_id = active_plan_db
    app = _make_client(session)

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        preview = await client.post(
            f"/plans/{plan_id}/reservations/preview",
            json={
                "action": "book",
                "candidate_id": "rest-001",
                "dining_time": "2026-07-01T17:30:00Z",
                "party_size": 2,
            },
        )
        key = preview.json()["idempotency_key"]

        first = await client.post(
            f"/plans/{plan_id}/reservations/confirm",
            json={"idempotency_key": key},
        )
        second = await client.post(
            f"/plans/{plan_id}/reservations/confirm",
            json={"idempotency_key": key},
        )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["reservation_id"] == second.json()["reservation_id"]
