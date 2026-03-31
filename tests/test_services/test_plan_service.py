from datetime import datetime, timezone

from sqlalchemy import select

from fan_experience.db.models import Plan, PlanStatus
from fan_experience.schemas.agent import PlanProposal
from fan_experience.schemas.plan import ShortlistOption
from fan_experience.services.plan_service import PlanService


# ensuring the first saved version activates the plan
def test_save_plan_version(generating_plan):
    session, plan_id = generating_plan

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
def test_save_second_version_increments(generating_plan):
    session, plan_id = generating_plan

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
