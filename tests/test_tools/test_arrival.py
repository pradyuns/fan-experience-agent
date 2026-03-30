import pytest

from fan_experience.tools.arrival import DINING_DURATIONS, estimate_arrival_and_slack


# verifying dining duration categories stay ordered by service length
def test_dining_duration_lookup_table():
    assert "fast_casual" in DINING_DURATIONS
    assert "casual_dining" in DINING_DURATIONS
    assert "fine_dining" in DINING_DURATIONS
    assert DINING_DURATIONS["fast_casual"] < DINING_DURATIONS["casual_dining"]
    assert DINING_DURATIONS["casual_dining"] < DINING_DURATIONS["fine_dining"]


@pytest.mark.asyncio
async def test_feasible_casual_dining():
    result = await estimate_arrival_and_slack(
        restaurant_coords=(34.050, -118.260),
        venue_coords=(34.043, -118.267),
        restaurant_category="casual_dining",
        dining_start_time="2026-07-01T17:00:00+00:00",
        event_doors_open="2026-07-01T18:30:00+00:00",
        mode="walking",
    )
    d = result.data
    assert d["is_feasible"] is True
    assert d["dining_duration_minutes"] == DINING_DURATIONS["casual_dining"]
    assert "travel_minutes" in d
    assert "buffer_minutes" in d
    assert "slack_minutes" in d
    assert "recommended_departure_time" in d
    assert "dining_end_time" in d


@pytest.mark.asyncio
async def test_infeasible_fine_dining_tight_window():
    result = await estimate_arrival_and_slack(
        restaurant_coords=(34.050, -118.260),
        venue_coords=(34.043, -118.267),
        restaurant_category="fine_dining",
        dining_start_time="2026-07-01T18:00:00+00:00",
        event_doors_open="2026-07-01T18:30:00+00:00",
        mode="walking",
    )
    d = result.data
    assert d["is_feasible"] is False


@pytest.mark.asyncio
async def test_fast_casual_quick_turnaround():
    result = await estimate_arrival_and_slack(
        restaurant_coords=(34.043, -118.267),
        venue_coords=(34.043, -118.267),
        restaurant_category="fast_casual",
        dining_start_time="2026-07-01T18:00:00+00:00",
        event_doors_open="2026-07-01T18:30:00+00:00",
        mode="walking",
    )
    d = result.data
    assert d["dining_duration_minutes"] == 25
    assert d["is_feasible"] is True
