import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from fan_experience.db.models import (
    Base,
    Event,
    Plan,
    PlanStatus,
    Purchase,
    User,
)
from fan_experience.schemas.agent import PlanProposal
from fan_experience.schemas.plan import ShortlistOption
from fan_experience.services.plan_service import PlanService


# creating an isolated in-memory db for plan-service tests
def _setup_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


# seeding the minimum plan chain required for version persistence
def _seed(session: Session):
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
        status=PlanStatus.GENERATING,
    )
    session.add_all([user, event, purchase, plan])
    session.commit()
    return plan.id, user_id, event_id


# ensuring the first saved version activates the plan
def test_save_plan_version():
    engine = _setup_db()
    with Session(engine) as session:
        plan_id, _user_id, _event_id = _seed(session)

        proposal = PlanProposal(
            shortlist=[
                ShortlistOption(
                    candidate_id="rest-001",
                    recommended=True,
                    dining_time=datetime(2026, 7, 1, 17, 30, tzinfo=timezone.utc),
                    option_reasoning="Best match",
                ),
            ],
            plan_summary="Dinner at Bestia",
            conversation_history=[],
        )

        service = PlanService(session)
        version = service.save_plan_version(
            plan_id=plan_id,
            proposal=proposal,
            confidence_result={
                "overall": 0.85,
                "freshness": 0.9,
                "source_reliability": 1.0,
                "timing_margin": 0.8,
                "preference_match": 0.7,
            },
            trigger_reason="initial",
            agent_reasoning="Selected based on proximity and preference match",
        )

        assert version.version_number == 1
        assert version.confidence_score == 0.85

        loaded_plan = session.execute(select(Plan).where(Plan.id == plan_id)).scalar_one()
        assert loaded_plan.status == PlanStatus.ACTIVE


# ensuring subsequent saves increment the version number
def test_save_second_version_increments():
    engine = _setup_db()
    with Session(engine) as session:
        plan_id, _user_id, _event_id = _seed(session)

        service = PlanService(session)
        proposal = PlanProposal(
            shortlist=[
                ShortlistOption(
                    candidate_id="rest-001",
                    recommended=True,
                    dining_time=datetime(2026, 7, 1, 17, 30, tzinfo=timezone.utc),
                    option_reasoning="First",
                )
            ],
            plan_summary="V1",
            conversation_history=[],
        )
        confidence = {
            "overall": 0.8,
            "freshness": 0.9,
            "source_reliability": 1.0,
            "timing_margin": 0.7,
            "preference_match": 0.7,
        }

        first_version = service.save_plan_version(
            plan_id,
            proposal,
            confidence,
            "initial",
            "First gen",
        )
        assert first_version.version_number == 1

        proposal.plan_summary = "V2"
        second_version = service.save_plan_version(
            plan_id,
            proposal,
            confidence,
            "replan",
            "Weather changed",
        )
        assert second_version.version_number == 2
