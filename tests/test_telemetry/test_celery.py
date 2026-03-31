from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from fan_experience.telemetry.celery import (
    begin_task_span,
    finish_task_span,
    inject_publish_headers,
    record_task_failure,
)
from fan_experience.telemetry.context import bind_context, get_context_values
from fan_experience.telemetry.metrics import snapshot_metric_events


def test_publish_headers_include_trace_and_request_metadata():
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")

    with bind_context(
        request_id="req-1",
        plan_id="plan-1",
        purchase_id="purchase-1",
        user_id="user-1",
    ):
        with tracer.start_as_current_span("parent"):
            headers = inject_publish_headers({})

    assert "traceparent" in headers
    assert headers["fan-request-id"] == "req-1"
    assert headers["fan-plan-id"] == "plan-1"
    assert headers["fan-purchase-id"] == "purchase-1"
    assert headers["fan-user-id"] == "user-1"


def test_task_span_lifecycle_extracts_context_and_records_success_metrics():
    begin_task_span(
        task_id="task-1",
        task_name="fan_experience.run_plan_generation",
        headers={
            "fan-request-id": "req-1",
            "fan-plan-id": "plan-1",
            "fan-purchase-id": "purchase-1",
            "fan-user-id": "user-1",
        },
    )

    assert get_context_values()["request_id"] == "req-1"
    assert get_context_values()["plan_id"] == "plan-1"
    assert get_context_values()["task_id"] == "task-1"

    finish_task_span(task_id="task-1", state="SUCCESS")

    assert get_context_values()["task_id"] is None
    assert snapshot_metric_events("fan_celery_tasks_total")[-1].attributes == {
        "task_name": "fan_experience.run_plan_generation",
        "result": "success",
    }
    assert snapshot_metric_events("fan_celery_task_duration_seconds")[-1].attributes == {
        "task_name": "fan_experience.run_plan_generation"
    }


def test_task_span_lifecycle_records_failure_metrics():
    begin_task_span(
        task_id="task-2",
        task_name="fan_experience.run_plan_generation",
        headers={"fan-request-id": "req-2"},
    )

    record_task_failure(
        task_id="task-2",
        task_name="fan_experience.run_plan_generation",
        exception=RuntimeError("boom"),
    )
    finish_task_span(task_id="task-2", state="FAILURE")

    assert snapshot_metric_events("fan_celery_tasks_total")[-1].attributes == {
        "task_name": "fan_experience.run_plan_generation",
        "result": "failure",
    }

