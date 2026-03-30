from datetime import datetime, timezone

_WEIGHTS = {
    "freshness": 0.25,
    "source_reliability": 0.20,
    "timing_margin": 0.30,
    "preference_match": 0.25,
}

_SOURCE_SCORES = {
    "primary": 1.0,
    "cached": 0.6,
    "fallback": 0.3,
}

_MAX_FRESHNESS_HOURS = 4.0


# computing the overall confidence score and its factor breakdown.
def compute_confidence(
    data_timestamps: list[datetime],
    source_types: list[str],
    slack_minutes: float,
    preference_match_score: float,
) -> dict:
    freshness = _compute_freshness(data_timestamps)
    source_reliability = _compute_source_reliability(source_types)
    timing_margin = _compute_timing_margin(slack_minutes)
    preference_match = max(0.0, min(1.0, preference_match_score))

    overall = (
        _WEIGHTS["freshness"] * freshness
        + _WEIGHTS["source_reliability"] * source_reliability
        + _WEIGHTS["timing_margin"] * timing_margin
        + _WEIGHTS["preference_match"] * preference_match
    )

    return {
        "overall": round(overall, 3),
        "freshness": round(freshness, 3),
        "source_reliability": round(source_reliability, 3),
        "timing_margin": round(timing_margin, 3),
        "preference_match": round(preference_match, 3),
    }


# scoring freshness by age decay across all source timestamps.
def _compute_freshness(timestamps: list[datetime]) -> float:
    if not timestamps:
        return 0.0

    now = datetime.now(timezone.utc)
    scores = []
    for timestamp in timestamps:
        age_hours = (now - timestamp).total_seconds() / 3600
        score = max(0.0, 1.0 - (age_hours / _MAX_FRESHNESS_HOURS))
        scores.append(score)
    return sum(scores) / len(scores)


# averaging reliability weights for the set of source types used.
def _compute_source_reliability(source_types: list[str]) -> float:
    if not source_types:
        return 0.0

    scores = [_SOURCE_SCORES.get(source_type, 0.5) for source_type in source_types]
    return sum(scores) / len(scores)


# converting slack minutes into a normalized timing margin score.
def _compute_timing_margin(slack_minutes: float) -> float:
    if slack_minutes >= 30:
        return 1.0
    if slack_minutes <= 0:
        return 0.0
    return 0.3 + 0.7 * (slack_minutes / 30)
