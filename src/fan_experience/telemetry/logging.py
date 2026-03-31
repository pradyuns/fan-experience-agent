from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any

from fan_experience.config import Settings, settings
from fan_experience.telemetry.context import get_context_values
from fan_experience.telemetry.tracing import current_span_id, current_trace_id

_LOGGING_CONFIGURED = False
_LOG_FIELDS = (
    "service",
    "environment",
    "request_id",
    "trace_id",
    "span_id",
    "task_id",
    "plan_id",
    "purchase_id",
    "user_id",
    "tool_name",
    "route",
    "duration_ms",
    "status",
    "error_type",
    "method",
    "status_code",
    "task_name",
    "result",
    "action",
    "model",
    "round_index",
    "stop_reason",
    "response_has_tool_calls",
    "tick_number",
    "event_id",
    "result_source",
)


class TelemetryContextFilter(logging.Filter):
    def __init__(self, app_settings: Settings):
        super().__init__()
        self._settings = app_settings

    def filter(self, record: logging.LogRecord) -> bool:
        context_values = get_context_values()
        trace_id = current_trace_id() or context_values["trace_id"]
        span_id = current_span_id()

        setattr(record, "service", self._settings.telemetry_service_name)
        setattr(record, "environment", self._settings.telemetry_env)
        setattr(record, "request_id", getattr(record, "request_id", None) or context_values["request_id"])
        setattr(record, "trace_id", getattr(record, "trace_id", None) or trace_id)
        setattr(record, "span_id", getattr(record, "span_id", None) or span_id)
        setattr(record, "task_id", getattr(record, "task_id", None) or context_values["task_id"])
        setattr(record, "plan_id", getattr(record, "plan_id", None) or context_values["plan_id"])
        setattr(record, "purchase_id", getattr(record, "purchase_id", None) or context_values["purchase_id"])
        setattr(record, "user_id", getattr(record, "user_id", None) or context_values["user_id"])
        setattr(record, "tool_name", getattr(record, "tool_name", None) or context_values["tool_name"])
        setattr(record, "event", getattr(record, "event", None) or record.getMessage())
        if record.exc_info and not getattr(record, "error_type", None):
            setattr(record, "error_type", record.exc_info[0].__name__)

        for field in _LOG_FIELDS:
            if not hasattr(record, field):
                setattr(record, field, None)

        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "event": record.event,
        }

        for field in _LOG_FIELDS:
            value = getattr(record, field, None)
            if value is not None:
                payload[field] = value

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, default=str)


def configure_logging(app_settings: Settings = settings) -> None:
    global _LOGGING_CONFIGURED
    if _LOGGING_CONFIGURED:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    handler.addFilter(TelemetryContextFilter(app_settings))

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(app_settings.telemetry_log_level.upper())

    _LOGGING_CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def emit_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    logger.log(level, event, extra={"event": event, **fields})
