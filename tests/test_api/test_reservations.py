import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

from fan_experience.api.app import create_app
from fan_experience.db.models import Event, Plan, PlanStatus, Purchase, User


@pytest.fixture
def seeded_db(db_session: Session):
    user_id = uuid.uuid4()
    event_id = uuid.uuid4()
    purchase_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    db_session.add_all(
        [
            User(id=user_id, name="Fan", email="f@t.com", timezone="UTC"),
            Event(
                id=event_id,
                name="Game",
                venue_name="V",
                venue_address="A",
                venue_lat=34.0,
                venue_lng=-118.0,
                event_time=datetime(2026, 7, 1, 20, 0, tzinfo=timezone.utc),
                doors_open=datetime(2026, 7, 1, 18, 30, tzinfo=timezone.utc),
                genre="sports",
            ),
            Purchase(
                id=purchase_id,
                user_id=user_id,
                event_id=event_id,
                purchase_id="ext-001",
                ticket_count=2,
                purchased_at=datetime.now(timezone.utc),
            ),
            Plan(
                id=plan_id,
                purchase_id=purchase_id,
                user_id=user_id,
                event_id=event_id,
                status=PlanStatus.ACTIVE,
            ),
        ]
    )
    db_session.commit()
    yield db_session, plan_id


@pytest.mark.asyncio
async def test_preview_and_confirm_flow(seeded_db):
    session, plan_id = seeded_db
    app = create_app()

    async def override_get_db():
        yield session

    from fan_experience.api.deps import get_db

    app.dependency_overrides[get_db] = override_get_db

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
