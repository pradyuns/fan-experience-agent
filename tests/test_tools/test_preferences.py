import pytest

from fan_experience.tools.preferences import get_user_preferences


@pytest.mark.asyncio
async def test_get_user_preferences():
    result = await get_user_preferences(user_id="user-001")
    d = result.data
    assert "cuisine_preferences" in d
    assert "price_range" in d
    assert "noise_preference" in d
    assert "dietary_restrictions" in d
