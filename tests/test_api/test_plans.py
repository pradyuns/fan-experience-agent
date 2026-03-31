import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

from fan_experience.api.app import create_app
from fan_experience.db.models import Event, Plan, PlanStatus, PlanVersion, Purchase, User


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
            PlanVersion(
                id=uuid.uuid4(),
                plan_id=plan_id,
                version_number=1,
                payload_json={
                    "shortlist": [
                        {
                            "candidate_id": "rest-001",
                            "recommended": True,
                            "dining_time": "2026-07-01T17:30:00Z",
                            "option_reasoning": "Best match",
                        }
                    ],
                    "plan_summary": "Dinner at Bestia",
                },
                confidence_score=0.85,
                confidence_breakdown_json={"freshness": 0.9},
                trigger_reason="initial",
                agent_reasoning="Good pick",
                conversation_history_json=[],
            ),
        ]
    )
    db_session.commit()
    yield db_session, plan_id, user_id


@pytest.mark.asyncio
async def test_get_plan(seeded_db):
    session, plan_id, _ = seeded_db
    app = create_app()

    async def override_get_db():
        yield session

    from fan_experience.api.deps import get_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.get(f"/plans/{plan_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ACTIVE"
    assert len(data["versions"]) == 1
    assert data["versions"][0]["shortlist"][0]["candidate_id"] == "rest-001"


@pytest.mark.asyncio
async def test_refine_plan(seeded_db):
    session, plan_id, _ = seeded_db
    app = create_app()

    async def override_get_db():
        yield session

    from fan_experience.api.deps import get_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/plans/{plan_id}/refine",
            json={
                "message": "cheaper options please",
                "structured_preferences": {"price_range": "low"},
            },
        )

    assert response.status_code == 200
    assert response.json()["status"] == "refine_queued"


@pytest.mark.asyncio
async def test_feedback(seeded_db):
    session, plan_id, _ = seeded_db
    app = create_app()

    async def override_get_db():
        yield session

    from fan_experience.api.deps import get_db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        response = await client.post(
            f"/plans/{plan_id}/feedback",
            json={"rating": 5, "comment": "Great pick!"},
        )

    assert response.status_code == 200
