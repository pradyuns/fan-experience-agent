import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from fan_experience.agent.session import AgentSession, SingleTurnSession
from fan_experience.schemas.agent import AgentContext, PlanProposal
from fan_experience.telemetry.metrics import snapshot_metric_events
from fan_experience.tools.base import ToolResult


# ensuring the abstract base cannot be instantiated directly
def test_agent_session_is_abstract():
    with pytest.raises(TypeError):
        AgentSession()


@pytest.mark.asyncio
async def test_single_turn_session_processes_tool_calls():
    context = AgentContext(
        plan_id="00000000-0000-0000-0000-000000000001",
        user_id="00000000-0000-0000-0000-000000000002",
        event_id="00000000-0000-0000-0000-000000000003",
        ticket_count=2,
    )

    mock_client = AsyncMock()

    tool_call_response = MagicMock()
    tool_call_response.stop_reason = "tool_use"
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.id = "call-1"
    tool_use_block.name = "get_event_details"
    tool_use_block.input = {"event_id": "event-001"}
    tool_call_response.content = [tool_use_block]

    final_response = MagicMock()
    final_response.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = json.dumps(
        {
            "shortlist": [
                {
                    "candidate_id": "rest-001",
                    "recommended": True,
                    "dining_time": "2026-07-01T17:30:00Z",
                    "option_reasoning": "Great Italian spot close to venue",
                },
                {
                    "candidate_id": "rest-003",
                    "recommended": False,
                    "dining_time": "2026-07-01T18:00:00Z",
                    "option_reasoning": "Quick budget option",
                },
            ],
            "plan_summary": "Dinner at Bestia at 5:30pm, quick walk to the arena",
            "conversation_history": [],
        }
    )
    final_response.content = [text_block]

    mock_client.messages.create = AsyncMock(
        side_effect=[tool_call_response, final_response]
    )

    session = SingleTurnSession(client=mock_client)
    proposal = await session.run(context)

    assert isinstance(proposal, PlanProposal)
    assert len(proposal.shortlist) == 2
    recommended = [o for o in proposal.shortlist if o.recommended]
    assert len(recommended) == 1
    assert recommended[0].candidate_id == "rest-001"
    assert mock_client.messages.create.call_count == 2


def test_single_turn_session_parses_fenced_json_response():
    final_response = MagicMock()
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = (
        "Based on all the information gathered, here's your personalized dining plan:\n\n"
        "```json\n"
        "{\n"
        '  "shortlist": [\n'
        "    {\n"
        '      "candidate_id": "rest-002",\n'
        '      "recommended": true,\n'
        '      "dining_time": "2026-07-01T17:00:00+00:00",\n'
        '      "option_reasoning": "Quiet sushi option with good timing."\n'
        "    }\n"
        "  ],\n"
        '  "plan_summary": "Dinner at 5 before the game.",\n'
        '  "conversation_history": []\n'
        "}\n"
        "```"
    )
    final_response.content = [text_block]

    session = SingleTurnSession(client=AsyncMock())
    proposal = session._parse_response(final_response)

    assert proposal.plan_summary == "Dinner at 5 before the game."
    assert proposal.shortlist[0].candidate_id == "rest-002"


@pytest.mark.asyncio
async def test_single_turn_session_records_spans_and_metrics_without_payload_attributes():
    provider = TracerProvider()
    exporter = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    tracer = provider.get_tracer("test")

    context = AgentContext(
        plan_id="00000000-0000-0000-0000-000000000001",
        user_id="00000000-0000-0000-0000-000000000002",
        event_id="00000000-0000-0000-0000-000000000003",
        ticket_count=2,
    )

    mock_client = AsyncMock()

    tool_call_response = MagicMock()
    tool_call_response.stop_reason = "tool_use"
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.id = "call-1"
    tool_use_block.name = "get_event_details"
    tool_use_block.input = {"event_id": "event-001"}
    tool_call_response.content = [tool_use_block]

    final_response = MagicMock()
    final_response.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = json.dumps(
        {
            "shortlist": [
                {
                    "candidate_id": "rest-001",
                    "recommended": True,
                    "dining_time": "2026-07-01T17:30:00Z",
                    "option_reasoning": "Great Italian spot close to venue",
                }
            ],
            "plan_summary": "Dinner at Bestia at 5:30pm",
            "conversation_history": [],
        }
    )
    final_response.content = [text_block]
    mock_client.messages.create = AsyncMock(
        side_effect=[tool_call_response, final_response]
    )

    session = SingleTurnSession(client=mock_client)
    mock_tool_handler = AsyncMock(
        return_value=ToolResult(data={"venue": "Arena"}, source="mock")
    )

    with patch("fan_experience.agent.session.get_tracer", return_value=tracer):
        with patch(
            "fan_experience.agent.session.get_tool_handler",
            return_value=mock_tool_handler,
        ):
            proposal = await session.run(context)

    assert proposal.plan_summary == "Dinner at Bestia at 5:30pm"
    metric_names = [event.name for event in snapshot_metric_events()]
    assert "fan_anthropic_requests_total" in metric_names
    assert "fan_agent_tool_calls_total" in metric_names

    spans = exporter.get_finished_spans()
    span_names = [span.name for span in spans]
    assert "agent.session" in span_names
    assert "anthropic.messages.create" in span_names
    assert "agent.tool.get_event_details" in span_names

    attribute_keys = {
        key
        for span in spans
        for key in span.attributes.keys()
    }
    assert "plan.id" in attribute_keys
    assert "tool_name" in attribute_keys
    assert "model" in attribute_keys
    assert "result_source" in attribute_keys
    assert not any(
        "prompt" in key or "content" in key or "input" in key or "output" in key
        for key in attribute_keys
    )
