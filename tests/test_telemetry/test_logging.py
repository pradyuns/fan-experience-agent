import json
import logging

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from fan_experience.config import Settings
from fan_experience.telemetry.context import bind_context
from fan_experience.telemetry.logging import JsonFormatter, TelemetryContextFilter


def test_json_log_serialization_includes_correlation_fields_without_payloads():
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")
    logger = logging.getLogger("fan_experience.test.logging")
    formatter = JsonFormatter()
    filter_ = TelemetryContextFilter(
        Settings(
            telemetry_service_name="fan-experience-agent",
            telemetry_env="test",
        )
    )

    with bind_context(request_id="req-1", plan_id="plan-1", user_id="user-1"):
        with tracer.start_as_current_span("log-span"):
            record = logger.makeRecord(
                logger.name,
                logging.INFO,
                __file__,
                10,
                "ignored",
                (),
                None,
                extra={
                    "event": "test.event",
                    "route": "/test",
                    "prompt": "secret prompt text",
                    "body": '{"raw":"payload"}',
                },
            )
            assert filter_.filter(record) is True
            payload = json.loads(formatter.format(record))

    assert payload["event"] == "test.event"
    assert payload["request_id"] == "req-1"
    assert payload["plan_id"] == "plan-1"
    assert payload["user_id"] == "user-1"
    assert payload["trace_id"]
    assert payload["span_id"]
    assert "prompt" not in payload
    assert "body" not in payload

