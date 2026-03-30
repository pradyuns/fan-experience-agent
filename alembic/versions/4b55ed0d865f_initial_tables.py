"""initial tables"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "4b55ed0d865f"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# creating all initial application tables.
def upgrade() -> None:
    plan_status = postgresql.ENUM(
        "GENERATING",
        "ACTIVE",
        "FAILED",
        "EXPIRED",
        name="planstatus",
        create_type=False,
    )
    reservation_status = postgresql.ENUM(
        "NONE",
        "PREVIEW_PENDING",
        "CONFIRMED",
        "CHANGE_PREVIEW_PENDING",
        "CHANGE_CONFIRMED",
        "CANCEL_PREVIEW_PENDING",
        "CANCELLED",
        name="reservationstatus",
        create_type=False,
    )
    notification_type = postgresql.ENUM(
        "PLAN_CREATED",
        "PLAN_UPDATED",
        "ACTION_REQUIRED",
        "RESERVATION_CONFIRMED",
        "RESERVATION_CHANGED",
        "RESERVATION_CANCELLED",
        name="notificationtype",
        create_type=False,
    )
    adaptation_result = postgresql.ENUM(
        "NO_CHANGE",
        "REPLAN_TRIGGERED",
        "HARD_TRIGGER",
        "RATE_LIMITED",
        name="adaptationresult",
        create_type=False,
    )

    plan_status.create(op.get_bind(), checkfirst=True)
    reservation_status.create(op.get_bind(), checkfirst=True)
    notification_type.create(op.get_bind(), checkfirst=True)
    adaptation_result.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("timezone", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=500), nullable=False),
        sa.Column("venue_name", sa.String(length=500), nullable=False),
        sa.Column("venue_address", sa.String(length=1000), nullable=False),
        sa.Column("venue_lat", sa.Float(), nullable=False),
        sa.Column("venue_lng", sa.Float(), nullable=False),
        sa.Column("event_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("doors_open", sa.DateTime(timezone=True), nullable=False),
        sa.Column("genre", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "purchases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("purchase_id", sa.String(length=255), nullable=False),
        sa.Column("ticket_count", sa.Integer(), nullable=False),
        sa.Column("purchased_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("purchase_id"),
    )
    op.create_index("ix_purchases_purchase_id", "purchases", ["purchase_id"], unique=False)
    op.create_table(
        "plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("purchase_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("status", plan_status, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["events.id"]),
        sa.ForeignKeyConstraint(["purchase_id"], ["purchases.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("purchase_id"),
    )
    op.create_table(
        "plan_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("confidence_score", sa.Float(), nullable=False),
        sa.Column("confidence_breakdown_json", sa.JSON(), nullable=False),
        sa.Column("trigger_reason", sa.String(length=100), nullable=False),
        sa.Column("agent_reasoning", sa.Text(), nullable=False),
        sa.Column("conversation_history_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_plan_versions_plan_id", "plan_versions", ["plan_id"], unique=False)
    op.create_table(
        "reservations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("restaurant_id", sa.String(length=255), nullable=False),
        sa.Column("restaurant_name", sa.String(length=500), nullable=False),
        sa.Column("status", reservation_status, nullable=False),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("reservation_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("provider_confirmation_id", sa.String(length=255), nullable=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=False),
        sa.Column("previewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key"),
    )
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("type", notification_type, nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "user_preferences",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("preference_type", sa.String(length=50), nullable=False),
        sa.Column("value_json", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_prefs_user_type",
        "user_preferences",
        ["user_id", "preference_type"],
        unique=False,
    )
    op.create_table(
        "adaptation_logs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("plan_id", sa.Uuid(), nullable=False),
        sa.Column("tick_number", sa.Integer(), nullable=False),
        sa.Column("result", adaptation_result, nullable=False),
        sa.Column("trigger_details_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["plan_id"], ["plans.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_adaptation_logs_plan_id",
        "adaptation_logs",
        ["plan_id"],
        unique=False,
    )


# dropping all initial application tables in reverse order.
def downgrade() -> None:
    op.drop_index("ix_adaptation_logs_plan_id", table_name="adaptation_logs")
    op.drop_table("adaptation_logs")
    op.drop_index("ix_user_prefs_user_type", table_name="user_preferences")
    op.drop_table("user_preferences")
    op.drop_table("notifications")
    op.drop_table("reservations")
    op.drop_index("ix_plan_versions_plan_id", table_name="plan_versions")
    op.drop_table("plan_versions")
    op.drop_table("plans")
    op.drop_index("ix_purchases_purchase_id", table_name="purchases")
    op.drop_table("purchases")
    op.drop_table("events")
    op.drop_table("users")
    op.execute("DROP TYPE adaptationresult")
    op.execute("DROP TYPE notificationtype")
    op.execute("DROP TYPE reservationstatus")
    op.execute("DROP TYPE planstatus")
