from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from opentelemetry import metrics
from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource

from fan_experience.config import Settings, settings


@dataclass(frozen=True)
class MetricEvent:
    name: str
    value: int | float
    attributes: dict[str, Any]


@dataclass
class Instruments:
    http_requests_total: Any | None = None
    http_request_duration_seconds: Any | None = None
    webhook_events_total: Any | None = None
    celery_tasks_total: Any | None = None
    celery_task_duration_seconds: Any | None = None
    plan_generation_total: Any | None = None
    anthropic_requests_total: Any | None = None
    anthropic_request_duration_seconds: Any | None = None
    agent_tool_calls_total: Any | None = None
    agent_tool_failures_total: Any | None = None
    agent_tool_duration_seconds: Any | None = None
    reservation_actions_total: Any | None = None
    adaptation_ticks_total: Any | None = None


_METRICS_INITIALIZED = False
_INSTRUMENTS = Instruments()
_METRIC_EVENTS: list[MetricEvent] = []


def _resource(app_settings: Settings) -> Resource:
    return Resource.create(
        {
            "service.name": app_settings.telemetry_service_name,
            "deployment.environment": app_settings.telemetry_env,
        }
    )


def _signal_endpoint(base_endpoint: str, signal_name: str) -> str:
    trimmed = base_endpoint.rstrip("/")
    if trimmed.endswith(f"/v1/{signal_name}"):
        return trimmed
    return f"{trimmed}/v1/{signal_name}"


def init_metrics(app_settings: Settings = settings) -> None:
    global _METRICS_INITIALIZED
    if _METRICS_INITIALIZED:
        return

    if app_settings.telemetry_enabled:
        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(
                endpoint=_signal_endpoint(
                    app_settings.otel_exporter_otlp_endpoint,
                    "metrics",
                )
            ),
            export_interval_millis=app_settings.otel_metrics_export_interval_ms,
        )
        provider = MeterProvider(
            resource=_resource(app_settings),
            metric_readers=[reader],
        )
        metrics.set_meter_provider(provider)
        meter = metrics.get_meter(app_settings.telemetry_service_name)

        _INSTRUMENTS.http_requests_total = meter.create_counter(
            "fan_http_requests_total",
            description="Total HTTP requests handled by the API.",
        )
        _INSTRUMENTS.http_request_duration_seconds = meter.create_histogram(
            "fan_http_request_duration_seconds",
            unit="s",
            description="HTTP request latency.",
        )
        _INSTRUMENTS.webhook_events_total = meter.create_counter(
            "fan_webhook_events_total",
            description="Webhook processing outcomes.",
        )
        _INSTRUMENTS.celery_tasks_total = meter.create_counter(
            "fan_celery_tasks_total",
            description="Celery task outcomes.",
        )
        _INSTRUMENTS.celery_task_duration_seconds = meter.create_histogram(
            "fan_celery_task_duration_seconds",
            unit="s",
            description="Celery task execution latency.",
        )
        _INSTRUMENTS.plan_generation_total = meter.create_counter(
            "fan_plan_generation_total",
            description="Plan generation outcomes.",
        )
        _INSTRUMENTS.anthropic_requests_total = meter.create_counter(
            "fan_anthropic_requests_total",
            description="Anthropic request outcomes.",
        )
        _INSTRUMENTS.anthropic_request_duration_seconds = meter.create_histogram(
            "fan_anthropic_request_duration_seconds",
            unit="s",
            description="Anthropic request latency.",
        )
        _INSTRUMENTS.agent_tool_calls_total = meter.create_counter(
            "fan_agent_tool_calls_total",
            description="Agent tool execution outcomes.",
        )
        _INSTRUMENTS.agent_tool_failures_total = meter.create_counter(
            "fan_agent_tool_failures_total",
            description="Agent tool failures.",
        )
        _INSTRUMENTS.agent_tool_duration_seconds = meter.create_histogram(
            "fan_agent_tool_duration_seconds",
            unit="s",
            description="Agent tool execution latency.",
        )
        _INSTRUMENTS.reservation_actions_total = meter.create_counter(
            "fan_reservation_actions_total",
            description="Reservation flow outcomes.",
        )
        _INSTRUMENTS.adaptation_ticks_total = meter.create_counter(
            "fan_adaptation_ticks_total",
            description="Adaptation tick outcomes.",
        )

    _METRICS_INITIALIZED = True


def _record_event(name: str, value: int | float, attributes: dict[str, Any]) -> None:
    _METRIC_EVENTS.append(MetricEvent(name=name, value=value, attributes=dict(attributes)))


def reset_metric_events() -> None:
    _METRIC_EVENTS.clear()


def snapshot_metric_events(name: str | None = None) -> list[MetricEvent]:
    if name is None:
        return list(_METRIC_EVENTS)
    return [event for event in _METRIC_EVENTS if event.name == name]


def record_http_request(
    *,
    method: str,
    route: str,
    status_code: int,
    duration_seconds: float,
) -> None:
    attributes = {
        "method": method,
        "route": route,
        "status_code": str(status_code),
    }
    _record_event("fan_http_requests_total", 1, attributes)
    _record_event("fan_http_request_duration_seconds", duration_seconds, attributes)
    if _INSTRUMENTS.http_requests_total is not None:
        _INSTRUMENTS.http_requests_total.add(1, attributes)
        _INSTRUMENTS.http_request_duration_seconds.record(duration_seconds, attributes)


def record_webhook_event(result: str) -> None:
    attributes = {"result": result}
    _record_event("fan_webhook_events_total", 1, attributes)
    if _INSTRUMENTS.webhook_events_total is not None:
        _INSTRUMENTS.webhook_events_total.add(1, attributes)


def record_celery_task(task_name: str, result: str) -> None:
    attributes = {"task_name": task_name, "result": result}
    _record_event("fan_celery_tasks_total", 1, attributes)
    if _INSTRUMENTS.celery_tasks_total is not None:
        _INSTRUMENTS.celery_tasks_total.add(1, attributes)


def record_celery_task_duration(task_name: str, duration_seconds: float) -> None:
    attributes = {"task_name": task_name}
    _record_event("fan_celery_task_duration_seconds", duration_seconds, attributes)
    if _INSTRUMENTS.celery_task_duration_seconds is not None:
        _INSTRUMENTS.celery_task_duration_seconds.record(duration_seconds, attributes)


def record_plan_generation(result: str) -> None:
    attributes = {"result": result}
    _record_event("fan_plan_generation_total", 1, attributes)
    if _INSTRUMENTS.plan_generation_total is not None:
        _INSTRUMENTS.plan_generation_total.add(1, attributes)


def record_anthropic_request(
    *,
    model: str,
    result: str,
    duration_seconds: float,
) -> None:
    attributes = {"model": model, "result": result}
    _record_event("fan_anthropic_requests_total", 1, attributes)
    _record_event(
        "fan_anthropic_request_duration_seconds",
        duration_seconds,
        {"model": model},
    )
    if _INSTRUMENTS.anthropic_requests_total is not None:
        _INSTRUMENTS.anthropic_requests_total.add(1, attributes)
        _INSTRUMENTS.anthropic_request_duration_seconds.record(
            duration_seconds,
            {"model": model},
        )


def record_agent_tool_call(
    *,
    tool_name: str,
    result: str,
    duration_seconds: float,
) -> None:
    attributes = {"tool_name": tool_name, "result": result}
    duration_attributes = {"tool_name": tool_name}
    _record_event("fan_agent_tool_calls_total", 1, attributes)
    _record_event("fan_agent_tool_duration_seconds", duration_seconds, duration_attributes)
    if result != "success":
        _record_event("fan_agent_tool_failures_total", 1, {"tool_name": tool_name})

    if _INSTRUMENTS.agent_tool_calls_total is not None:
        _INSTRUMENTS.agent_tool_calls_total.add(1, attributes)
        _INSTRUMENTS.agent_tool_duration_seconds.record(
            duration_seconds,
            duration_attributes,
        )
        if result != "success":
            _INSTRUMENTS.agent_tool_failures_total.add(
                1,
                {"tool_name": tool_name},
            )


def record_reservation_action(*, action: str, result: str) -> None:
    attributes = {"action": action, "result": result}
    _record_event("fan_reservation_actions_total", 1, attributes)
    if _INSTRUMENTS.reservation_actions_total is not None:
        _INSTRUMENTS.reservation_actions_total.add(1, attributes)


def record_adaptation_tick(result: str) -> None:
    attributes = {"result": result}
    _record_event("fan_adaptation_ticks_total", 1, attributes)
    if _INSTRUMENTS.adaptation_ticks_total is not None:
        _INSTRUMENTS.adaptation_ticks_total.add(1, attributes)

