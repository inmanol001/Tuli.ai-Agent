from agent.capabilities.plugins.registry import PluginRegistry
from agent.capabilities.skills.selector import SkillSelector
from agent.capabilities.tools.registry import ToolRegistry
from agent.router.router_schema import RouterDecision


class CapabilityContextBuilder:
    def __init__(
        self,
        plugin_registry: PluginRegistry | None = None,
        skill_selector: SkillSelector | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.plugin_registry = plugin_registry or PluginRegistry()
        self.skill_selector = skill_selector or SkillSelector()
        self.tool_registry = tool_registry or ToolRegistry()

    def select(self, decision: RouterDecision) -> dict[str, list[dict]]:
        plugins = [
            plugin.model_dump()
            for plugin in self.plugin_registry.find_enabled(decision.suggested_plugins)
        ]
        skills = [
            skill.model_dump()
            for skill in self.skill_selector.select(decision.suggested_skills)
        ]
        tools = [
            tool.model_dump()
            for tool in self.tool_registry.find_active(decision.suggested_tools)
        ]
        return {"plugins": plugins, "skills": skills, "tools": tools}
