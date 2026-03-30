from fan_experience.schemas.agent import PlanProposal


# validating agent output against known ids and deterministic feasibility.
def validate_proposal(
    proposal: PlanProposal,
    known_candidate_ids: set[str],
    feasible_candidate_ids: set[str],
) -> list[str]:
    errors = []

    if len(proposal.shortlist) == 0:
        errors.append("Shortlist is empty and must contain 2-3 options")
        return errors

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
