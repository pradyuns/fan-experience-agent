from collections.abc import Callable
from typing import Any

from fan_experience.tools.arrival import estimate_arrival_and_slack
from fan_experience.tools.availability import check_reservation_availability
from fan_experience.tools.directions import get_directions
from fan_experience.tools.events import get_event_details
from fan_experience.tools.preferences import get_user_preferences
from fan_experience.tools.restaurants import search_restaurants
from fan_experience.tools.weather import get_weather

_TOOL_DEFINITIONS = [
    {
        "name": "search_restaurants",
        "description": "Search for restaurants near a location. Returns candidates with id, name, cuisine, rating, price_level, distance_km, available_times, noise_level, vibe_tags, and category.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "Lat/lng coordinates [lat, lng]",
                },
                "radius_km": {"type": "number", "description": "Search radius in km"},
                "cuisine_types": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Filter by cuisine types, or null for all",
                    "nullable": True,
                },
                "party_size": {"type": "integer", "description": "Number of diners"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "time_range": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Time range [start_HH:MM, end_HH:MM]",
                },
            },
            "required": ["location", "radius_km", "party_size", "date", "time_range"],
        },
    },
    {
        "name": "get_event_details",
        "description": "Get event details including venue location, event time, doors open time, genre, and expected attendance.",
        "input_schema": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "Event identifier"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "get_weather",
        "description": "Get weather forecast for a location, date, and time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "location": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "[lat, lng]",
                },
                "date": {"type": "string", "description": "YYYY-MM-DD"},
                "time": {"type": "string", "description": "HH:MM"},
            },
            "required": ["location", "date", "time"],
        },
    },
    {
        "name": "get_directions",
        "description": "Get travel duration and route summary between two locations.",
        "input_schema": {
            "type": "object",
            "properties": {
                "origin": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "[lat, lng]",
                },
                "destination": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "[lat, lng]",
                },
                "mode": {"type": "string", "description": "walking, driving, or transit"},
                "departure_time": {
                    "type": "string",
                    "description": "ISO datetime for departure",
                },
            },
            "required": ["origin", "destination", "mode", "departure_time"],
        },
    },
    {
        "name": "estimate_arrival_and_slack",
        "description": "Compute dining feasibility, travel time, and slack before event doors open.",
        "input_schema": {
            "type": "object",
            "properties": {
                "restaurant_coords": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "[lat, lng]",
                },
                "venue_coords": {
                    "type": "array",
                    "items": {"type": "number"},
                    "description": "[lat, lng]",
                },
                "restaurant_category": {
                    "type": "string",
                    "description": "Restaurant service category",
                },
                "dining_start_time": {
                    "type": "string",
                    "description": "ISO datetime for dining start",
                },
                "event_doors_open": {
                    "type": "string",
                    "description": "ISO datetime when doors open",
                },
                "mode": {"type": "string", "description": "walking, driving, or transit"},
            },
            "required": [
                "restaurant_coords",
                "venue_coords",
                "restaurant_category",
                "dining_start_time",
                "event_doors_open",
                "mode",
            ],
        },
    },
    {
        "name": "get_user_preferences",
        "description": "Get current user dining preferences and prior ratings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "string", "description": "User identifier"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "check_reservation_availability",
        "description": "Check whether a restaurant has reservation slots for the requested party and time.",
        "input_schema": {
            "type": "object",
            "properties": {
                "restaurant_id": {
                    "type": "string",
                    "description": "Restaurant identifier",
                },
                "party_size": {"type": "integer", "description": "Number of diners"},
                "date": {"type": "string", "description": "Date in YYYY-MM-DD format"},
                "time": {"type": "string", "description": "Time in HH:MM format"},
            },
            "required": ["restaurant_id", "party_size", "date", "time"],
        },
    },
]

_TOOL_HANDLERS: dict[str, Callable[..., Any]] = {
    "search_restaurants": lambda **kw: search_restaurants(
        location=tuple(kw["location"]),
        radius_km=kw["radius_km"],
        cuisine_types=kw.get("cuisine_types"),
        party_size=kw["party_size"],
        date=kw["date"],
        time_range=tuple(kw["time_range"]),
    ),
    "get_event_details": lambda **kw: get_event_details(event_id=kw["event_id"]),
    "get_weather": lambda **kw: get_weather(
        location=tuple(kw["location"]),
        date=kw["date"],
        time=kw["time"],
    ),
    "get_directions": lambda **kw: get_directions(
        origin=tuple(kw["origin"]),
        destination=tuple(kw["destination"]),
        mode=kw["mode"],
        departure_time=kw["departure_time"],
    ),
    "estimate_arrival_and_slack": lambda **kw: estimate_arrival_and_slack(
        restaurant_coords=tuple(kw["restaurant_coords"]),
        venue_coords=tuple(kw["venue_coords"]),
        restaurant_category=kw["restaurant_category"],
        dining_start_time=kw["dining_start_time"],
        event_doors_open=kw["event_doors_open"],
        mode=kw["mode"],
    ),
    "get_user_preferences": lambda **kw: get_user_preferences(user_id=kw["user_id"]),
    "check_reservation_availability": lambda **kw: check_reservation_availability(
        restaurant_id=kw["restaurant_id"],
        party_size=kw["party_size"],
        date=kw["date"],
        time=kw["time"],
    ),
}


# exposing the tool list in the format expected by the agent layer
def get_tool_definitions() -> list[dict[str, Any]]:
    return list(_TOOL_DEFINITIONS)


# resolving a tool name to its implementation function
def get_tool_handler(name: str) -> Callable[..., Any] | None:
    return _TOOL_HANDLERS.get(name)
