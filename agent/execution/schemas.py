from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agent.capabilities.tools.schemas import ToolCall
from agent.executor.results import ToolResult


class ActionAttemptResult(BaseModel):
    attempt_number: int
    execution_number: int
    tool_call: dict[str, Any]
    tool_result: dict[str, Any]
    reflection_decision: dict[str, Any]


class ActionRunResult(BaseModel):
    tool_call: ToolCall
    final_tool_result: ToolResult
    attempts: list[ActionAttemptResult] = Field(default_factory=list)
    success: bool = False
    stopped: bool = False
    stop_reason: str | None = None
    retry_count: int = 0
    reflection_trace: list[dict[str, Any]] = Field(default_factory=list)
