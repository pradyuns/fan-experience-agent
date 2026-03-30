import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid


# defining the base class for all orm models.
class Base(DeclarativeBase):
    pass


# generating utc timestamps for default model fields.
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# generating uuid primary keys for new records.
def _new_uuid() -> uuid.UUID:
    return uuid.uuid4()


# defining plan lifecycle states stored in the database.
class PlanStatus(str, enum.Enum):
    GENERATING = "GENERATING"
    ACTIVE = "ACTIVE"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"


class ReservationStatus(str, enum.Enum):
    NONE = "NONE"
    PREVIEW_PENDING = "PREVIEW_PENDING"
    CONFIRMED = "CONFIRMED"
    CHANGE_PREVIEW_PENDING = "CHANGE_PREVIEW_PENDING"
    CHANGE_CONFIRMED = "CHANGE_CONFIRMED"
    CANCEL_PREVIEW_PENDING = "CANCEL_PREVIEW_PENDING"
    CANCELLED = "CANCELLED"


class NotificationType(str, enum.Enum):
    PLAN_CREATED = "PLAN_CREATED"
    PLAN_UPDATED = "PLAN_UPDATED"
    ACTION_REQUIRED = "ACTION_REQUIRED"
    RESERVATION_CONFIRMED = "RESERVATION_CONFIRMED"
    RESERVATION_CHANGED = "RESERVATION_CHANGED"
    RESERVATION_CANCELLED = "RESERVATION_CANCELLED"


class AdaptationResult(str, enum.Enum):
    NO_CHANGE = "NO_CHANGE"
    REPLAN_TRIGGERED = "REPLAN_TRIGGERED"
    HARD_TRIGGER = "HARD_TRIGGER"
    RATE_LIMITED = "RATE_LIMITED"


# storing core fan account details.
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# storing event and venue details tied to purchases.
class Event(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(500))
    venue_name: Mapped[str] = mapped_column(String(500))
    venue_address: Mapped[str] = mapped_column(String(1000))
    venue_lat: Mapped[float] = mapped_column(Float)
    venue_lng: Mapped[float] = mapped_column(Float)
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    doors_open: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    genre: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


# recording an external ticket purchase for a user and event.
class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("events.id"))
    purchase_id: Mapped[str] = mapped_column(String(255), unique=True)
    ticket_count: Mapped[int] = mapped_column(Integer)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    __table_args__ = (Index("ix_purchases_purchase_id", "purchase_id"),)


# tracking the overall plan lifecycle for a purchase.
class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    purchase_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("purchases.id"),
        unique=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("events.id"))
    status: Mapped[PlanStatus] = mapped_column(
        Enum(PlanStatus),
        default=PlanStatus.GENERATING,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )


# storing immutable plan snapshots for each revision.
class PlanVersion(Base):
    __tablename__ = "plan_versions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("plans.id"))
    version_number: Mapped[int] = mapped_column(Integer)
    payload_json: Mapped[dict] = mapped_column(JSON)
    confidence_score: Mapped[float] = mapped_column(Float)
    confidence_breakdown_json: Mapped[dict] = mapped_column(JSON)
    trigger_reason: Mapped[str] = mapped_column(String(100))
    agent_reasoning: Mapped[str] = mapped_column(Text)
    conversation_history_json: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (Index("ix_plan_versions_plan_id", "plan_id"),)


# storing reservation previews and confirmed booking metadata.
class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("plans.id"))
    restaurant_id: Mapped[str] = mapped_column(String(255))
    restaurant_name: Mapped[str] = mapped_column(String(500))
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus),
        default=ReservationStatus.NONE,
    )
    party_size: Mapped[int] = mapped_column(Integer)
    reservation_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    provider_confirmation_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True)
    previewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )


# recording fan-facing plan and reservation notifications.
class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("plans.id"))
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# storing learned user preference signals with confidence.
class UserPreference(Base):
    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    preference_type: Mapped[str] = mapped_column(String(50))
    value_json: Mapped[dict] = mapped_column(JSON)
    confidence: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        onupdate=_utcnow,
    )

    __table_args__ = (Index("ix_user_prefs_user_type", "user_id", "preference_type"),)


# recording each adaptation tick result for auditing and rate limits.
class AdaptationLog(Base):
    __tablename__ = "adaptation_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("plans.id"))
    tick_number: Mapped[int] = mapped_column(Integer)
    result: Mapped[AdaptationResult] = mapped_column(Enum(AdaptationResult))
    trigger_details_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (Index("ix_adaptation_logs_plan_id", "plan_id"),)
