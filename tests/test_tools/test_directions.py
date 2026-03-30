import pytest

from fan_experience.tools.directions import get_directions


@pytest.mark.asyncio
async def test_get_directions():
    result = await get_directions(
        origin=(34.050, -118.260),
        destination=(34.043, -118.267),
        mode="walking",
        departure_time="2026-07-01T18:30:00Z",
    )
    d = result.data
    assert "duration_minutes" in d
    assert "distance_km" in d
    assert "traffic_factor" in d
    assert "route_summary" in d
    assert result.source is not None
    assert result.freshness_timestamp is not None


@pytest.mark.asyncio
async def test_get_directions_driving():
    result = await get_directions(
        origin=(34.050, -118.260),
        destination=(34.043, -118.267),
        mode="driving",
        departure_time="2026-07-01T18:30:00Z",
    )
    d = result.data
    assert d["traffic_factor"] >= 1.0
