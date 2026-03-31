from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from celery import signals
from opentelemetry import context as otel_context, trace
from opentelemetry.trace import SpanKind, Status, StatusCode

from fan_experience.telemetry.context import bind_context, reset_context, set_context_values
from fan_experience.telemetry.logging import emit_event, get_logger
from fan_experience.telemetry.metrics import (
    record_celery_task,
    record_celery_task_duration,
)
from fan_experience.telemetry.tracing import (
    current_trace_id,
    extract_context,
    get_tracer,
    inject_context,
    set_span_attributes,
)

_HEADERS = {
    "request_id": "fan-request-id",
    "plan_id": "fan-plan-id",
    "purchase_id": "fan-purchase-id",
    "user_id": "fan-user-id",
}
_SIGNALS_REGISTERED = False
_LOGGER = get_logger(__name__)


@dataclass
class ActiveTaskSpan:
    span: Any
    context_token: object
    context_tokens: dict[str, Any]
    started_at: float
    task_name: str


_ACTIVE_TASKS: dict[str, ActiveTaskSpan] = {}


def inject_publish_headers(headers: dict[str, Any] | None = None) -> dict[str, Any]:
    carrier = inject_context(headers)
    from fan_experience.telemetry.context import get_context_values

    current_context = get_context_values()
    for field, header_name in _HEADERS.items():
        value = current_context.get(field)
        if value is not None:
            carrier[header_name] = value
    return carrier


def begin_task_span(
    *,
    task_id: str,
    task_name: str,
    headers: dict[str, Any] | None = None,
) -> None:
    extracted_context = extract_context(headers or {})
    tracer = get_tracer(__name__)
    span = tracer.start_span(task_name, context=extracted_context, kind=SpanKind.CONSUMER)
    context_token = otel_context.attach(trace.set_span_in_context(span, extracted_context))
    context_tokens = set_context_values(
        request_id=(headers or {}).get(_HEADERS["request_id"]),
        plan_id=(headers or {}).get(_HEADERS["plan_id"]),
        purchase_id=(headers or {}).get(_HEADERS["purchase_id"]),
        user_id=(headers or {}).get(_HEADERS["user_id"]),
        task_id=task_id,
        trace_id=current_trace_id(),
    )

    set_span_attributes(
        span,
        **{
            "celery.task_id": task_id,
            "celery.task_name": task_name,
            "request.id": (headers or {}).get(_HEADERS["request_id"]),
            "plan.id": (headers or {}).get(_HEADERS["plan_id"]),
            "purchase.id": (headers or {}).get(_HEADERS["purchase_id"]),
            "user.id": (headers or {}).get(_HEADERS["user_id"]),
        },
    )
    _ACTIVE_TASKS[task_id] = ActiveTaskSpan(
        span=span,
        context_token=context_token,
        context_tokens=context_tokens,
        started_at=time.perf_counter(),
        task_name=task_name,
    )
    emit_event(
        _LOGGER,
        "celery.task.started",
        task_id=task_id,
        task_name=task_name,
        status="started",
    )


def record_task_failure(*, task_id: str, task_name: str, exception: BaseException) -> None:
    active = _ACTIVE_TASKS.get(task_id)
    if active is not None:
        active.span.record_exception(exception)
        active.span.set_status(Status(StatusCode.ERROR))

    record_celery_task(task_name, "failure")
    emit_event(
        _LOGGER,
        "celery.task.failed",
        level=logging.ERROR,
        task_id=task_id,
        task_name=task_name,
        status="failure",
        error_type=type(exception).__name__,
    )


def finish_task_span(*, task_id: str, state: str | None = None) -> None:
    active = _ACTIVE_TASKS.pop(task_id, None)
    if active is None:
        return

    duration_seconds = time.perf_counter() - active.started_at
    record_celery_task_duration(active.task_name, duration_seconds)
    result = "success" if state == "SUCCESS" else "failure"
    if result == "success":
        record_celery_task(active.task_name, result)
        active.span.set_status(Status(StatusCode.OK))
    else:
        active.span.set_status(Status(StatusCode.ERROR))

    set_span_attributes(
        active.span,
        **{
            "celery.state": state or "UNKNOWN",
            "duration.ms": round(duration_seconds * 1000, 3),
        },
    )
    emit_event(
        _LOGGER,
        "celery.task.finished",
        task_id=task_id,
        task_name=active.task_name,
        status=result,
        duration_ms=round(duration_seconds * 1000, 3),
    )

    active.span.end()
    otel_context.detach(active.context_token)
    reset_context(active.context_tokens)


def register_celery_signal_handlers() -> None:
    global _SIGNALS_REGISTERED
    if _SIGNALS_REGISTERED:
        return

    @signals.before_task_publish.connect(weak=False)
    def _before_task_publish(headers=None, **kwargs):
        if headers is None:
            return
        headers.update(inject_publish_headers(headers))

    @signals.task_prerun.connect(weak=False)
    def _task_prerun(task_id=None, task=None, **kwargs):
        request_headers = dict(getattr(task.request, "headers", {}) or {})
        begin_task_span(
            task_id=task_id,
            task_name=task.name,
            headers=request_headers,
        )

    @signals.task_postrun.connect(weak=False)
    def _task_postrun(task_id=None, state=None, **kwargs):
        finish_task_span(task_id=task_id, state=state)

    @signals.task_failure.connect(weak=False)
    def _task_failure(task_id=None, sender=None, exception=None, **kwargs):
        if exception is None:
            return
        task_name = getattr(sender, "name", "unknown")
        record_task_failure(
            task_id=task_id,
            task_name=task_name,
            exception=exception,
        )

    _SIGNALS_REGISTERED = True

