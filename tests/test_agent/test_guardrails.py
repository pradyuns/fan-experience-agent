from datetime import datetime, timezone

import pytest

from fan_experience.agent.guardrails import validate_proposal
from fan_experience.schemas.agent import PlanProposal
from fan_experience.schemas.plan import ShortlistOption


async def test_event_validation_allows_feasible_times_across_utc_midnight():
    from datetime import timedelta
    from types import SimpleNamespace

    from fan_experience.agent.guardrails import validate_against_event

    event = SimpleNamespace(
        venue_lat=34.043, venue_lng=-118.267,
        doors_open=datetime(2026, 7, 2, 2, 0, tzinfo=timezone.utc),
    )
    proposal = _make_proposal(["rest-002", "rest-003"])
    for option in proposal.shortlist:
        option.dining_time = datetime(2026, 7, 1, 16, 30, tzinfo=timezone(timedelta(hours=-7)))
    assert await validate_against_event(proposal, event, 2) == []


# building proposal fixtures with controllable recommendation counts
def _make_proposal(candidate_ids=None, recommended_count=1):
    options = []
    ids = candidate_ids or ["rest-001", "rest-002"]
    for i, candidate_id in enumerate(ids):
        options.append(
            ShortlistOption(
                candidate_id=candidate_id,
                recommended=(i < recommended_count),
                dining_time=datetime(2026, 7, 1, 17, 30, tzinfo=timezone.utc),
                option_reasoning="Good option",
            )
        )
    return PlanProposal(
        shortlist=options,
        plan_summary="Dinner plan",
        conversation_history=[],
    )


# ensuring a clean proposal passes all hard validations
@pytest.mark.parametrize("ids", [["rest-001", "rest-002"], ["rest-001", "rest-002", "rest-003"]])
def test_valid_proposal_passes(ids):
    known_ids = {"rest-001", "rest-002", "rest-003"}
    feasible_ids = known_ids
    proposal = _make_proposal(ids)
    errors = validate_proposal(proposal, known_ids, feasible_ids)
    assert errors == []


@pytest.mark.parametrize("ids", [["rest-001"], ["rest-001", "rest-002", "rest-003", "rest-004"]])
def test_rejects_wrong_shortlist_size(ids):
    errors = validate_proposal(_make_proposal(ids), set(ids), set(ids))
    assert any("2-3" in error for error in errors)


def test_rejects_duplicate_candidate_ids():
    errors = validate_proposal(_make_proposal(["rest-001", "rest-001"]), {"rest-001"}, {"rest-001"})
    assert any("distinct" in error for error in errors)


# rejecting candidate ids the agent did not receive from tools
def test_rejects_unknown_candidate_id():
    known_ids = {"rest-001"}
    feasible_ids = {"rest-001"}
    proposal = _make_proposal(["rest-001", "rest-999"])
    errors = validate_proposal(proposal, known_ids, feasible_ids)
    assert any("rest-999" in error for error in errors)


# rejecting options that were not feasible per deterministic timing checks
def test_rejects_infeasible_candidate():
    known_ids = {"rest-001", "rest-002"}
    feasible_ids = {"rest-001"}
    proposal = _make_proposal(["rest-001", "rest-002"])
    errors = validate_proposal(proposal, known_ids, feasible_ids)
    assert any("feasible" in error.lower() for error in errors)


# rejecting proposals that recommend nothing
def test_rejects_zero_recommended():
    known_ids = {"rest-001", "rest-002"}
    feasible_ids = {"rest-001", "rest-002"}
    proposal = _make_proposal(["rest-001", "rest-002"], recommended_count=0)
    errors = validate_proposal(proposal, known_ids, feasible_ids)
    assert any("recommended" in error.lower() for error in errors)


# rejecting proposals that recommend more than one option
def test_rejects_multiple_recommended():
    known_ids = {"rest-001", "rest-002"}
    feasible_ids = {"rest-001", "rest-002"}
    proposal = _make_proposal(["rest-001", "rest-002"], recommended_count=2)
    errors = validate_proposal(proposal, known_ids, feasible_ids)
    assert any("recommended" in error.lower() for error in errors)


# rejecting proposals with an empty shortlist
def test_rejects_empty_shortlist():
    known_ids = {"rest-001"}
    feasible_ids = {"rest-001"}
    proposal = PlanProposal(
        shortlist=[],
        plan_summary="Plan",
        conversation_history=[],
    )
    errors = validate_proposal(proposal, known_ids, feasible_ids)
    assert any("empty" in error.lower() or "shortlist" in error.lower() for error in errors)
