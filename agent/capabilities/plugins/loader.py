from agent.capabilities.plugins.registry import PluginRegistry


def load_plugins() -> PluginRegistry:
    return PluginRegistry()

