from datetime import datetime, timezone

from fan_experience.agent.guardrails import validate_proposal
from fan_experience.schemas.agent import PlanProposal
from fan_experience.schemas.plan import ShortlistOption


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
def test_valid_proposal_passes():
    known_ids = {"rest-001", "rest-002", "rest-003"}
    feasible_ids = {"rest-001", "rest-002"}
    proposal = _make_proposal(["rest-001", "rest-002"])
    errors = validate_proposal(proposal, known_ids, feasible_ids)
    assert errors == []


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
