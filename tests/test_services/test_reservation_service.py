from datetime import datetime, timezone

import pytest

from fan_experience.db.models import ReservationStatus
from fan_experience.services.reservation_service import ReservationService


# ensuring booking preview creates a pending reservation with an idempotency key
def test_preview_creates_pending_reservation(active_plan):
    session, plan_id = active_plan
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


# ensuring confirmation transitions the preview to confirmed
def test_confirm_transitions_to_confirmed(active_plan):
    session, plan_id = active_plan
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


# ensuring repeated confirm calls are idempotent
def test_confirm_is_idempotent(active_plan):
    session, plan_id = active_plan
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


# ensuring a confirmed reservation can enter cancel-preview state
def test_cancel_preview(active_plan):
    session, plan_id = active_plan
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


# ensuring cancel confirmation transitions to cancelled
def test_confirm_cancel(active_plan):
    session, plan_id = active_plan
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


# ensuring unknown idempotency keys raise a clear error
def test_confirm_unknown_key_raises(active_plan):
    session, _plan_id = active_plan
    service = ReservationService(session)
    with pytest.raises(ValueError, match="not found"):
        service.confirm_booking("nonexistent-key")
