from agent.capabilities.plugins.registry import PluginRegistry
from agent.capabilities.plugins.validator import validate_plugin
from agent.capabilities.skills.loader import load_skill
from agent.capabilities.skills.selector import SkillSelector
from agent.capabilities.tools.registry import ToolRegistry
from agent.capabilities.tools.schemas import ToolCall
from agent.executor.validator import ToolValidator


def test_browser_plugin_loads():
    plugins = PluginRegistry()
    loaded = plugins.find_enabled(["browser"])
    assert len(loaded) == 1
    assert loaded[0].name == "browser"
    assert (
        loaded[0].description
        == "Capacidades para buscar información y abrir contenido web con el navegador por defecto."
    )
    assert validate_plugin(loaded[0]) is True
    assert plugins.get("browser").tools == ["browser_search"]


def test_macos_plugin_includes_observation_tools():
    plugins = PluginRegistry()
    macos = plugins.get("macos")
    assert macos is not None
    assert "open_app" in macos.tools
    assert "window_native_tiling" in macos.tools
    assert "macos_permissions_check" in macos.tools
    assert "macos_observe_frontmost" in macos.tools
    assert "macos_visible_windows" in macos.tools
    assert "macos_list_apps" in macos.tools
    assert "macos_space_status" in macos.tools
    assert "macos_space_next" in macos.tools
    assert "macos_space_previous" in macos.tools
    assert "macos_space_mission_control" in macos.tools
    assert "macos_space_switch_desktop_number" in macos.tools


def test_browser_search_skill_loads():
    skills = SkillSelector().select(["browser_search"])
    assert len(skills) == 1
    assert skills[0].name == "browser_search"
    assert skills[0].description == "Buscar información o abrir contenido web usando el navegador por defecto."
    assert skills[0].tools == ["browser_search"]
    assert "browser_search" in skills[0].content


def test_macos_windows_skill_loads():
    skills = SkillSelector().select(["macos_windows"])
    assert len(skills) == 1
    assert skills[0].name == "macos_windows"
    assert skills[0].description == "Mover o redimensionar la ventana activa de macOS usando acciones nativas seguras."
    assert skills[0].tools == ["window_native_tiling"]
    assert "window_native_tiling" in skills[0].content


def test_tool_registry_declares_active_real_tools_for_phase_2_1():
    registry = ToolRegistry()
    browser_tool = registry.get("browser_search")
    assert browser_tool.declared is True
    assert browser_tool.active is True
    assert registry.find_declared(["browser_search"])[0].name == "browser_search"
    assert browser_tool.parameters["required"] == ["query"]
    assert browser_tool.description.startswith("Open the default browser for web navigation or search.")
    assert browser_tool.parameters["properties"]["query"]["description"] == (
        "The search topic, website name, or absolute http/https URL requested by the user."
    )
    assert browser_tool.parameters["properties"]["target"]["description"] == (
        "Browser destination mode. Use auto unless the user clearly requested a specific destination or provided a URL."
    )
    assert registry.get("browser_search").active is True
    assert registry.get("open_app").active is True
    assert registry.get("window_native_tiling").active is True
    assert registry.get("window_native_tiling").parameters["properties"]["action"]["enum"] == [
        "fill",
        "center",
        "left",
        "right",
        "top",
        "bottom",
        "top-left",
        "top-right",
        "bottom-left",
        "bottom-right",
        "left-right",
        "quarters",
        "return",
    ]
    assert registry.get("open_app").risk_level == "low"
    assert registry.get("open_url").active is False
    assert registry.get("macos_permissions_check").active is True
    assert registry.get("macos_observe_frontmost").risk_level == "low"
    assert registry.get("macos_visible_windows").active is True
    assert registry.get("macos_list_apps").active is True
    assert registry.get("macos_space_status").active is True
    assert registry.get("macos_space_next").risk_level == "low"
    assert registry.get("macos_space_previous").active is True
    assert registry.get("macos_space_mission_control").active is True
    assert registry.get("macos_space_switch_desktop_number").risk_level == "low"
    assert registry.get("take_screenshot").active is False
    assert registry.get("click").active is False
    assert registry.get("type_text").active is False


def test_skill_loader_reads_frontmatter_metadata():
    skill = load_skill("agent/capabilities/skills/browser_search/SKILL.md")
    assert skill.name == "browser_search"
    assert skill.description == "Buscar información o abrir contenido web usando el navegador por defecto."
    assert skill.tools == ["browser_search"]


def test_tool_validator_accepts_valid_browser_search_call_schema_level():
    validator = ToolValidator()
    validator.validate(
        ToolCall(
            tool_name="browser_search",
            arguments={"query": "omega", "target": "youtube"},
        )
    )


def test_tool_validator_accepts_active_open_tools():
    validator = ToolValidator()
    validator.validate(ToolCall(tool_name="open_app", arguments={"app_name": "Safari"}))
    validator.validate(ToolCall(tool_name="window_native_tiling", arguments={"action": "right"}))
    validator.validate(ToolCall(tool_name="macos_permissions_check", arguments={}))
    validator.validate(ToolCall(tool_name="macos_observe_frontmost", arguments={}))
    validator.validate(ToolCall(tool_name="macos_visible_windows", arguments={}))
    validator.validate(ToolCall(tool_name="macos_list_apps", arguments={}))
    validator.validate(ToolCall(tool_name="macos_space_status", arguments={}))
    validator.validate(ToolCall(tool_name="macos_space_next", arguments={}))
    validator.validate(ToolCall(tool_name="macos_space_previous", arguments={}))
    validator.validate(ToolCall(tool_name="macos_space_mission_control", arguments={}))
    validator.validate(ToolCall(tool_name="macos_space_switch_desktop_number", arguments={"number": 2}))


def test_tool_validator_rejects_missing_browser_search_query():
    validator = ToolValidator()
    try:
        validator.validate(ToolCall(tool_name="browser_search", arguments={}))
    except Exception as exc:
        assert "browser_search requires a query argument" in str(exc)


def test_tool_validator_rejects_invalid_window_native_tiling_action():
    validator = ToolValidator()
    try:
        validator.validate(ToolCall(tool_name="window_native_tiling", arguments={"action": "diagonal"}))
    except Exception as exc:
        assert "window_native_tiling supports a fixed allowlist" in str(exc)
