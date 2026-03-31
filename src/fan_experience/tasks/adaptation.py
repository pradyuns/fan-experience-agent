import uuid
import logging
from datetime import datetime, timedelta, timezone

from opentelemetry.trace import Status, StatusCode
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
from fan_experience.tasks.celery_app import celery_app
from fan_experience.telemetry.context import bind_context
from fan_experience.telemetry.logging import emit_event, get_logger
from fan_experience.telemetry.metrics import record_adaptation_tick
from fan_experience.telemetry.tracing import get_tracer, set_span_attributes

logger = get_logger(__name__)


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


@celery_app.task(name="fan_experience.run_adaptation_tick")
def run_adaptation_tick(plan_id_str: str, db_session: Session | None = None):
    plan_id = uuid.UUID(plan_id_str)
    tracer = get_tracer(__name__)

    owns_session = db_session is None
    if owns_session:
        db_session = sync_session()

    try:
        with bind_context(plan_id=str(plan_id)):
            with tracer.start_as_current_span("adaptation.tick") as span:
                set_span_attributes(span, **{"plan.id": str(plan_id)})
                try:
                    max_tick = db_session.execute(
                        select(func.coalesce(func.max(AdaptationLog.tick_number), 0)).where(
                            AdaptationLog.plan_id == plan_id
                        )
                    ).scalar_one()
                    tick_number = max_tick + 1

                    hard_triggers = check_hard_triggers(db_session, plan_id)
                    if hard_triggers:
                        result = AdaptationResult.HARD_TRIGGER
                        details = {"triggers": hard_triggers}
                    elif should_rate_limit(db_session, plan_id):
                        result = AdaptationResult.RATE_LIMITED
                        details = {"reason": "rate_limited"}
                    else:
                        result = AdaptationResult.NO_CHANGE
                        details = {"checked": ["weather", "traffic", "availability"]}

                    db_session.add(
                        AdaptationLog(
                            plan_id=plan_id,
                            tick_number=tick_number,
                            result=result,
                            trigger_details_json=details,
                        )
                    )
                    db_session.commit()
                    record_adaptation_tick(result.value.lower())
                    emit_event(
                        logger,
                        "adaptation.tick.completed",
                        status=result.value.lower(),
                        tick_number=tick_number,
                    )
                    return result.value
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR))
                    emit_event(
                        logger,
                        "adaptation.tick.failed",
                        level=logging.ERROR,
                        status="failure",
                        error_type=type(exc).__name__,
                    )
                    raise
    finally:
        if owns_session:
            db_session.close()
