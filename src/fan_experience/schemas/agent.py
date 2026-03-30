import uuid

from pydantic import BaseModel, Field

from fan_experience.schemas.plan import ShortlistOption


class AgentContext(BaseModel):
    plan_id: uuid.UUID
    user_id: uuid.UUID
    event_id: uuid.UUID
    ticket_count: int
    refinement_preferences: dict | None = None


class PlanProposal(BaseModel):
    shortlist: list[ShortlistOption]
    plan_summary: str
    conversation_history: list = Field(default_factory=list)
