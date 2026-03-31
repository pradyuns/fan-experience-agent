from __future__ import annotations

import logging
import time
import uuid

from opentelemetry.trace import SpanKind, Status, StatusCode
from starlette.datastructures import Headers, MutableHeaders

from fan_experience.telemetry.context import bind_context
from fan_experience.telemetry.logging import emit_event, get_logger
from fan_experience.telemetry.metrics import record_http_request
from fan_experience.telemetry.tracing import (
    current_trace_id,
    extract_context,
    get_tracer,
    set_span_attributes,
)


class TelemetryMiddleware:
    def __init__(self, app):
        self.app = app
        self._logger = get_logger(__name__)
        self._tracer = get_tracer(__name__)

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = Headers(raw=scope.get("headers", []))
        request_id = headers.get("x-request-id") or str(uuid.uuid4())
        method = scope.get("method", "GET").upper()
        route = None
        status_code = 500
        start = time.perf_counter()

        with bind_context(request_id=request_id):
            with self._tracer.start_as_current_span(
                f"HTTP {method}",
                context=extract_context(headers),
                kind=SpanKind.SERVER,
            ) as span:
                with bind_context(trace_id=current_trace_id()):
                    emit_event(
                        self._logger,
                        "http.request.started",
                        method=method,
                    )

                    async def send_wrapper(message):
                        nonlocal route, status_code
                        if message["type"] == "http.response.start":
                            status_code = message["status"]
                            route = self._route_template(scope)
                            mutable_headers = MutableHeaders(scope=message)
                            mutable_headers["X-Request-ID"] = request_id
                            span.update_name(f"HTTP {method} {route}")
                            set_span_attributes(
                                span,
                                **{
                                    "http.method": method,
                                    "http.route": route,
                                    "http.status_code": status_code,
                                    "request.id": request_id,
                                },
                            )
                        await send(message)

                    try:
                        await self.app(scope, receive, send_wrapper)
                    except Exception as exc:
                        route = route or self._route_template(scope)
                        duration_seconds = time.perf_counter() - start
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR))
                        set_span_attributes(
                            span,
                            **{
                                "http.method": method,
                                "http.route": route,
                                "http.status_code": 500,
                                "error.type": type(exc).__name__,
                                "request.id": request_id,
                            },
                        )
                        record_http_request(
                            method=method,
                            route=route,
                            status_code=500,
                            duration_seconds=duration_seconds,
                        )
                        emit_event(
                            self._logger,
                            "http.request.finished",
                            level=logging.ERROR,
                            method=method,
                            route=route,
                            status="error",
                            status_code=500,
                            duration_ms=round(duration_seconds * 1000, 3),
                            error_type=type(exc).__name__,
                        )
                        raise
                    else:
                        route = route or self._route_template(scope)
                        duration_seconds = time.perf_counter() - start
                        if status_code >= 500:
                            span.set_status(Status(StatusCode.ERROR))
                        else:
                            span.set_status(Status(StatusCode.OK))
                        record_http_request(
                            method=method,
                            route=route,
                            status_code=status_code,
                            duration_seconds=duration_seconds,
                        )
                        emit_event(
                            self._logger,
                            "http.request.finished",
                            method=method,
                            route=route,
                            status="error" if status_code >= 500 else "success",
                            status_code=status_code,
                            duration_ms=round(duration_seconds * 1000, 3),
                        )

    @staticmethod
    def _route_template(scope) -> str:
        route = scope.get("route")
        route_path = getattr(route, "path", None)
        if route_path:
            return route_path
        return "<unmatched>"

