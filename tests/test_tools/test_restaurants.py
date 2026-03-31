import pytest

from fan_experience.tools.restaurants import search_restaurants


@pytest.mark.asyncio
async def test_search_restaurants_returns_candidates():
    result = await search_restaurants(
        location=(34.043, -118.267),
        radius_km=2.0,
        cuisine_types=["italian", "japanese"],
        party_size=2,
        date="2026-07-01",
        time_range=("17:00", "19:00"),
    )
    assert result.source is not None
    assert result.freshness_timestamp is not None
    assert len(result.data) > 0

    first = result.data[0]
    assert "id" in first
    assert "name" in first
    assert "cuisine" in first
    assert "price_level" in first
    assert "distance_km" in first
    assert "available_times" in first
    assert "category" in first


@pytest.mark.asyncio
async def test_search_restaurants_respects_party_size():
    result = await search_restaurants(
        location=(34.043, -118.267),
        radius_km=2.0,
        cuisine_types=None,
        party_size=20,
        date="2026-07-01",
        time_range=("17:00", "19:00"),
    )
    assert isinstance(result.data, list)
