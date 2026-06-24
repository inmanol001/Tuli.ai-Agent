from __future__ import annotations

from agent.workflows.definitions import DesignCanvaPostWorkflow


class FullWorkflowRegistry:
    def __init__(self) -> None:
        self._workflows = {
            "design_canva_post": DesignCanvaPostWorkflow(),
        }

    def get(self, name: str):
        return self._workflows.get(name)

    def names(self) -> list[str]:
        return sorted(self._workflows)
