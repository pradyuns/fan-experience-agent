import uuid
from datetime import datetime

from pydantic import BaseModel

from fan_experience.db.models import ReservationStatus


# book/change/cancel preview before committing
class ReservationPreviewRequest(BaseModel):
    action: str
    candidate_id: str
    dining_time: datetime
    party_size: int


class ReservationPreviewResponse(BaseModel):
    preview_id: uuid.UUID
    action: str
    restaurant_name: str
    dining_time: datetime
    party_size: int
    cancellation_policy: str | None
    deposit_required: bool
    idempotency_key: str
    status: ReservationStatus


# confirms a previously previewed reservation
class ReservationConfirmRequest(BaseModel):
    idempotency_key: str
