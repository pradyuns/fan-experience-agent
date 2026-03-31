import asyncio
import json
import re
from abc import ABC, abstractmethod
from typing import Any

from anthropic import AsyncAnthropic

from fan_experience.agent.prompt import SYSTEM_PROMPT
from fan_experience.agent.tool_registry import get_tool_definitions, get_tool_handler
from fan_experience.config import settings
from fan_experience.schemas.agent import AgentContext, PlanProposal


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
                system=SYSTEM_PROMPT,
                tools=tools,
                messages=messages,
            )

            if response.stop_reason == "end_turn":
                return self._parse_response(response)

            # run all tool calls from this response concurrently
            tool_blocks = [b for b in response.content if b.type == "tool_use"]
            tool_results = await asyncio.gather(
                *[self._execute_tool(b) for b in tool_blocks]
            )

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": list(tool_results)})

        raise RuntimeError("Agent exceeded maximum tool rounds")

    # execute a single tool call and return the result dict
    async def _execute_tool(self, block: Any) -> dict:
        handler = get_tool_handler(block.name)
        if handler is None:
            return {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps({"error": f"Unknown tool: {block.name}"}),
            }

        result = await handler(**block.input)
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
