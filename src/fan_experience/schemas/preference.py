import uuid
from datetime import datetime

from pydantic import BaseModel


class PreferenceResponse(BaseModel):
    id: uuid.UUID
    preference_type: str
    value: dict
    confidence: float
    updated_at: datetime


class UserPreferencesResponse(BaseModel):
    user_id: uuid.UUID
    preferences: list[PreferenceResponse]
