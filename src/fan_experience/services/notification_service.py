import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session as SyncSession

from fan_experience.db.models import Notification, NotificationType


# persisting plan notifications and read state for the user experience.
class NotificationService:
    def __init__(self, session: SyncSession):
        self._session = session

    def create(
        self,
        plan_id: uuid.UUID,
        notification_type: NotificationType,
        message: str,
    ) -> Notification:
        notification = Notification(
            plan_id=plan_id,
            type=notification_type,
            message=message,
        )
        self._session.add(notification)
        self._session.commit()
        return notification

    def list_for_plan(self, plan_id: uuid.UUID) -> list[Notification]:
        return list(
            self._session.execute(
                select(Notification)
                .where(Notification.plan_id == plan_id)
                .order_by(Notification.created_at.desc())
            ).scalars()
        )

    def mark_read(self, notification_id: uuid.UUID) -> None:
        notification = self._session.get(Notification, notification_id)
        if notification is None:
            raise ValueError(f"Notification {notification_id} not found")
        notification.read_at = datetime.now(timezone.utc)
        self._session.commit()
