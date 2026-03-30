import pytest

from fan_experience.tools.weather import get_weather


@pytest.mark.asyncio
async def test_get_weather():
    result = await get_weather(
        _location=(34.043, -118.267),
        _date="2026-07-01",
        _time="18:00",
    )
    d = result.data
    assert "temperature_f" in d
    assert "conditions" in d
    assert "precipitation_probability" in d
    assert "wind_speed_mph" in d
    assert "advisory_flags" in d
    assert result.source is not None
