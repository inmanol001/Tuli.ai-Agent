from types import SimpleNamespace

from agent.gateway.message_types import ContextPackage
from agent.models.tool_planner import ToolPlanner
from agent.router.router_schema import RouterDecision


class FakeToolClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat_with_tools(self, model, messages, tools, **kwargs):
        self.calls.append(
            {"model": model, "messages": messages, "tools": tools, "kwargs": kwargs}
        )
        return self.response


def context_for(tool):
    return ContextPackage(
        system_prompt="system",
        user_message="cambia al escritorio 3",
        router_decision=RouterDecision(route="action_ready"),
        selected_tools=[tool],
        selected_plugins=[{"name": "macos"}],
        selected_skills=[{"name": "macos_spaces"}],
        safety_rules=["No fake actions."],
    )


def test_tool_planner_converts_registry_tools_to_ollama_native_tools():
    response = {
        "message": {
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "macos_space_switch_desktop_number",
                        "arguments": {"number": 3},
                    }
                }
            ],
        }
    }
    tool = {
        "name": "macos_space_switch_desktop_number",
        "description": "Switch desktop.",
        "parameters": {
            "type": "object",
            "properties": {"number": {"type": "integer"}},
            "required": ["number"],
        },
        "risk_level": "low",
        "declared": True,
        "active": True,
    }
    client = FakeToolClient(response)
    planner = ToolPlanner(client=client)

    result = planner.plan(context_for(tool))

    assert client.calls[0]["model"] == "llama3-groq-tool-use:8b"
    assert client.calls[0]["tools"][0]["type"] == "function"
    assert client.calls[0]["tools"][0]["function"]["name"] == tool["name"]
    assert result.tool_calls[0].tool_name == "macos_space_switch_desktop_number"
    assert result.tool_calls[0].arguments == {"number": 3}
    assert result.tool_calls[0].risk_level == "low"


def test_tool_planner_reads_object_style_tool_calls():
    response = SimpleNamespace(
        message=SimpleNamespace(
            content="",
            tool_calls=[
                SimpleNamespace(
                    function=SimpleNamespace(
                        name="macos_space_previous",
                        arguments={},
                    )
                )
            ],
        )
    )
    tool = {
        "name": "macos_space_previous",
        "description": "Previous desktop.",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "risk_level": "low",
        "declared": True,
        "active": True,
    }

    result = ToolPlanner(client=FakeToolClient(response)).plan(context_for(tool))

    assert result.tool_calls[0].tool_name == "macos_space_previous"
    assert result.content == ""


def test_tool_planner_does_not_parse_fake_action_from_content():
    response = {
        "message": {
            "content": "¡Claro! Cambiando al escritorio 1.",
            "tool_calls": [],
        }
    }
    tool = {
        "name": "macos_space_switch_desktop_number",
        "description": "Switch desktop.",
        "parameters": {"type": "object", "properties": {}, "required": []},
        "risk_level": "low",
        "declared": True,
        "active": True,
    }

    result = ToolPlanner(client=FakeToolClient(response)).plan(context_for(tool))

    assert result.tool_calls == []
    assert result.content == "¡Claro! Cambiando al escritorio 1."
    assert result.no_tool_reason == "no_native_tool_call"
