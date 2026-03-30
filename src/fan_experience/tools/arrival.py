from datetime import datetime, timedelta

from fan_experience.tools.base import ToolResult
from fan_experience.tools.directions import get_directions

# defining code-owned dining duration defaults by restaurant category.
DINING_DURATIONS: dict[str, int] = {
    "fast_casual": 25,
    "casual_dining": 50,
    "fine_dining": 100,
    "bar_snacks": 30,
    "food_truck": 15,
}

_BUFFER_MINUTES = 10


# computing deterministic dining feasibility and venue arrival slack.
async def estimate_arrival_and_slack(
    restaurant_coords: tuple[float, float],
    venue_coords: tuple[float, float],
    restaurant_category: str,
    dining_start_time: str,
    event_doors_open: str,
    mode: str,
) -> ToolResult:
    dining_duration = DINING_DURATIONS.get(restaurant_category, 45)

    dining_start = datetime.fromisoformat(dining_start_time)
    doors_open = datetime.fromisoformat(event_doors_open)
    dining_end = dining_start + timedelta(minutes=dining_duration)

    directions = await get_directions(
        origin=restaurant_coords,
        destination=venue_coords,
        mode=mode,
        _departure_time=dining_end.isoformat(),
    )
    travel_minutes = directions.data["duration_minutes"]

    recommended_departure = dining_end
    arrival_time = dining_end + timedelta(minutes=travel_minutes)
    slack_minutes = (doors_open - arrival_time).total_seconds() / 60
    is_feasible = slack_minutes >= -_BUFFER_MINUTES

    data = {
        "travel_minutes": round(travel_minutes, 1),
        "dining_duration_minutes": dining_duration,
        "buffer_minutes": _BUFFER_MINUTES,
        "slack_minutes": round(slack_minutes, 1),
        "is_feasible": is_feasible,
        "recommended_departure_time": recommended_departure.isoformat(),
        "dining_end_time": dining_end.isoformat(),
    }
    return ToolResult(data=data, source="deterministic_calculator")
