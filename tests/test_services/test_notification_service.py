import uuid

import pytest
from sqlalchemy import select

from fan_experience.db.models import Notification, NotificationType
from fan_experience.services.notification_service import NotificationService


def test_create_notification(active_plan):
    session, plan_id = active_plan
    service = NotificationService(session)

    notification = service.create(
        plan_id,
        NotificationType.PLAN_CREATED,
        "Your plan is ready!",
    )

    assert notification.type == NotificationType.PLAN_CREATED
    assert notification.read_at is None


def test_list_notifications(active_plan):
    session, plan_id = active_plan
    service = NotificationService(session)

    service.create(plan_id, NotificationType.PLAN_CREATED, "Plan ready")
    service.create(plan_id, NotificationType.ACTION_REQUIRED, "Please confirm")

    notifications = service.list_for_plan(plan_id)
    assert len(notifications) == 2
    assert notifications[0].created_at >= notifications[1].created_at


def test_mark_read(active_plan):
    session, plan_id = active_plan
    service = NotificationService(session)

    notification = service.create(plan_id, NotificationType.PLAN_CREATED, "Ready")
    service.mark_read(notification.id)

    reloaded = session.execute(
        select(Notification).where(Notification.id == notification.id)
    ).scalar_one()
    assert reloaded.read_at is not None


def test_mark_read_nonexistent(active_plan):
    session, _ = active_plan
    service = NotificationService(session)

    with pytest.raises(ValueError, match="not found"):
        service.mark_read(uuid.uuid4())
