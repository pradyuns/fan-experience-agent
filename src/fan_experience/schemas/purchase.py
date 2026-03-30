import uuid
from datetime import datetime

from pydantic import BaseModel


class PurchaseWebhook(BaseModel):
    purchase_id: str
    user_id: uuid.UUID
    event_id: uuid.UUID
    ticket_count: int
    purchased_at: datetime
    hmac_signature: str
