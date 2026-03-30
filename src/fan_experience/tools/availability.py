from fan_experience.tools.base import ToolResult

_MOCK_AVAILABILITY = {
    "rest-001": {
        "available": True,
        "available_slots": ["17:00", "17:30", "18:00"],
        "deposit_required": False,
        "cancellation_policy": "Free cancellation up to 2 hours before",
    },
    "rest-002": {
        "available": True,
        "available_slots": ["17:00", "17:30"],
        "deposit_required": False,
        "cancellation_policy": "Free cancellation up to 1 hour before",
    },
    "rest-003": {
        "available": True,
        "available_slots": ["17:00", "17:30", "18:00", "18:30", "19:00"],
        "deposit_required": False,
        "cancellation_policy": "No reservation needed",
    },
    "rest-004": {
        "available": True,
        "available_slots": ["18:00", "18:30"],
        "deposit_required": True,
        "cancellation_policy": "48-hour cancellation policy, $25 deposit",
    },
}


# returning reservation availability details for a mock restaurant provider.
async def check_reservation_availability(
    restaurant_id: str,
    party_size: int,
    date: str,
    time: str,
) -> ToolResult:
    del party_size, date, time

    data = _MOCK_AVAILABILITY.get(
        restaurant_id,
        {
            "available": False,
            "available_slots": [],
            "deposit_required": False,
            "cancellation_policy": None,
        },
    )
    return ToolResult(data=data, source="mock_reservation_api")
