from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


WorkflowPlanStatus = Literal[
    "planning",
    "waiting_user_input",
    "waiting_approval",
    "running",
    "blocked",
    "completed",
    "failed",
    "cancelled",
]

WorkflowStepStatus = Literal[
    "pending",
    "running",
    "completed",
    "failed",
    "skipped",
    "waiting_user_input",
    "waiting_approval",
    "approved",
    "rejected",
    "needs_revision",
    "blocked",
]


class WorkflowPlanStep(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    title: str
    kind: str
    status: WorkflowStepStatus = "pending"
    description: str | None = None
    expected_result: str | None = None
    selected_tool: str | None = None
    selected_macro: str | None = None
    requires_user_input: bool = False
    requires_approval: bool = False
    question: str | None = None
    approval_request: str | None = None
    user_answer: str | None = None
    approved: bool | None = None
    result_summary: str | None = None
    error: str | None = None


class WorkflowExecutionPlan(BaseModel):
    workflow_id: str = Field(default_factory=lambda: uuid4().hex)
    workflow_name: str
    session_id: str | None = None
    user_goal: str
    status: WorkflowPlanStatus = "planning"
    steps: list[WorkflowPlanStep] = Field(default_factory=list)
    current_step_index: int = 0
    state: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
    checkpoints: list[dict[str, Any]] = Field(default_factory=list)
    active_checkpoint_id: str | None = None
    created_at: str
    updated_at: str


WorkflowPlan = WorkflowExecutionPlan
