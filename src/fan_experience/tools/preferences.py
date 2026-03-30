from fan_experience.tools.base import ToolResult

_MOCK_PREFERENCES = {
    "user-001": {
        "cuisine_preferences": [
            {"cuisine": "italian", "weight": 0.9, "confidence": 0.8},
            {"cuisine": "japanese", "weight": 0.7, "confidence": 0.6},
        ],
        "price_range": "medium",
        "noise_preference": "moderate",
        "dietary_restrictions": [],
        "past_ratings": [{"restaurant_id": "rest-001", "rating": 5}],
        "preferred_vibe": ["date-night", "trendy"],
    },
}

_DEFAULT_PREFERENCES = {
    "cuisine_preferences": [],
    "price_range": "medium",
    "noise_preference": "any",
    "dietary_restrictions": [],
    "past_ratings": [],
    "preferred_vibe": [],
}


# returning stored or default preference signals for a fan.
async def get_user_preferences(user_id: str) -> ToolResult:
    data = _MOCK_PREFERENCES.get(user_id, _DEFAULT_PREFERENCES)
    return ToolResult(data=data, source="mock_preference_store")
