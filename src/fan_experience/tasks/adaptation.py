import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from fan_experience.config import settings
from fan_experience.db.engine import as_utc, sync_session
from fan_experience.db.models import (
    AdaptationLog,
    AdaptationResult,
    Event,
    Plan,
    Reservation,
    ReservationStatus,
)


def check_hard_triggers(session: Session, plan_id: uuid.UUID) -> list[str]:
    triggers: list[str] = []

    plan = session.execute(select(Plan).where(Plan.id == plan_id)).scalar_one()
    event = session.execute(select(Event).where(Event.id == plan.event_id)).scalar_one()

    if as_utc(event.event_time) < datetime.now(timezone.utc):
        triggers.append("event_expired")

    cancelled_reservation = session.execute(
        select(Reservation).where(
            Reservation.plan_id == plan_id,
            Reservation.status == ReservationStatus.CANCELLED,
        )
    ).scalar_one_or_none()
    if cancelled_reservation is not None:
        triggers.append("reservation_cancelled_by_provider")

    return triggers


def should_rate_limit(session: Session, plan_id: uuid.UUID) -> bool:
    total_replans = session.execute(
        select(func.count(AdaptationLog.id)).where(
            AdaptationLog.plan_id == plan_id,
            AdaptationLog.result == AdaptationResult.REPLAN_TRIGGERED,
        )
    ).scalar_one()
    if total_replans >= settings.max_replans_per_plan:
        return True

    # check for recent replans within the cooldown window
    cooldown_start = datetime.now(timezone.utc) - timedelta(
        minutes=settings.replan_cooldown_minutes
    )
    recent_count = session.execute(
        select(func.count(AdaptationLog.id)).where(
            AdaptationLog.plan_id == plan_id,
            AdaptationLog.result == AdaptationResult.REPLAN_TRIGGERED,
            AdaptationLog.created_at >= cooldown_start,
        )
    ).scalar_one()
    return recent_count > 0


def run_adaptation_tick(plan_id_str: str, db_session: Session | None = None):
    plan_id = uuid.UUID(plan_id_str)

    owns_session = db_session is None
    if owns_session:
        db_session = sync_session()

    try:
        max_tick = db_session.execute(
            select(func.coalesce(func.max(AdaptationLog.tick_number), 0)).where(
                AdaptationLog.plan_id == plan_id
            )
        ).scalar_one()
        tick_number = max_tick + 1

        hard_triggers = check_hard_triggers(db_session, plan_id)
        if hard_triggers:
            db_session.add(
                AdaptationLog(
                    plan_id=plan_id,
                    tick_number=tick_number,
                    result=AdaptationResult.HARD_TRIGGER,
                    trigger_details_json={"triggers": hard_triggers},
                )
            )
            db_session.commit()
            return

        if should_rate_limit(db_session, plan_id):
            db_session.add(
                AdaptationLog(
                    plan_id=plan_id,
                    tick_number=tick_number,
                    result=AdaptationResult.RATE_LIMITED,
                    trigger_details_json={"reason": "rate_limited"},
                )
            )
            db_session.commit()
            return

        db_session.add(
            AdaptationLog(
                plan_id=plan_id,
                tick_number=tick_number,
                result=AdaptationResult.NO_CHANGE,
                trigger_details_json={
                    "checked": ["weather", "traffic", "availability"]
                },
            )
        )
        db_session.commit()
    finally:
        if owns_session:
            db_session.close()
