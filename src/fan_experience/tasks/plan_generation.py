import asyncio
import logging
import uuid
from datetime import datetime, timezone

from opentelemetry.trace import Status, StatusCode
from sqlalchemy import select
from sqlalchemy.orm import Session

from fan_experience.agent.guardrails import validate_against_event
from fan_experience.agent.session import SingleTurnSession
from fan_experience.db.engine import sync_session
from fan_experience.db.models import Event, NotificationType, Plan, PlanStatus, Purchase
from fan_experience.schemas.agent import AgentContext
from fan_experience.services.confidence import compute_confidence
from fan_experience.services.notification_service import NotificationService
from fan_experience.services.plan_service import PlanService
from fan_experience.tasks.celery_app import celery_app
from fan_experience.telemetry.context import bind_context
from fan_experience.telemetry.logging import emit_event, get_logger
from fan_experience.telemetry.metrics import record_plan_generation
from fan_experience.telemetry.tracing import get_tracer, set_span_attributes

logger = get_logger(__name__)


@celery_app.task(name="fan_experience.run_plan_generation")
def run_plan_generation(plan_id_str: str, db_session: Session | None = None):
    plan_id = uuid.UUID(plan_id_str)
    tracer = get_tracer(__name__)

    if db_session is None:
        db_session = sync_session()
        owns_session = True
    else:
        owns_session = False

    plan = None
    try:
        with bind_context(plan_id=str(plan_id)):
            with tracer.start_as_current_span("plan_generation.run") as span:
                set_span_attributes(span, **{"plan.id": str(plan_id)})
                try:
                    plan = db_session.execute(
                        select(Plan).where(Plan.id == plan_id)
                    ).scalar_one()
                    purchase = db_session.execute(
                        select(Purchase).where(Purchase.id == plan.purchase_id)
                    ).scalar_one()
                    set_span_attributes(
                        span,
                        **{
                            "purchase.external_id": purchase.purchase_id,
                            "user.id": str(plan.user_id),
                            "event.id": str(plan.event_id),
                        },
                    )

                    with bind_context(
                        purchase_id=purchase.purchase_id,
                        user_id=str(plan.user_id),
                    ):
                        emit_event(
                            logger,
                            "task.plan_generation.started",
                            status="started",
                        )

                        context = AgentContext(
                            plan_id=plan.id,
                            user_id=plan.user_id,
                            event_id=plan.event_id,
                            ticket_count=purchase.ticket_count,
                        )

                        proposal = asyncio.run(SingleTurnSession().run(context))

                        event = db_session.execute(
                            select(Event).where(Event.id == plan.event_id)
                        ).scalar_one()
                        errors = asyncio.run(
                            validate_against_event(proposal, event, purchase.ticket_count)
                        )
                        if errors:
                            raise ValueError(
                                f"Proposal failed guardrails: {errors}"
                            )

                        now = datetime.now(timezone.utc)
                        confidence = compute_confidence(
                            data_timestamps=[now],
                            source_types=["primary"],
                            slack_minutes=30.0,
                            preference_match_score=0.7,
                        )

                        PlanService(db_session).save_plan_version(
                            plan_id=plan.id,
                            proposal=proposal,
                            confidence_result=confidence,
                            trigger_reason="initial",
                            agent_reasoning="Initial plan generation",
                        )
                        NotificationService(db_session).create(
                            plan.id,
                            NotificationType.PLAN_CREATED,
                            proposal.plan_summary,
                        )

                        record_plan_generation("success")
                        set_span_attributes(span, **{"plan.result": "success"})
                        emit_event(
                            logger,
                            "task.plan_generation.finished",
                            status="success",
                        )
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR))
                    record_plan_generation("failure")
                    if plan is not None:
                        plan.status = PlanStatus.FAILED
                        db_session.commit()
                    emit_event(
                        logger,
                        "task.plan_generation.failed",
                        level=logging.ERROR,
                        status="failure",
                        error_type=type(exc).__name__,
                    )
                    raise
    finally:
        if owns_session:
            db_session.close()
