from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any

_FIELD_NAMES = (
    "request_id",
    "trace_id",
    "plan_id",
    "purchase_id",
    "user_id",
    "task_id",
    "tool_name",
)

_CONTEXT_VARS: dict[str, ContextVar[str | None]] = {
    field: ContextVar(f"fan_telemetry_{field}", default=None) for field in _FIELD_NAMES
}


def get_context_values() -> dict[str, str | None]:
    return {field: var.get() for field, var in _CONTEXT_VARS.items()}


def set_context_values(**values: Any) -> dict[str, Token[str | None]]:
    tokens: dict[str, Token[str | None]] = {}
    for field, value in values.items():
        if field not in _CONTEXT_VARS:
            raise KeyError(f"Unknown telemetry context field: {field}")
        normalized = None if value is None else str(value)
        tokens[field] = _CONTEXT_VARS[field].set(normalized)
    return tokens


def reset_context(tokens: dict[str, Token[str | None]]) -> None:
    for field, token in reversed(list(tokens.items())):
        _CONTEXT_VARS[field].reset(token)


@contextmanager
def bind_context(**values: Any) -> Iterator[None]:
    tokens = set_context_values(**values)
    try:
        yield
    finally:
        reset_context(tokens)

