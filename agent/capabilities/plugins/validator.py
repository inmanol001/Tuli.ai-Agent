from agent.capabilities.plugins.registry import PluginDefinition


def validate_plugin(plugin: PluginDefinition) -> bool:
    return bool(
        plugin.name
        and plugin.description
        and isinstance(plugin.tools, list)
        and isinstance(plugin.skills, list)
        and plugin.enabled in {True, False}
    )
