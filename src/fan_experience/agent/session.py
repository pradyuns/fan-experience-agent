import asyncio
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from typing import Any

from anthropic import AsyncAnthropic
from opentelemetry.trace import Status, StatusCode

from fan_experience.agent.prompt import SYSTEM_PROMPT
from fan_experience.agent.tool_registry import get_tool_definitions, get_tool_handler
from fan_experience.config import settings
from fan_experience.schemas.agent import AgentContext, PlanProposal
from fan_experience.telemetry.context import bind_context
from fan_experience.telemetry.logging import emit_event, get_logger
from fan_experience.telemetry.metrics import (
    record_agent_tool_call,
    record_anthropic_request,
)
from fan_experience.telemetry.tracing import get_tracer, set_span_attributes

MODEL_NAME = "claude-sonnet-4-20250514"
logger = get_logger(__name__)


# shared interface for all agent session implementations
class AgentSession(ABC):
    @abstractmethod
    async def run(self, context: AgentContext) -> PlanProposal:
        ...


# runs a single tool-use loop to produce one plan proposal
class SingleTurnSession(AgentSession):
    MAX_TOOL_ROUNDS = 15

    def __init__(self, client: AsyncAnthropic | None = None):
        self._client = client or AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def run(self, context: AgentContext) -> PlanProposal:
        tracer = get_tracer(__name__)
        user_message = (
            "Generate a dining plan for:\n"
            f"- Event ID: {context.event_id}\n"
            f"- User ID: {context.user_id}\n"
            f"- Party size: {context.ticket_count}\n"
        )
        if context.refinement_preferences:
            user_message += (
                f"- Refinement: {json.dumps(context.refinement_preferences)}\n"
            )

        messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
        tools = get_tool_definitions()
        total_tool_calls = 0
        round_count = 0

        with bind_context(
            plan_id=str(context.plan_id),
            user_id=str(context.user_id),
        ):
            with tracer.start_as_current_span("agent.session") as span:
                set_span_attributes(
                    span,
                    **{
                        "plan.id": str(context.plan_id),
                        "event.id": str(context.event_id),
                        "user.id": str(context.user_id),
                        "ticket_count": context.ticket_count,
                    },
                )
                emit_event(logger, "agent.session.started", status="started")
                try:
                    for round_index in range(self.MAX_TOOL_ROUNDS):
                        round_count = round_index + 1
                        response = await self._call_model(
                            messages=messages,
                            tools=tools,
                            round_index=round_index,
                        )

                        if response.stop_reason == "end_turn":
                            set_span_attributes(
                                span,
                                **{
                                    "agent.round_count": round_count,
                                    "agent.total_tool_calls": total_tool_calls,
                                },
                            )
                            return self._parse_response(response)

                        tool_blocks = [
                            block for block in response.content if block.type == "tool_use"
                        ]
                        total_tool_calls += len(tool_blocks)
                        tool_results = await asyncio.gather(
                            *[self._execute_tool(block) for block in tool_blocks]
                        )

                        messages.append({"role": "assistant", "content": response.content})
                        messages.append({"role": "user", "content": list(tool_results)})
                except Exception as exc:
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR))
                    raise

        raise RuntimeError("Agent exceeded maximum tool rounds")

    async def _call_model(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        round_index: int,
    ) -> Any:
        tracer = get_tracer(__name__)
        started_at = time.perf_counter()
        with tracer.start_as_current_span("anthropic.messages.create") as span:
            set_span_attributes(
                span,
                **{
                    "model": MODEL_NAME,
                    "round_index": round_index,
                },
            )
            try:
                response = await self._client.messages.create(
                    model=MODEL_NAME,
                    max_tokens=4096,
                    system=SYSTEM_PROMPT,
                    tools=tools,
                    messages=messages,
                )
            except Exception as exc:
                duration_seconds = time.perf_counter() - started_at
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                record_anthropic_request(
                    model=MODEL_NAME,
                    result="error",
                    duration_seconds=duration_seconds,
                )
                emit_event(
                    logger,
                    "agent.anthropic.request",
                    level=logging.ERROR,
                    status="error",
                    model=MODEL_NAME,
                    round_index=round_index,
                    duration_ms=round(duration_seconds * 1000, 3),
                    error_type=type(exc).__name__,
                )
                raise

            tool_blocks = [block for block in response.content if block.type == "tool_use"]
            duration_seconds = time.perf_counter() - started_at
            set_span_attributes(
                span,
                **{
                    "stop_reason": response.stop_reason,
                    "response_has_tool_calls": bool(tool_blocks),
                },
            )
            record_anthropic_request(
                model=MODEL_NAME,
                result="success",
                duration_seconds=duration_seconds,
            )
            emit_event(
                logger,
                "agent.anthropic.request",
                status="success",
                model=MODEL_NAME,
                round_index=round_index,
                stop_reason=response.stop_reason,
                response_has_tool_calls=bool(tool_blocks),
                duration_ms=round(duration_seconds * 1000, 3),
            )
            return response

    # execute a single tool call and return the result dict
    async def _execute_tool(self, block: Any) -> dict:
        tracer = get_tracer(__name__)
        started_at = time.perf_counter()

        with bind_context(tool_name=block.name):
            emit_event(logger, "agent.tool.started", tool_name=block.name, status="started")
            with tracer.start_as_current_span(f"agent.tool.{block.name}") as span:
                set_span_attributes(span, **{"tool_name": block.name})
                handler = get_tool_handler(block.name)
                if handler is None:
                    duration_seconds = time.perf_counter() - started_at
                    span.set_status(Status(StatusCode.ERROR))
                    set_span_attributes(span, **{"success": False})
                    record_agent_tool_call(
                        tool_name=block.name,
                        result="error",
                        duration_seconds=duration_seconds,
                    )
                    emit_event(
                        logger,
                        "agent.tool.finished",
                        level=logging.ERROR,
                        tool_name=block.name,
                        status="error",
                        duration_ms=round(duration_seconds * 1000, 3),
                        error_type="UnknownTool",
                    )
                    return {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"error": f"Unknown tool: {block.name}"}),
                    }

                try:
                    result = await handler(**block.input)
                except Exception as exc:
                    duration_seconds = time.perf_counter() - started_at
                    span.record_exception(exc)
                    span.set_status(Status(StatusCode.ERROR))
                    set_span_attributes(span, **{"success": False})
                    record_agent_tool_call(
                        tool_name=block.name,
                        result="error",
                        duration_seconds=duration_seconds,
                    )
                    emit_event(
                        logger,
                        "agent.tool.finished",
                        level=logging.ERROR,
                        tool_name=block.name,
                        status="error",
                        duration_ms=round(duration_seconds * 1000, 3),
                        error_type=type(exc).__name__,
                    )
                    return {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps({"error": type(exc).__name__}),
                    }

                duration_seconds = time.perf_counter() - started_at
                set_span_attributes(
                    span,
                    **{
                        "result_source": result.source,
                        "success": True,
                    },
                )
                record_agent_tool_call(
                    tool_name=block.name,
                    result="success",
                    duration_seconds=duration_seconds,
                )
                emit_event(
                    logger,
                    "agent.tool.finished",
                    tool_name=block.name,
                    status="success",
                    result_source=result.source,
                    duration_ms=round(duration_seconds * 1000, 3),
                )
                return {
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result.data, default=str),
                }

    # parse the final text response into a validated plan proposal
    def _parse_response(self, response: Any) -> PlanProposal:
        text_blocks: list[str] = []
        for block in response.content:
            if block.type == "text":
                text_blocks.append(block.text)
                try:
                    return PlanProposal(**json.loads(self._extract_json(block.text)))
                except json.JSONDecodeError:
                    continue
        if text_blocks:
            combined_text = "\n".join(text_blocks)
            return PlanProposal(**json.loads(self._extract_json(combined_text)))
        raise ValueError("No text block in agent response")

    @staticmethod
    def _extract_json(text: str) -> str:
        stripped = text.strip()
        if stripped.startswith("{"):
            return stripped

        fenced_match = re.search(r"```json\s*(\{.*\})\s*```", text, re.DOTALL)
        if fenced_match:
            return fenced_match.group(1)

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]

        return stripped
