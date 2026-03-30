import pytest

from fan_experience.tools.events import get_event_details


@pytest.mark.asyncio
async def test_get_event_details():
    result = await get_event_details(event_id="event-001")
    assert result.source is not None
    d = result.data
    assert "venue_name" in d
    assert "venue_lat" in d
    assert "venue_lng" in d
    assert "event_time" in d
    assert "doors_open" in d
    assert "genre" in d
    assert "expected_attendance" in d
