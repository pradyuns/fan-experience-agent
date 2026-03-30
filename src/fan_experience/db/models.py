import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON, Uuid


# sqlalchemy declarative base for all models
class Base(DeclarativeBase):
    pass


# default factories for timestamps and primary keys
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> uuid.UUID:
    return uuid.uuid4()


# -- enums --

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


# outcome of each adaptation-loop tick
class AdaptationResult(str, enum.Enum):
    NO_CHANGE = "NO_CHANGE"
    REPLAN_TRIGGERED = "REPLAN_TRIGGERED"
    HARD_TRIGGER = "HARD_TRIGGER"
    RATE_LIMITED = "RATE_LIMITED"


# -- tables --

class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255))
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


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


# links a user to a ticketed event
class Purchase(Base):
    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("users.id"))
    event_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("events.id"))
    purchase_id: Mapped[str] = mapped_column(String(255), unique=True)
    ticket_count: Mapped[int] = mapped_column(Integer)
    purchased_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


# one plan per purchase, tracks dining plan lifecycle
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


# immutable snapshot of a plan at a point in time
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


# restaurant reservation tied to a plan
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


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("plans.id"))
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# learned user preferences (cuisine, price, etc.)
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


# audit trail for each adaptation-loop evaluation
class AdaptationLog(Base):
    __tablename__ = "adaptation_logs"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=_new_uuid)
    plan_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("plans.id"))
    tick_number: Mapped[int] = mapped_column(Integer)
    result: Mapped[AdaptationResult] = mapped_column(Enum(AdaptationResult))
    trigger_details_json: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    __table_args__ = (Index("ix_adaptation_logs_plan_id", "plan_id"),)
