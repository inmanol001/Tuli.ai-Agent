from __future__ import annotations

from agent.action_macros.definitions import (
    OpenAppAndTileWindowActionMacro,
    TileActiveWindowActionMacro,
)


class ActionMacroRegistry:
    def __init__(self) -> None:
        self._macros = {
            "open_app_and_tile_window": OpenAppAndTileWindowActionMacro(),
            "tile_active_window": TileActiveWindowActionMacro(),
        }

    def get(self, name: str):
        return self._macros.get(name)

    def names(self) -> list[str]:
        return sorted(self._macros)


WorkflowRegistry = ActionMacroRegistry
