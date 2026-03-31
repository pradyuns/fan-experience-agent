from __future__ import annotations

from collections.abc import Mapping, MutableMapping
from typing import Any

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.trace import Span
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from fan_experience.config import Settings, settings

_TRACING_INITIALIZED = False
_PROPAGATOR = TraceContextTextMapPropagator()


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


def init_tracing(app_settings: Settings = settings) -> None:
    global _TRACING_INITIALIZED
    if _TRACING_INITIALIZED:
        return

    if app_settings.telemetry_enabled:
        provider = TracerProvider(
            sampler=TraceIdRatioBased(app_settings.otel_trace_sample_ratio),
            resource=_resource(app_settings),
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=_signal_endpoint(
                        app_settings.otel_exporter_otlp_endpoint,
                        "traces",
                    )
                )
            )
        )
        trace.set_tracer_provider(provider)

    _TRACING_INITIALIZED = True


def get_tracer(name: str = "fan_experience"):
    return trace.get_tracer(name)


def inject_context(headers: MutableMapping[str, Any] | None = None) -> dict[str, Any]:
    carrier: dict[str, Any] = {} if headers is None else dict(headers)
    _PROPAGATOR.inject(carrier)
    return carrier


def extract_context(headers: Mapping[str, Any] | None = None):
    return _PROPAGATOR.extract({} if headers is None else dict(headers))


def format_trace_id(trace_id: int) -> str:
    return f"{trace_id:032x}"


def format_span_id(span_id: int) -> str:
    return f"{span_id:016x}"


def current_trace_id() -> str | None:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    return format_trace_id(span_context.trace_id)


def current_span_id() -> str | None:
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    return format_span_id(span_context.span_id)


def set_span_attributes(span: Span, **attributes: Any) -> None:
    if not span.is_recording():
        return

    for key, value in attributes.items():
        if value is None:
            continue
        if isinstance(value, (str, bool, int, float)):
            span.set_attribute(key, value)
            continue
        if isinstance(value, (list, tuple)):
            span.set_attribute(key, [str(item) for item in value])
            continue
        span.set_attribute(key, str(value))

