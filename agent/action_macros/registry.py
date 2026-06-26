from __future__ import annotations

from agent.action_macros.definitions import (
    OpenAppAndTileWindowActionMacro,
    OpenBrowserAndSearchActionMacro,
    OpenWorkSetupActionMacro,
    PlayRandomYoutubeVideoActionMacro,
    TileActiveWindowActionMacro,
)


class ActionMacroRegistry:
    """Registry of recipe-style macros keyed by stable workflow name."""

    def __init__(self) -> None:
        self._macros = {
            "open_app_and_tile_window": OpenAppAndTileWindowActionMacro(),
            "open_browser_and_search": OpenBrowserAndSearchActionMacro(),
            "open_work_setup": OpenWorkSetupActionMacro(),
            "play_random_youtube_video": PlayRandomYoutubeVideoActionMacro(),
            "tile_active_window": TileActiveWindowActionMacro(),
        }

    def get(self, name: str):
        return self._macros.get(name)

    def names(self) -> list[str]:
        return sorted(self._macros)


WorkflowRegistry = ActionMacroRegistry
