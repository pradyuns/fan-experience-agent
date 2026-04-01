from celery import Celery

from fan_experience.config import settings
from fan_experience.telemetry.celery import register_celery_signal_handlers
from fan_experience.telemetry.logging import configure_logging
from fan_experience.telemetry.metrics import init_metrics
from fan_experience.telemetry.tracing import init_tracing

configure_logging()
init_tracing()
init_metrics()


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
    worker_hijack_root_logger=False,
    worker_redirect_stdouts=False,
)
register_celery_signal_handlers()

# importing task modules ensures Celery registers decorated tasks at worker startup.
from fan_experience.tasks import adaptation  # noqa: E402,F401
from fan_experience.tasks import plan_generation  # noqa: E402,F401
