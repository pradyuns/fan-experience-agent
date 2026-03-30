import uuid
from datetime import datetime

from pydantic import BaseModel

from fan_experience.db.models import PlanStatus


# single restaurant candidate in a plan's shortlist
class ShortlistOption(BaseModel):
    candidate_id: str
    recommended: bool
    dining_time: datetime
    option_reasoning: str


class PlanVersionResponse(BaseModel):
    id: uuid.UUID
    version_number: int
    shortlist: list[ShortlistOption]
    confidence_score: float
    confidence_breakdown: dict
    trigger_reason: str
    agent_reasoning: str
    created_at: datetime


class PlanResponse(BaseModel):
    id: uuid.UUID
    status: PlanStatus
    current_version: PlanVersionResponse | None
    versions: list[PlanVersionResponse]
    created_at: datetime


# user refinement input (free-text or structured prefs)
class RefineRequest(BaseModel):
    message: str | None = None
    structured_preferences: dict | None = None


class FeedbackRequest(BaseModel):
    rating: int | None = None
    thumbs_up: bool | None = None
    comment: str | None = None
