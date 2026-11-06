import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from fan_experience.db.models import (
    Event,
    Notification,
    NotificationType,
    Plan,
    PlanStatus,
    PlanVersion,
    Purchase,
    User,
)
from fan_experience.tasks.plan_generation import run_plan_generation
from fan_experience.telemetry.metrics import snapshot_metric_events


def _seed(session):
    user_id = uuid.uuid4()
    event_id = uuid.uuid4()
    purchase_id = uuid.uuid4()
    plan_id = uuid.uuid4()

    session.add_all(
        [
            User(id=user_id, name="Fan", email="f@t.com", timezone="UTC"),
            Event(
                id=event_id,
                name="Game",
                venue_name="Arena",
                venue_address="A",
                venue_lat=34.043,
                venue_lng=-118.267,
                event_time=datetime(2026, 7, 1, 20, 0, tzinfo=timezone.utc),
                doors_open=datetime(2026, 7, 1, 18, 30, tzinfo=timezone.utc),
                genre="basketball",
            ),
            Purchase(
                id=purchase_id,
                user_id=user_id,
                event_id=event_id,
                purchase_id="ext-001",
                ticket_count=2,
                purchased_at=datetime.now(timezone.utc),
            ),
            Plan(
                id=plan_id,
                purchase_id=purchase_id,
                user_id=user_id,
                event_id=event_id,
                status=PlanStatus.GENERATING,
            ),
        ]
    )
    session.commit()
    return plan_id


def test_run_plan_generation_success(db_session):
    plan_id = _seed(db_session)

    from fan_experience.schemas.agent import PlanProposal
    from fan_experience.schemas.plan import ShortlistOption

    mock_proposal = PlanProposal(
        shortlist=[
            ShortlistOption(
                candidate_id="rest-001",
                recommended=True,
                dining_time=datetime(2026, 7, 1, 16, 30, tzinfo=timezone.utc),
                option_reasoning="Best match",
            ),
            ShortlistOption(
                candidate_id="rest-002",
                recommended=False,
                dining_time=datetime(2026, 7, 1, 17, 0, tzinfo=timezone.utc),
                option_reasoning="Budget option",
            ),
        ],
        plan_summary="Dinner at Bestia at 4:30pm",
        conversation_history=[],
    )

    mock_agent_session = MagicMock()
    mock_agent_session.run = AsyncMock(return_value=mock_proposal)

    with patch(
        "fan_experience.tasks.plan_generation.SingleTurnSession",
        return_value=mock_agent_session,
    ):
        run_plan_generation(str(plan_id), db_session=db_session)

    plan = db_session.execute(select(Plan).where(Plan.id == plan_id)).scalar_one()
    assert plan.status == PlanStatus.ACTIVE

    versions = list(
        db_session.execute(
            select(PlanVersion).where(PlanVersion.plan_id == plan_id)
        ).scalars()
    )
    assert len(versions) == 1
    assert versions[0].version_number == 1

    notifications = list(
        db_session.execute(
            select(Notification).where(Notification.plan_id == plan_id)
        ).scalars()
    )
    assert len(notifications) == 1
    assert notifications[0].type == NotificationType.PLAN_CREATED
    assert snapshot_metric_events("fan_plan_generation_total")[-1].attributes == {
        "result": "success"
    }


@pytest.mark.parametrize(
    ("candidate_id", "hour", "message"),
    [("invented", 16, "Unknown candidate_id"), ("rest-001", 18, "not feasible")],
)
def test_plan_generation_rejects_unverified_or_infeasible_candidates(
    db_session, candidate_id, hour, message
):
    from fan_experience.schemas.agent import PlanProposal
    from fan_experience.schemas.plan import ShortlistOption

    plan_id = _seed(db_session)
    proposal = PlanProposal(
        shortlist=[
            ShortlistOption(
                candidate_id=candidate_id, recommended=True,
                dining_time=datetime(2026, 7, 1, hour, 0, tzinfo=timezone.utc),
                option_reasoning="Suggested by agent",
            ),
            ShortlistOption(
                candidate_id="rest-002", recommended=False,
                dining_time=datetime(2026, 7, 1, 17, 0, tzinfo=timezone.utc),
                option_reasoning="Alternative",
            ),
        ],
        plan_summary="Dinner", conversation_history=[],
    )
    agent = MagicMock()
    agent.run = AsyncMock(return_value=proposal)
    with patch("fan_experience.tasks.plan_generation.SingleTurnSession", return_value=agent):
        with pytest.raises(ValueError, match=message):
            run_plan_generation(str(plan_id), db_session=db_session)
    plan = db_session.execute(select(Plan).where(Plan.id == plan_id)).scalar_one()
    assert plan.status == PlanStatus.FAILED
    assert not list(db_session.execute(select(PlanVersion).where(PlanVersion.plan_id == plan_id)).scalars())


def test_run_plan_generation_failure_marks_failed(db_session):
    plan_id = _seed(db_session)

    mock_agent_session = MagicMock()
    mock_agent_session.run = AsyncMock(
        side_effect=RuntimeError("Agent exceeded maximum tool rounds")
    )

    with patch(
        "fan_experience.tasks.plan_generation.SingleTurnSession",
        return_value=mock_agent_session,
    ):
        with pytest.raises(RuntimeError, match="Agent exceeded maximum tool rounds"):
            run_plan_generation(str(plan_id), db_session=db_session)

    plan = db_session.execute(select(Plan).where(Plan.id == plan_id)).scalar_one()
    assert plan.status == PlanStatus.FAILED
    assert snapshot_metric_events("fan_plan_generation_total")[-1].attributes == {
        "result": "failure"
    }
