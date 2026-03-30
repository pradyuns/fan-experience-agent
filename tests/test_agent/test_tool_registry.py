from fan_experience.agent.prompt import build_system_prompt
from fan_experience.agent.tool_registry import get_tool_definitions, get_tool_handler


# ensuring the agent sees a complete tool contract list
def test_tool_definitions_are_valid():
    tools = get_tool_definitions()
    assert len(tools) == 7
    for tool in tools:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"


# ensuring each declared tool name resolves to a callable handler
def test_all_tools_have_handlers():
    tools = get_tool_definitions()
    for tool in tools:
        handler = get_tool_handler(tool["name"])
        assert handler is not None, f"No handler for {tool['name']}"
        assert callable(handler)


# ensuring unknown tool names do not resolve accidentally
def test_unknown_tool_returns_none():
    handler = get_tool_handler("nonexistent_tool")
    assert handler is None


# ensuring the prompt contains the required structured output fields
def test_system_prompt_contains_constraints():
    prompt = build_system_prompt()
    assert "shortlist" in prompt
    assert "candidate_id" in prompt
    assert "recommended" in prompt
    assert "option_reasoning" in prompt
    assert "plan_summary" in prompt
