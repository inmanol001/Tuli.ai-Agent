from pathlib import Path

from pydantic import BaseModel, Field


class PluginDefinition(BaseModel):
    name: str
    description: str
    tools: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    risk: str = "low"
    enabled: bool = True


class PluginRegistry:
    def __init__(
        self, path: str | Path = "agent/capabilities/plugins/installed"
    ) -> None:
        self.path = Path(path)
        self._plugins = self._load()

    def _load(self) -> dict[str, PluginDefinition]:
        try:
            import yaml
        except ModuleNotFoundError:
            return {}
        plugins: dict[str, PluginDefinition] = {}
        for plugin_yaml in self.path.glob("*/plugin.yaml"):
            data = yaml.safe_load(plugin_yaml.read_text(encoding="utf-8")) or {}
            plugin = PluginDefinition.model_validate(data)
            plugins[plugin.name] = plugin
        return plugins

    def all(self) -> list[PluginDefinition]:
        return list(self._plugins.values())

    def get(self, name: str) -> PluginDefinition | None:
        return self._plugins.get(name)

    def find_enabled(self, names: list[str]) -> list[PluginDefinition]:
        return [
            plugin
            for name in names
            if (plugin := self._plugins.get(name)) is not None and plugin.enabled
        ]
