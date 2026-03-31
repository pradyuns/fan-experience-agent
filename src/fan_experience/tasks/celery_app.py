from celery import Celery

from fan_experience.config import settings


celery_app = Celery(
    "fan_experience",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# importing task modules ensures Celery registers decorated tasks at worker startup.
from fan_experience.tasks import plan_generation  # noqa: E402,F401
