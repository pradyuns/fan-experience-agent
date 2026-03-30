from fan_experience.tools.base import ToolResult


# returns static mock weather (clear, 78°F)
async def get_weather(
    _location: tuple[float, float],
    _date: str,
    _time: str,
) -> ToolResult:
    data = {
        "temperature_f": 78,
        "conditions": "clear",
        "precipitation_probability": 0.05,
        "wind_speed_mph": 8,
        "advisory_flags": [],
    }
    return ToolResult(data=data, source="mock_weather_api")
