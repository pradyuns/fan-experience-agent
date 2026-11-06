from datetime import timezone

from fan_experience.schemas.agent import PlanProposal
from fan_experience.tools.arrival import DINING_DURATIONS, _BUFFER_MINUTES
from fan_experience.tools.restaurants import search_restaurants


async def validate_against_event(proposal, event, ticket_count: int) -> list[str]:
    """Check a proposal against a fresh candidate search and event timing.

    The current mock provider supplies distance rather than coordinates. Estimate
    walking at the mock directions provider's 4.8 km/h, with its 10-minute grace.
    """
    doors = event.doors_open
    if doors.tzinfo is None:
        doors = doors.replace(tzinfo=timezone.utc)
    doors = doors.astimezone(timezone.utc)
    result = await search_restaurants(
        location=(event.venue_lat, event.venue_lng),
        radius_km=5,
        cuisine_types=None,
        party_size=ticket_count,
        date=doors.date().isoformat(),
        time_range=("00:00", "23:59"),
    )
    candidates = {candidate["id"]: candidate for candidate in result.data}
    errors = validate_proposal(proposal, set(candidates), set(candidates))
    for option in proposal.shortlist:
        candidate = candidates.get(option.candidate_id)
        if candidate is None:
            continue
        start = option.dining_time
        if start.tzinfo is None:
            errors.append(f"Candidate {option.candidate_id} needs a timezone-aware dining time")
            continue
        start = start.astimezone(timezone.utc)
        duration = DINING_DURATIONS.get(candidate["category"], 45)
        travel = round(candidate["distance_km"] / 4.8 * 60, 1)
        slack = (doors - start).total_seconds() / 60 - duration - travel
        if slack < -_BUFFER_MINUTES:
            errors.append(f"Candidate {option.candidate_id} is not feasible per arrival estimate")
    return errors


# validating agent output against known ids and deterministic feasibility.
def validate_proposal(
    proposal: PlanProposal,
    known_candidate_ids: set[str],
    feasible_candidate_ids: set[str],
) -> list[str]:
    errors = []

    if not 2 <= len(proposal.shortlist) <= 3:
        errors.append("Shortlist must contain 2-3 options")

    candidate_ids = [option.candidate_id for option in proposal.shortlist]
    if len(candidate_ids) != len(set(candidate_ids)):
        errors.append("Shortlist must contain distinct candidate IDs")

    for option in proposal.shortlist:
        if option.candidate_id not in known_candidate_ids:
            errors.append(f"Unknown candidate_id: {option.candidate_id}")
        if option.candidate_id not in feasible_candidate_ids:
            errors.append(
                f"Candidate {option.candidate_id} is not feasible per arrival estimate"
            )

    recommended_count = sum(1 for option in proposal.shortlist if option.recommended)
    if recommended_count != 1:
        errors.append(f"Expected exactly 1 recommended option, got {recommended_count}")

    return errors
