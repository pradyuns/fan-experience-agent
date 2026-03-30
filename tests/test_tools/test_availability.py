import pytest

from fan_experience.tools.availability import check_reservation_availability


@pytest.mark.asyncio
async def test_check_availability_available():
    result = await check_reservation_availability(
        restaurant_id="rest-001",
        party_size=2,
        date="2026-07-01",
        time="17:30",
    )
    d = result.data
    assert "available" in d
    assert "available_slots" in d
    assert "deposit_required" in d
    assert "cancellation_policy" in d
