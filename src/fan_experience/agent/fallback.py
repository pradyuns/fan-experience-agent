from datetime import datetime, timezone

from fan_experience.schemas.agent import PlanProposal
from fan_experience.schemas.plan import ShortlistOption


# building a deterministic shortlist from top-rated feasible candidates.
def build_fallback_proposal(
    candidates: list[dict],
    feasibility: dict[str, dict],
) -> PlanProposal:
    feasible_candidates = [
        candidate
        for candidate in candidates
        if feasibility.get(candidate["id"], {}).get("is_feasible", False)
    ]
    feasible_candidates.sort(key=lambda candidate: candidate.get("rating", 0), reverse=True)
    top_candidates = feasible_candidates[:3]

    shortlist = []
    fallback_time = datetime.now(timezone.utc).isoformat()
    for index, candidate in enumerate(top_candidates):
        feasibility_data = feasibility[candidate["id"]]
        dining_time = feasibility_data.get("dining_end_time", fallback_time)
        shortlist.append(
            ShortlistOption(
                candidate_id=candidate["id"],
                recommended=(index == 0),
                dining_time=dining_time,
                option_reasoning=f"{candidate['name']} - rated {candidate.get('rating', 'N/A')}",
            )
        )

    return PlanProposal(
        shortlist=shortlist,
        plan_summary=(
            f"Auto-selected: {top_candidates[0]['name']}"
            if top_candidates
            else "No feasible options found"
        ),
        conversation_history=[],
    )
