from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from agent.capabilities.tools.schemas import ToolCall
from agent.executor.results import ToolResult


WorkflowName = Literal["tile_active_window", "open_app_and_tile_window"]


class ActionMacroPlan(BaseModel):
    selected: bool = False
    workflow_name: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    error: str | None = None


class ActionMacroStepResult(BaseModel):
    step_index: int
    tool_call: ToolCall
    tool_result: ToolResult
    success: bool
    stopped: bool = False
    stop_reason: str | None = None


class ActionMacroResult(BaseModel):
    workflow_name: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    steps: list[ActionMacroStepResult] = Field(default_factory=list)
    success: bool = False
    stopped_reason: str | None = None
    error: str | None = None


WorkflowPlan = ActionMacroPlan
WorkflowStepResult = ActionMacroStepResult
WorkflowResult = ActionMacroResult
