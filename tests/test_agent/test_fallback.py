from fan_experience.agent.fallback import build_fallback_proposal


# ensuring the fallback ranks feasible candidates by rating
def test_fallback_selects_top_candidates():
    candidates = [
        {"id": "rest-001", "name": "Bestia", "rating": 4.6, "category": "fine_dining"},
        {"id": "rest-002", "name": "Sugarfish", "rating": 4.5, "category": "casual_dining"},
        {"id": "rest-003", "name": "In-N-Out", "rating": 4.2, "category": "fast_casual"},
    ]
    feasibility = {
        "rest-001": {"is_feasible": True, "dining_end_time": "2026-07-01T17:30:00Z"},
        "rest-002": {"is_feasible": True, "dining_end_time": "2026-07-01T17:50:00Z"},
        "rest-003": {"is_feasible": True, "dining_end_time": "2026-07-01T18:25:00Z"},
    }
    proposal = build_fallback_proposal(candidates, feasibility)
    assert len(proposal.shortlist) >= 2
    recommended = [option for option in proposal.shortlist if option.recommended]
    assert len(recommended) == 1
    assert recommended[0].candidate_id == "rest-001"


# ensuring infeasible candidates are omitted from fallback output
def test_fallback_excludes_infeasible():
    candidates = [
        {"id": "rest-001", "name": "Bestia", "rating": 4.6, "category": "fine_dining"},
        {"id": "rest-002", "name": "Sugarfish", "rating": 4.5, "category": "casual_dining"},
    ]
    feasibility = {
        "rest-001": {"is_feasible": False},
        "rest-002": {"is_feasible": True, "dining_end_time": "2026-07-01T17:50:00Z"},
    }
    proposal = build_fallback_proposal(candidates, feasibility)
    candidate_ids = [option.candidate_id for option in proposal.shortlist]
    assert "rest-001" not in candidate_ids
    assert "rest-002" in candidate_ids
