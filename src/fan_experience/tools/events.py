from fan_experience.tools.base import ToolResult

# hard-coded event fixtures for dev/testing
_MOCK_EVENTS = {
    "event-001": {
        "venue_name": "Crypto.com Arena",
        "venue_address": "1111 S Figueroa St, Los Angeles, CA",
        "venue_lat": 34.043,
        "venue_lng": -118.267,
        "event_time": "2026-07-01T20:00:00Z",
        "doors_open": "2026-07-01T18:30:00Z",
        "genre": "basketball",
        "expected_attendance": 18000,
    },
    "event-002": {
        "venue_name": "Hollywood Bowl",
        "venue_address": "2301 N Highland Ave, Los Angeles, CA",
        "venue_lat": 34.112,
        "venue_lng": -118.339,
        "event_time": "2026-08-15T19:30:00Z",
        "doors_open": "2026-08-15T17:30:00Z",
        "genre": "music",
        "expected_attendance": 17500,
    },
}


async def get_event_details(event_id: str) -> ToolResult:
    data = _MOCK_EVENTS.get(event_id)
    if data is None:
        return ToolResult(
            data={"error": f"Event {event_id} not found"},
            source="mock_event_api",
        )
    return ToolResult(data=data, source="mock_event_api")
