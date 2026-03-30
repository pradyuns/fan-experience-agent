import json
from abc import ABC, abstractmethod
from typing import Any

from anthropic import AsyncAnthropic

from fan_experience.agent.prompt import build_system_prompt
from fan_experience.agent.tool_registry import get_tool_definitions, get_tool_handler
from fan_experience.config import settings
from fan_experience.schemas.agent import AgentContext, PlanProposal


# defining the shared interface for all agent session implementations.
class AgentSession(ABC):
    @abstractmethod
    async def run(self, context: AgentContext) -> PlanProposal:
        ...


# running a single tool-use loop to produce one plan proposal.
class SingleTurnSession(AgentSession):
    MAX_TOOL_ROUNDS = 15

    def __init__(self, client: AsyncAnthropic | None = None):
        self._client = client or AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def run(self, context: AgentContext) -> PlanProposal:
        system_prompt = build_system_prompt()
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

        for _ in range(self.MAX_TOOL_ROUNDS):
            response = await self._client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                return self._parse_response(response)

            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue

                handler = get_tool_handler(block.name)
                if handler is None:
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(
                                {"error": f"Unknown tool: {block.name}"}
                            ),
                        }
                    )
                    continue

                result = await handler(**block.input)
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result.data, default=str),
                    }
                )

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        raise RuntimeError("Agent exceeded maximum tool rounds")

    # parsing the final text response into a validated plan proposal.
    def _parse_response(self, response: Any) -> PlanProposal:
        for block in response.content:
            if block.type == "text":
                return PlanProposal(**json.loads(block.text))
        raise ValueError("No text block in agent response")
