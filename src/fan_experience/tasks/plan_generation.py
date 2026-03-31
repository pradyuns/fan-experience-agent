import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from fan_experience.agent.guardrails import validate_proposal
from fan_experience.agent.session import SingleTurnSession
from fan_experience.db.engine import sync_session
from fan_experience.db.models import NotificationType, Plan, PlanStatus, Purchase
from fan_experience.schemas.agent import AgentContext
from fan_experience.services.confidence import compute_confidence
from fan_experience.services.notification_service import NotificationService
from fan_experience.services.plan_service import PlanService
from fan_experience.tasks.celery_app import celery_app


@celery_app.task(name="fan_experience.run_plan_generation")
def run_plan_generation(plan_id_str: str, db_session: Session | None = None):
    plan_id = uuid.UUID(plan_id_str)

    if db_session is None:
        db_session = sync_session()
        owns_session = True
    else:
        owns_session = False

    plan = None
    try:
        plan = db_session.execute(select(Plan).where(Plan.id == plan_id)).scalar_one()
        purchase = db_session.execute(
            select(Purchase).where(Purchase.id == plan.purchase_id)
        ).scalar_one()

        context = AgentContext(
            plan_id=plan.id,
            user_id=plan.user_id,
            event_id=plan.event_id,
            ticket_count=purchase.ticket_count,
        )

        proposal = asyncio.run(SingleTurnSession().run(context))

        known_ids = {option.candidate_id for option in proposal.shortlist}
        errors = validate_proposal(proposal, known_ids, known_ids)
        if errors:
            raise ValueError(f"Proposal failed guardrails: {errors}")

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
    except Exception:
        if plan is not None:
            plan.status = PlanStatus.FAILED
            db_session.commit()
    finally:
        if owns_session:
            db_session.close()
