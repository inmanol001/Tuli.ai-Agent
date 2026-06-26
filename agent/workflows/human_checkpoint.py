from __future__ import annotations

from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


HumanCheckpointKind = Literal[
    "missing_info",
    "preference",
    "approval",
    "safety_confirmation",
    "visual_validation",
    "correction_request",
]


class HumanCheckpoint(BaseModel):
    checkpoint_id: str = Field(default_factory=lambda: uuid4().hex)
    workflow_id: str
    step_id: str | None = None
    kind: HumanCheckpointKind
    question: str
    options: list[str] = Field(default_factory=list)
    required: bool = True
    resolved: bool = False
    user_response: str | None = None
    approved: bool | None = None


class HumanCheckpointResponse(BaseModel):
    status: str = "waiting_user_input"
    needs_user_input: bool = True
    text: str
    workflow_id: str
    current_step_id: str | None = None
    checkpoint_id: str


class HumanCheckpointManager:
    """Create, persist, and resolve user-facing checkpoints for workflow pauses."""

    def create_checkpoint(
        self,
        *,
        workflow_id: str,
        kind: HumanCheckpointKind,
        question: str,
        step_id: str | None = None,
        options: list[str] | None = None,
        required: bool = True,
    ) -> HumanCheckpoint:
        return HumanCheckpoint(
            workflow_id=workflow_id,
            step_id=step_id,
            kind=kind,
            question=question,
            options=list(options or []),
            required=required,
        )

    def pause_plan(
        self,
        plan,
        checkpoint: HumanCheckpoint,
    ):
        plan.active_checkpoint_id = checkpoint.checkpoint_id
        plan.checkpoints.append(checkpoint.model_dump(mode="json"))
        self._mark_step_for_checkpoint(plan, checkpoint)
        self._set_plan_status_for_checkpoint(plan, checkpoint.kind)
        self._stash_checkpoint_state(plan, checkpoint)
        return plan

    def resolve_checkpoint(
        self,
        plan,
        checkpoint_id: str,
        *,
        user_response: str | None = None,
        approved: bool | None = None,
        state_updates: dict[str, Any] | None = None,
    ):
        checkpoint = self._get_checkpoint(plan, checkpoint_id)
        checkpoint["resolved"] = True
        checkpoint["user_response"] = user_response
        if approved is not None:
            checkpoint["approved"] = approved
        plan.active_checkpoint_id = None
        if state_updates:
            plan.state.update(state_updates)
        plan.state["active_checkpoint"] = None
        plan.state["last_checkpoint_response"] = user_response
        self._apply_resolution_to_step(
            plan,
            checkpoint,
            approved=approved,
            user_response=user_response,
        )
        self._set_resume_status(plan)
        return plan

    def build_response(
        self,
        checkpoint: HumanCheckpoint,
        *,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        return HumanCheckpointResponse(
            text=checkpoint.question,
            workflow_id=checkpoint.workflow_id,
            current_step_id=checkpoint.step_id,
            checkpoint_id=checkpoint.checkpoint_id,
        ).model_dump(mode="json")

    def to_agent_response_payload(
        self,
        checkpoint: HumanCheckpoint,
    ) -> dict[str, Any]:
        return HumanCheckpointResponse(
            text=checkpoint.question,
            workflow_id=checkpoint.workflow_id,
            current_step_id=checkpoint.step_id,
            checkpoint_id=checkpoint.checkpoint_id,
        ).model_dump(mode="json")

    def _mark_step_for_checkpoint(self, plan, checkpoint: HumanCheckpoint) -> None:
        if checkpoint.step_id is None:
            return
        step = self._get_step(plan, checkpoint.step_id)
        if checkpoint.kind in {"approval", "safety_confirmation", "visual_validation"}:
            step.status = "waiting_approval"
            step.requires_approval = True
            step.approval_request = checkpoint.question
        else:
            step.status = "waiting_user_input"
            step.requires_user_input = True
            step.question = checkpoint.question

    def _set_plan_status_for_checkpoint(self, plan, kind: HumanCheckpointKind) -> None:
        if kind in {"approval", "safety_confirmation", "visual_validation"}:
            plan.status = "waiting_approval"
        else:
            plan.status = "waiting_user_input"

    def _stash_checkpoint_state(self, plan, checkpoint: HumanCheckpoint) -> None:
        plan.state["active_checkpoint"] = checkpoint.model_dump(mode="json")

    def _get_checkpoint(self, plan, checkpoint_id: str) -> dict[str, Any]:
        for checkpoint in plan.checkpoints:
            if checkpoint.get("checkpoint_id") == checkpoint_id:
                return checkpoint
        raise KeyError(f"checkpoint not found: {checkpoint_id}")

    def _apply_resolution_to_step(
        self,
        plan,
        checkpoint: dict[str, Any],
        *,
        approved: bool | None,
        user_response: str | None,
    ) -> None:
        step_id = checkpoint.get("step_id")
        if step_id is None:
            return
        step = self._get_step(plan, step_id)
        if user_response is not None:
            step.user_answer = user_response
        if approved is not None:
            step.approved = approved
            if approved:
                step.status = "approved"
                step.result_summary = user_response or checkpoint.get("question")
            else:
                step.status = "needs_revision"
        elif checkpoint.get("kind") in {"missing_info", "preference", "correction_request"}:
            step.status = "completed"
            step.result_summary = user_response or checkpoint.get("question")
        plan.state["last_checkpoint_response"] = user_response

    def _set_resume_status(self, plan) -> None:
        if any(step.status == "needs_revision" for step in plan.steps):
            plan.status = "blocked"
            return
        if any(
            step.status in {"waiting_user_input", "waiting_approval"}
            for step in plan.steps
        ):
            return
        plan.status = "running"

    def _get_step(self, plan, step_id: str):
        for step in plan.steps:
            if step.id == step_id:
                return step
        raise KeyError(f"workflow step not found: {step_id}")


WorkflowHumanCheckpoint = HumanCheckpoint
WorkflowHumanCheckpointManager = HumanCheckpointManager
