import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import Session

from fan_experience.db.models import Event, Plan, PlanStatus, Purchase, User


# seeding the minimum user/event/purchase/plan chain for service tests
def _seed_plan(session: Session, plan_status: PlanStatus) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    user_id = uuid.uuid4()
    event_id = uuid.uuid4()
    purchase_id = uuid.uuid4()

    user = User(id=user_id, name="Fan", email="f@t.com", timezone="UTC")
    event = Event(
        id=event_id,
        name="Game",
        venue_name="Arena",
        venue_address="123 St",
        venue_lat=34.043,
        venue_lng=-118.267,
        event_time=datetime(2026, 7, 1, 20, 0, tzinfo=timezone.utc),
        doors_open=datetime(2026, 7, 1, 18, 30, tzinfo=timezone.utc),
        genre="basketball",
    )
    purchase = Purchase(
        id=purchase_id,
        user_id=user_id,
        event_id=event_id,
        purchase_id="ext-001",
        ticket_count=2,
        purchased_at=datetime.now(timezone.utc),
    )
    plan = Plan(
        id=uuid.uuid4(),
        purchase_id=purchase_id,
        user_id=user_id,
        event_id=event_id,
        status=plan_status,
    )
    session.add_all([user, event, purchase, plan])
    session.commit()
    return plan.id, user_id, event_id


@pytest.fixture
def generating_plan(db_session: Session) -> tuple[Session, uuid.UUID]:
    plan_id, _, _ = _seed_plan(db_session, PlanStatus.GENERATING)
    return db_session, plan_id


@pytest.fixture
def active_plan(db_session: Session) -> tuple[Session, uuid.UUID]:
    plan_id, _, _ = _seed_plan(db_session, PlanStatus.ACTIVE)
    return db_session, plan_id
