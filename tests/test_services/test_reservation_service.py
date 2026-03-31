import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fan_experience.db.models import (
    Base,
    Event,
    Plan,
    PlanStatus,
    Purchase,
    ReservationStatus,
    User,
)
from fan_experience.services.reservation_service import ReservationService


# creating the minimum persisted plan chain needed for reservation tests
def _setup():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)

    user_id = uuid.uuid4()
    event_id = uuid.uuid4()
    purchase_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    user = User(id=user_id, name="Fan", email="f@t.com", timezone="UTC")
    event = Event(
        id=event_id,
        name="Game",
        venue_name="Arena",
        venue_address="A",
        venue_lat=0.0,
        venue_lng=0.0,
        event_time=datetime(2026, 7, 1, 20, 0, tzinfo=timezone.utc),
        doors_open=datetime(2026, 7, 1, 18, 30, tzinfo=timezone.utc),
        genre="sports",
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
        id=plan_id,
        purchase_id=purchase_id,
        user_id=user_id,
        event_id=event_id,
        status=PlanStatus.ACTIVE,
    )
    session.add_all([user, event, purchase, plan])
    session.commit()
    return session, plan_id


# ensuring booking preview creates a pending reservation with an idempotency key
def test_preview_creates_pending_reservation():
    session, plan_id = _setup()
    service = ReservationService(session)

    preview = service.preview_booking(
        plan_id=plan_id,
        restaurant_id="rest-001",
        restaurant_name="Bestia",
        party_size=2,
        reservation_time=datetime(2026, 7, 1, 17, 30, tzinfo=timezone.utc),
    )
    assert preview.status == ReservationStatus.PREVIEW_PENDING
    assert preview.idempotency_key is not None
    session.close()


# ensuring confirmation transitions the preview to confirmed
def test_confirm_transitions_to_confirmed():
    session, plan_id = _setup()
    service = ReservationService(session)

    preview = service.preview_booking(
        plan_id=plan_id,
        restaurant_id="rest-001",
        restaurant_name="Bestia",
        party_size=2,
        reservation_time=datetime(2026, 7, 1, 17, 30, tzinfo=timezone.utc),
    )

    confirmed = service.confirm_booking(preview.idempotency_key)
    assert confirmed.status == ReservationStatus.CONFIRMED
    assert confirmed.confirmed_at is not None
    session.close()


# ensuring repeated confirm calls are idempotent
def test_confirm_is_idempotent():
    session, plan_id = _setup()
    service = ReservationService(session)

    preview = service.preview_booking(
        plan_id=plan_id,
        restaurant_id="rest-001",
        restaurant_name="Bestia",
        party_size=2,
        reservation_time=datetime(2026, 7, 1, 17, 30, tzinfo=timezone.utc),
    )

    first = service.confirm_booking(preview.idempotency_key)
    second = service.confirm_booking(preview.idempotency_key)
    assert first.id == second.id
    assert second.status == ReservationStatus.CONFIRMED
    session.close()


# ensuring a confirmed reservation can enter cancel-preview state
def test_cancel_preview():
    session, plan_id = _setup()
    service = ReservationService(session)

    preview = service.preview_booking(
        plan_id=plan_id,
        restaurant_id="rest-001",
        restaurant_name="Bestia",
        party_size=2,
        reservation_time=datetime(2026, 7, 1, 17, 30, tzinfo=timezone.utc),
    )
    service.confirm_booking(preview.idempotency_key)

    cancel_preview = service.preview_cancel(plan_id=plan_id, restaurant_id="rest-001")
    assert cancel_preview.status == ReservationStatus.CANCEL_PREVIEW_PENDING
    session.close()


# ensuring cancel confirmation transitions to cancelled
def test_confirm_cancel():
    session, plan_id = _setup()
    service = ReservationService(session)

    preview = service.preview_booking(
        plan_id=plan_id,
        restaurant_id="rest-001",
        restaurant_name="Bestia",
        party_size=2,
        reservation_time=datetime(2026, 7, 1, 17, 30, tzinfo=timezone.utc),
    )
    service.confirm_booking(preview.idempotency_key)
    cancel_preview = service.preview_cancel(plan_id=plan_id, restaurant_id="rest-001")
    cancelled = service.confirm_cancel(cancel_preview.idempotency_key)
    assert cancelled.status == ReservationStatus.CANCELLED
    session.close()


# ensuring unknown idempotency keys raise a clear error
def test_confirm_unknown_key_raises():
    session, _plan_id = _setup()
    service = ReservationService(session)
    with pytest.raises(ValueError, match="not found"):
        service.confirm_booking("nonexistent-key")
    session.close()
