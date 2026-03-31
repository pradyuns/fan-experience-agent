import uuid
from datetime import timezone

from fan_experience.db.engine import async_session_factory
from fan_experience.db.models import Event
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
    if data is not None:
        return ToolResult(data=data, source="mock_event_api")

    try:
        parsed_id = uuid.UUID(event_id)
    except ValueError:
        return ToolResult(
            data={"error": f"Event {event_id} not found"},
            source="mock_event_api",
        )

    async with async_session_factory() as session:
        event = await session.get(Event, parsed_id)

    if event is None:
        return ToolResult(
            data={"error": f"Event {event_id} not found"},
            source="mock_event_api",
        )

    return ToolResult(
        data={
            "venue_name": event.venue_name,
            "venue_address": event.venue_address,
            "venue_lat": event.venue_lat,
            "venue_lng": event.venue_lng,
            "event_time": event.event_time.astimezone(timezone.utc).isoformat(),
            "doors_open": event.doors_open.astimezone(timezone.utc).isoformat(),
            "genre": event.genre,
            "expected_attendance": 18000,
        },
        source="db_event_store",
    )
