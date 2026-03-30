from fan_experience.tools.base import ToolResult

_MOCK_RESTAURANTS = [
    {
        "id": "rest-001",
        "name": "Bestia",
        "cuisine": "italian",
        "rating": 4.6,
        "price_level": 3,
        "distance_km": 0.8,
        "available_times": ["17:00", "17:30", "18:00", "18:30"],
        "noise_level": "moderate",
        "vibe_tags": ["trendy", "date-night"],
        "category": "fine_dining",
    },
    {
        "id": "rest-002",
        "name": "Sugarfish",
        "cuisine": "japanese",
        "rating": 4.5,
        "price_level": 2,
        "distance_km": 1.2,
        "available_times": ["17:00", "17:30", "19:00"],
        "noise_level": "quiet",
        "vibe_tags": ["minimalist", "quick"],
        "category": "casual_dining",
    },
    {
        "id": "rest-003",
        "name": "In-N-Out Burger",
        "cuisine": "american",
        "rating": 4.2,
        "price_level": 1,
        "distance_km": 0.5,
        "available_times": ["17:00", "17:30", "18:00", "18:30", "19:00"],
        "noise_level": "loud",
        "vibe_tags": ["casual", "fast"],
        "category": "fast_casual",
    },
    {
        "id": "rest-004",
        "name": "Bavel",
        "cuisine": "middle_eastern",
        "rating": 4.7,
        "price_level": 3,
        "distance_km": 0.9,
        "available_times": ["18:00", "18:30"],
        "noise_level": "moderate",
        "vibe_tags": ["trendy", "group-friendly"],
        "category": "fine_dining",
    },
    {
        "id": "rest-005",
        "name": "Howlin' Ray's",
        "cuisine": "american",
        "rating": 4.4,
        "price_level": 1,
        "distance_km": 1.5,
        "available_times": ["17:00", "17:30", "18:00"],
        "noise_level": "loud",
        "vibe_tags": ["casual", "spicy"],
        "category": "fast_casual",
    },
]


# filtering mock restaurant candidates for the requested plan window.
async def search_restaurants(
    location: tuple[float, float],
    radius_km: float,
    cuisine_types: list[str] | None,
    party_size: int,
    date: str,
    time_range: tuple[str, str],
) -> ToolResult:
    del location, date, time_range

    candidates = _MOCK_RESTAURANTS.copy()

    if cuisine_types:
        candidates = [r for r in candidates if r["cuisine"] in cuisine_types]

    candidates = [r for r in candidates if r["distance_km"] <= radius_km]

    if party_size >= 8:
        candidates = [r for r in candidates if r["category"] != "fast_casual"]

    return ToolResult(data=candidates, source="mock_restaurant_api")
