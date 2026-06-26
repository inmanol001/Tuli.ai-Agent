from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from agent.capabilities.tools.schemas import ToolCall
from agent.executor.results import ToolResult


WorkflowName = Literal[
    "tile_active_window",
    "open_app_and_tile_window",
    "open_browser_and_search",
    "play_random_youtube_video",
    "open_work_setup",
]


class ActionMacroPlan(BaseModel):
    """Intent-selected recipe for a fast, predeclared action macro."""

    selected: bool = False
    workflow_name: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    error: str | None = None


class ActionMacroStepResult(BaseModel):
    """Result for one macro step, including the underlying ActionRunner trace."""

    step_index: int
    tool_call: ToolCall
    tool_result: ToolResult
    success: bool
    stopped: bool = False
    stop_reason: str | None = None
    action_run: dict[str, Any] | None = None
    reflection_trace: list[dict[str, Any]] = Field(default_factory=list)
    retry_count: int = 0


class ActionMacroResult(BaseModel):
    """End-to-end result for a recipe-style macro execution."""

    workflow_name: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    steps: list[ActionMacroStepResult] = Field(default_factory=list)
    success: bool = False
    stopped_reason: str | None = None
    error: str | None = None


WorkflowPlan = ActionMacroPlan
WorkflowStepResult = ActionMacroStepResult
WorkflowResult = ActionMacroResult
