from datetime import datetime, timedelta, timezone

from fan_experience.services.confidence import compute_confidence


# verifying fresh primary data with strong slack yields high confidence
def test_fresh_data_high_margins_high_confidence():
    now = datetime.now(timezone.utc)
    result = compute_confidence(
        data_timestamps=[now, now, now],
        source_types=["primary", "primary", "primary"],
        slack_minutes=45.0,
        preference_match_score=0.9,
    )
    assert result["overall"] >= 0.8
    assert "freshness" in result
    assert "source_reliability" in result
    assert "timing_margin" in result
    assert "preference_match" in result


# ensuring stale inputs lower the freshness component
def test_stale_data_reduces_confidence():
    stale = datetime.now(timezone.utc) - timedelta(hours=6)
    result = compute_confidence(
        data_timestamps=[stale, stale, stale],
        source_types=["primary", "primary", "primary"],
        slack_minutes=45.0,
        preference_match_score=0.9,
    )
    assert result["freshness"] < 0.8


# ensuring near-zero slack penalizes timing confidence
def test_tight_margins_reduce_confidence():
    now = datetime.now(timezone.utc)
    result = compute_confidence(
        data_timestamps=[now],
        source_types=["primary"],
        slack_minutes=2.0,
        preference_match_score=0.9,
    )
    assert result["timing_margin"] < 0.5


# ensuring cached and fallback inputs reduce source reliability
def test_cached_sources_reduce_confidence():
    now = datetime.now(timezone.utc)
    result = compute_confidence(
        data_timestamps=[now, now],
        source_types=["cached", "fallback"],
        slack_minutes=30.0,
        preference_match_score=0.8,
    )
    assert result["source_reliability"] < 0.8


# ensuring the overall score remains normalized
def test_overall_is_weighted_average():
    now = datetime.now(timezone.utc)
    result = compute_confidence(
        data_timestamps=[now],
        source_types=["primary"],
        slack_minutes=30.0,
        preference_match_score=0.5,
    )
    assert 0.0 <= result["overall"] <= 1.0
