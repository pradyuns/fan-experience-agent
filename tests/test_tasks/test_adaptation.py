import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from fan_experience.db.models import (
    AdaptationLog,
    AdaptationResult,
    Base,
    Event,
    Plan,
    PlanStatus,
    PlanVersion,
    Purchase,
    User,
)
from fan_experience.tasks.adaptation import (
    check_hard_triggers,
    run_adaptation_tick,
    should_rate_limit,
)


def _setup(event_hours_from_now=24):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine)

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
                id=uuid.uuid4(),
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
    return session, plan_id, event_id


def test_no_hard_triggers_normally():
    session, plan_id, _ = _setup()
    assert check_hard_triggers(session, plan_id) == []
    session.close()


def test_rate_limit_no_recent_replans():
    session, plan_id, _ = _setup()
    assert should_rate_limit(session, plan_id) is False
    session.close()


def test_rate_limit_with_recent_replan():
    session, plan_id, _ = _setup()
    session.add(
        AdaptationLog(
            id=uuid.uuid4(),
            plan_id=plan_id,
            tick_number=1,
            result=AdaptationResult.REPLAN_TRIGGERED,
            trigger_details_json={"reason": "weather"},
        )
    )
    session.commit()

    assert should_rate_limit(session, plan_id) is True
    session.close()


def test_rate_limit_after_max_replans():
    session, plan_id, _ = _setup()
    for index in range(5):
        session.add(
            AdaptationLog(
                id=uuid.uuid4(),
                plan_id=plan_id,
                tick_number=index + 1,
                result=AdaptationResult.REPLAN_TRIGGERED,
                trigger_details_json={},
            )
        )
    session.commit()

    assert should_rate_limit(session, plan_id) is True
    session.close()


def test_adaptation_tick_no_change():
    session, plan_id, _ = _setup()

    run_adaptation_tick(str(plan_id), db_session=session)

    logs = session.execute(
        select(AdaptationLog).where(AdaptationLog.plan_id == plan_id)
    ).scalars()
    loaded_logs = list(logs)
    assert len(loaded_logs) == 1
    assert loaded_logs[0].result == AdaptationResult.NO_CHANGE
    session.close()
