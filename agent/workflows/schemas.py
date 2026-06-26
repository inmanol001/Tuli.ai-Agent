from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from agent.capabilities.tools.schemas import ToolCall


FullWorkflowStatus = Literal[
    "not_selected",
    "selected",
    "needs_clarification",
    "waiting_user_input",
    "waiting_approval",
    "needs_revision",
    "simulated",
    "blocked_missing_tools",
    "blocked",
    "running",
    "completed",
    "failed",
    "cancelled",
]

FullWorkflowPhaseStatus = Literal[
    "pending",
    "running",
    "completed",
    "waiting_user_input",
    "waiting_approval",
    "needs_revision",
    "simulated",
    "skipped",
    "blocked_missing_tools",
    "failed",
    "blocked",
    "cancelled",
]

FullWorkflowStepKind = Literal[
    "reason",
    "tool",
    "action_macro",
    "observe",
    "verify",
    "wait",
    "branch",
    "ask_user",
    "approval",
    "simulated",
    "blocked_missing_tools",
]


class FullWorkflowState(BaseModel):
    data: dict[str, Any] = Field(default_factory=dict)

    def get_value(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set_value(self, key: str, value: Any) -> None:
        self.data[key] = value


class FullWorkflowPlan(BaseModel):
    selected: bool = False
    workflow_name: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    status: FullWorkflowStatus = "not_selected"
    reason: str | None = None
    missing_info: list[str] = Field(default_factory=list)
    simulation_mode: bool = False
    missing_tools: list[str] = Field(default_factory=list)


class FullWorkflowStepDefinition(BaseModel):
    phase_name: str
    kind: FullWorkflowStepKind
    description: str
    required_tools: list[str] = Field(default_factory=list)
    can_run_now: bool = False
    reason_task: str | None = None
    output_key: str | None = None
    tool_name: str | None = None
    tool_goal: str | None = None
    allowed_tools: list[str] = Field(default_factory=list)
    expected_result: str | None = None
    tool_arguments: dict[str, Any] = Field(default_factory=dict)
    simulated_actions: list[str] = Field(default_factory=list)
    missing_tools: list[str] = Field(default_factory=list)
    phase_status: FullWorkflowPhaseStatus = "pending"


class FullWorkflowPhaseSpec(FullWorkflowStepDefinition):
    summary: str | None = None
    error: str | None = None


class FullWorkflowPhaseResult(BaseModel):
    phase_name: str
    kind: FullWorkflowStepKind | None = None
    status: FullWorkflowPhaseStatus
    summary: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    action_runs: list[dict[str, Any]] = Field(default_factory=list)
    reflection_traces: list[dict[str, Any]] = Field(default_factory=list)
    retry_count: int = 0
    requires_user_input: bool = False
    requires_approval: bool = False
    question: str | None = None
    approval_request: str | None = None
    checkpoint_id: str | None = None
    reasoning_output: str | None = None
    state_updates: dict[str, Any] = Field(default_factory=dict)
    simulated_actions: list[str] = Field(default_factory=list)
    missing_tools: list[str] = Field(default_factory=list)
    error: str | None = None
    stopped: bool = False
    stop_reason: str | None = None


class FullWorkflowResult(BaseModel):
    workflow_name: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    state: FullWorkflowState = Field(default_factory=FullWorkflowState)
    workflow_id: str | None = None
    plan_path: str | None = None
    status: FullWorkflowStatus = "running"
    phases: list[FullWorkflowPhaseResult] = Field(default_factory=list)
    success: bool = False
    simulation_mode: bool = False
    needs_user_input: bool = False
    needs_approval: bool = False
    question: str | None = None
    approval_request: str | None = None
    checkpoint_id: str | None = None
    current_step_id: str | None = None
    stopped_reason: str | None = None
    missing_tools: list[str] = Field(default_factory=list)
    error: str | None = None


class FullWorkflowFinalizerResult(BaseModel):
    text: str
    fallback: bool = True
    error: str | None = None


WorkflowState = FullWorkflowState
WorkflowPlan = FullWorkflowPlan
WorkflowStepKind = FullWorkflowStepKind
WorkflowStepDefinition = FullWorkflowStepDefinition
WorkflowPhaseSpec = FullWorkflowPhaseSpec
WorkflowPhaseResult = FullWorkflowPhaseResult
WorkflowResult = FullWorkflowResult
WorkflowFinalizerResult = FullWorkflowFinalizerResult
