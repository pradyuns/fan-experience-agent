import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from fan_experience.agent.session import AgentSession, SingleTurnSession
from fan_experience.schemas.agent import AgentContext, PlanProposal


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
