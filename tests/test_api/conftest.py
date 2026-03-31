import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.orm import Session

from fan_experience.api.app import create_app
from fan_experience.db.models import (
    Event,
    Plan,
    PlanStatus,
    PlanVersion,
    Purchase,
    User,
    UserPreference,
)


# seeds user/event/purchase/plan chain for api tests
def _seed_plan(session: Session, plan_id: uuid.UUID, user_id: uuid.UUID):
    event_id = uuid.uuid4()
    purchase_id = uuid.uuid4()

    session.add_all(
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
    session.commit()


# plan with a version attached (for plans api tests)
@pytest.fixture
def plan_with_version(db_session: Session):
    plan_id = uuid.uuid4()
    user_id = uuid.uuid4()
    _seed_plan(db_session, plan_id, user_id)

    db_session.add(
        PlanVersion(
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
    )
    db_session.commit()
    yield db_session, plan_id, user_id


# active plan without versions (for reservation api tests)
@pytest.fixture
def active_plan_db(db_session: Session):
    plan_id = uuid.uuid4()
    user_id = uuid.uuid4()
    _seed_plan(db_session, plan_id, user_id)
    yield db_session, plan_id


# user with preferences (for users api tests)
@pytest.fixture
def user_with_prefs(db_session: Session):
    user_id = uuid.uuid4()
    db_session.add(User(id=user_id, name="Fan", email="f@t.com", timezone="UTC"))
    db_session.add_all(
        [
            UserPreference(
                user_id=user_id,
                preference_type="cuisine",
                value_json={"italian": 0.9},
                confidence=0.8,
            ),
            UserPreference(
                user_id=user_id,
                preference_type="price",
                value_json={"range": "medium"},
                confidence=0.7,
            ),
        ]
    )
    db_session.commit()
    yield db_session, user_id


# creates a test client with db session override
@pytest.fixture
def test_client(db_session: Session):
    app = create_app()

    async def override_get_db():
        yield db_session

    from fan_experience.api.deps import get_db

    app.dependency_overrides[get_db] = override_get_db

    async def _client():
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            yield client

    return app, _client
