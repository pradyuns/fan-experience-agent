import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from fan_experience.db.models import (
    AdaptationLog,
    AdaptationResult,
    Event,
    Plan,
    PlanStatus,
    PlanVersion,
    Purchase,
    Reservation,
    ReservationStatus,
    User,
)
from fan_experience.tasks.adaptation import (
    check_hard_triggers,
    run_adaptation_tick,
    should_rate_limit,
)


def _seed(session, event_hours_from_now=24):
    user_id = uuid.uuid4()
    event_id = uuid.uuid4()
    purchase_id = uuid.uuid4()
    plan_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

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
                event_time=now + timedelta(hours=event_hours_from_now),
                doors_open=now + timedelta(hours=event_hours_from_now - 1.5),
                genre="sports",
            ),
            Purchase(
                id=purchase_id,
                user_id=user_id,
                event_id=event_id,
                purchase_id="ext-001",
                ticket_count=2,
                purchased_at=now,
            ),
            Plan(
                id=plan_id,
                purchase_id=purchase_id,
                user_id=user_id,
                event_id=event_id,
                status=PlanStatus.ACTIVE,
            ),
            PlanVersion(
                plan_id=plan_id,
                version_number=1,
                payload_json={"shortlist": []},
                confidence_score=0.8,
                confidence_breakdown_json={},
                trigger_reason="initial",
                agent_reasoning="First",
                conversation_history_json=[],
            ),
        ]
    )
    session.commit()
    return plan_id, event_id


def test_no_hard_triggers_normally(db_session):
    plan_id, _ = _seed(db_session)
    assert check_hard_triggers(db_session, plan_id) == []


def test_hard_trigger_expired_event(db_session):
    plan_id, _ = _seed(db_session, event_hours_from_now=-1)
    triggers = check_hard_triggers(db_session, plan_id)
    assert "event_expired" in triggers


def test_hard_trigger_cancelled_reservation(db_session):
    plan_id, _ = _seed(db_session)
    db_session.add(
        Reservation(
            plan_id=plan_id,
            restaurant_id="rest-001",
            restaurant_name="Bestia",
            status=ReservationStatus.CANCELLED,
            party_size=2,
            reservation_time=datetime.now(timezone.utc) + timedelta(hours=2),
            idempotency_key=str(uuid.uuid4()),
        )
    )
    db_session.commit()

    triggers = check_hard_triggers(db_session, plan_id)
    assert "reservation_cancelled_by_provider" in triggers


def test_rate_limit_no_recent_replans(db_session):
    plan_id, _ = _seed(db_session)
    assert should_rate_limit(db_session, plan_id) is False


def test_rate_limit_with_recent_replan(db_session):
    plan_id, _ = _seed(db_session)
    db_session.add(
        AdaptationLog(
            plan_id=plan_id,
            tick_number=1,
            result=AdaptationResult.REPLAN_TRIGGERED,
            trigger_details_json={"reason": "weather"},
        )
    )
    db_session.commit()

    assert should_rate_limit(db_session, plan_id) is True


def test_rate_limit_after_max_replans(db_session):
    plan_id, _ = _seed(db_session)
    for index in range(5):
        db_session.add(
            AdaptationLog(
                plan_id=plan_id,
                tick_number=index + 1,
                result=AdaptationResult.REPLAN_TRIGGERED,
                trigger_details_json={},
            )
        )
    db_session.commit()

    assert should_rate_limit(db_session, plan_id) is True


def test_adaptation_tick_no_change(db_session):
    plan_id, _ = _seed(db_session)

    run_adaptation_tick(str(plan_id), db_session=db_session)

    logs = list(
        db_session.execute(
            select(AdaptationLog).where(AdaptationLog.plan_id == plan_id)
        ).scalars()
    )
    assert len(logs) == 1
    assert logs[0].result == AdaptationResult.NO_CHANGE


def test_adaptation_tick_hard_trigger(db_session):
    plan_id, _ = _seed(db_session, event_hours_from_now=-1)

    run_adaptation_tick(str(plan_id), db_session=db_session)

    logs = list(
        db_session.execute(
            select(AdaptationLog).where(AdaptationLog.plan_id == plan_id)
        ).scalars()
    )
    assert len(logs) == 1
    assert logs[0].result == AdaptationResult.HARD_TRIGGER


def test_adaptation_tick_rate_limited(db_session):
    plan_id, _ = _seed(db_session)

    # exhaust the replan budget
    for i in range(5):
        db_session.add(
            AdaptationLog(
                plan_id=plan_id,
                tick_number=i + 1,
                result=AdaptationResult.REPLAN_TRIGGERED,
                trigger_details_json={},
            )
        )
    db_session.commit()

    run_adaptation_tick(str(plan_id), db_session=db_session)

    logs = list(
        db_session.execute(
            select(AdaptationLog).where(
                AdaptationLog.plan_id == plan_id,
                AdaptationLog.result == AdaptationResult.RATE_LIMITED,
            )
        ).scalars()
    )
    assert len(logs) == 1
