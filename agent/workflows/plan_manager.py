from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.workflows.requirement_checker import (
    RequirementCheckResult,
    RequirementChecker,
    RequirementContext,
)
from agent.workflows.human_checkpoint import (
    HumanCheckpoint,
    HumanCheckpointManager,
    HumanCheckpointKind,
)
from agent.workflows.plan_schemas import (
    WorkflowExecutionPlan,
    WorkflowPlanStatus,
    WorkflowPlanStep,
)


class WorkflowPlanManager:
    """Manage a live runtime plan for one workflow execution."""

    def __init__(self, base_dir: str | Path = "runtime/plans") -> None:
        self.base_dir = Path(base_dir)
        self.requirement_checker = RequirementChecker()
        self.human_checkpoint_manager = HumanCheckpointManager()

    def create_plan(
        self,
        *,
        workflow_name: str,
        user_goal: str,
        session_id: str | None = None,
        steps: list[WorkflowPlanStep | dict[str, Any]] | None = None,
        state: dict[str, Any] | None = None,
        notes: list[str] | None = None,
        workflow_id: str | None = None,
        status: WorkflowPlanStatus = "planning",
    ) -> WorkflowExecutionPlan:
        now = self._now()
        return WorkflowExecutionPlan(
            workflow_id=workflow_id or self._new_workflow_id(),
            workflow_name=workflow_name,
            session_id=session_id,
            user_goal=user_goal,
            status=status,
            steps=[self._coerce_step(step) for step in (steps or [])],
            current_step_index=0,
            state=dict(state or {}),
            notes=list(notes or []),
            created_at=now,
            updated_at=now,
        )

    def load_plan(
        self,
        workflow_id: str,
        *,
        session_id: str | None = None,
    ) -> WorkflowExecutionPlan:
        json_path = self._plan_json_path(workflow_id, session_id=session_id)
        if json_path.exists():
            return WorkflowExecutionPlan.model_validate_json(json_path.read_text())

        markdown_path = self._plan_markdown_path(workflow_id, session_id=session_id)
        if not markdown_path.exists():
            raise FileNotFoundError(f"workflow plan not found: {workflow_id}")

        return self._plan_from_markdown(
            markdown_path.read_text(),
            workflow_id=workflow_id,
            session_id=session_id,
        )

    def save_plan(self, plan: WorkflowExecutionPlan) -> WorkflowExecutionPlan:
        plan.updated_at = self._now()
        markdown_path = self._plan_markdown_path(
            plan.workflow_id, session_id=plan.session_id
        )
        json_path = self._plan_json_path(plan.workflow_id, session_id=plan.session_id)
        markdown_path.parent.mkdir(parents=True, exist_ok=True)
        markdown_path.write_text(self.render_markdown(plan))
        json_path.write_text(plan.model_dump_json(indent=2))
        return plan

    def render_markdown(self, plan: WorkflowExecutionPlan) -> str:
        lines = [
            f"# Workflow Plan: {plan.workflow_name}",
            "",
            "## Objetivo",
            plan.user_goal,
            "",
            "## Estado",
            plan.status,
            "",
            "## Pasos",
            "",
        ]
        for step in plan.steps:
            marker = "[x]" if step.status in {"completed", "approved"} else "[ ]"
            lines.append(f"- {marker} {step.title}")

        lines.extend(["", "## Datos"])
        if plan.state:
            for key, value in plan.state.items():
                lines.append(f"{self._pretty_key(key)}: {self._format_value(value)}")
        else:
            lines.append("Sin datos aún.")

        lines.extend(["", "## Último resultado"])
        lines.append(self._last_result(plan) or "Pendiente abrir el siguiente paso.")
        return "\n".join(lines).rstrip() + "\n"

    def mark_step_running(self, plan: WorkflowExecutionPlan, step_id: str) -> WorkflowExecutionPlan:
        step = self._get_step(plan, step_id)
        step.status = "running"
        self._set_current_step(plan, step_id)
        return self.save_plan(plan)

    def mark_step_completed(
        self,
        plan: WorkflowExecutionPlan,
        step_id: str,
        *,
        result_summary: str | None = None,
    ) -> WorkflowExecutionPlan:
        step = self._get_step(plan, step_id)
        step.status = "completed"
        step.result_summary = result_summary
        step.error = None
        self._advance_current_step(plan, step_id)
        return self.save_plan(plan)

    def mark_step_failed(
        self,
        plan: WorkflowExecutionPlan,
        step_id: str,
        *,
        error: str,
    ) -> WorkflowExecutionPlan:
        step = self._get_step(plan, step_id)
        step.status = "failed"
        step.error = error
        plan.status = "failed"
        self._set_current_step(plan, step_id)
        return self.save_plan(plan)

    def mark_step_blocked(
        self,
        plan: WorkflowExecutionPlan,
        step_id: str,
        *,
        reason: str,
    ) -> WorkflowExecutionPlan:
        step = self._get_step(plan, step_id)
        step.status = "blocked"
        step.error = reason
        plan.status = "blocked"
        self._set_current_step(plan, step_id)
        return self.save_plan(plan)

    def mark_step_waiting_user_input(
        self,
        plan: WorkflowExecutionPlan,
        step_id: str,
        *,
        question: str | None = None,
    ) -> WorkflowExecutionPlan:
        step = self._get_step(plan, step_id)
        step.status = "waiting_user_input"
        step.requires_user_input = True
        step.question = question
        plan.status = "waiting_user_input"
        self._set_current_step(plan, step_id)
        return self.save_plan(plan)

    def mark_step_waiting_approval(
        self,
        plan: WorkflowExecutionPlan,
        step_id: str,
        *,
        approval_request: str | None = None,
    ) -> WorkflowExecutionPlan:
        step = self._get_step(plan, step_id)
        step.status = "waiting_approval"
        step.requires_approval = True
        step.approval_request = approval_request
        plan.status = "waiting_approval"
        self._set_current_step(plan, step_id)
        return self.save_plan(plan)

    def add_note(self, plan: WorkflowExecutionPlan, note: str) -> WorkflowExecutionPlan:
        plan.notes.append(note)
        return self.save_plan(plan)

    def update_state(
        self, plan: WorkflowExecutionPlan, updates: dict[str, Any]
    ) -> WorkflowExecutionPlan:
        plan.state.update(updates)
        return self.save_plan(plan)

    def next_pending_step(self, plan: WorkflowExecutionPlan) -> WorkflowPlanStep | None:
        for step in plan.steps[plan.current_step_index :]:
            if step.status == "pending":
                return step
        for step in plan.steps:
            if step.status == "pending":
                return step
        return None

    def insert_step_after(
        self,
        plan: WorkflowExecutionPlan,
        after_step_id: str,
        step: WorkflowPlanStep | dict[str, Any],
    ) -> WorkflowExecutionPlan:
        new_step = self._coerce_step(step)
        for index, existing in enumerate(plan.steps):
            if existing.id == after_step_id:
                plan.steps.insert(index + 1, new_step)
                return self.save_plan(plan)
        plan.steps.append(new_step)
        return self.save_plan(plan)

    def skip_step(self, plan: WorkflowExecutionPlan, step_id: str) -> WorkflowExecutionPlan:
        step = self._get_step(plan, step_id)
        step.status = "skipped"
        self._advance_current_step(plan, step_id)
        return self.save_plan(plan)

    def check_requirements(
        self,
        plan: WorkflowExecutionPlan,
        step_id: str,
        *,
        requires_visual_validation: bool = False,
        requires_approval: bool = False,
        correction_request: bool = False,
    ) -> RequirementCheckResult:
        step = self._get_step(plan, step_id)
        result = self.requirement_checker.check(
            RequirementContext(
                workflow_name=plan.workflow_name,
                user_goal=plan.user_goal,
                step_kind=step.kind,
                step_title=step.title,
                state=plan.state,
                requires_visual_validation=requires_visual_validation,
                requires_approval=requires_approval,
                correction_request=correction_request,
            )
        )
        self.apply_requirement_check(plan, step_id, result)
        return result

    def apply_requirement_check(
        self,
        plan: WorkflowExecutionPlan,
        step_id: str,
        result: RequirementCheckResult,
    ) -> WorkflowExecutionPlan:
        step = self._get_step(plan, step_id)
        if result.needs_approval:
            checkpoint_kind: HumanCheckpointKind = (
                "safety_confirmation"
                if result.reason == "safety_confirmation"
                else "visual_validation"
                if result.reason == "visual_validation"
                else "approval"
            )
            checkpoint = self.human_checkpoint_manager.create_checkpoint(
                workflow_id=plan.workflow_id,
                step_id=step_id,
                kind=checkpoint_kind,
                question=result.approval_request or (result.questions[0] if result.questions else "¿Me das permiso para continuar?"),
                options=["approve", "reject"],
                required=True,
            )
            self.human_checkpoint_manager.pause_plan(plan, checkpoint)
        elif result.needs_user_input:
            checkpoint_kind: HumanCheckpointKind = (
                "correction_request"
                if result.reason == "correction_request"
                else "preference"
                if result.reason == "preference"
                else "missing_info"
            )
            checkpoint = self.human_checkpoint_manager.create_checkpoint(
                workflow_id=plan.workflow_id,
                step_id=step_id,
                kind=checkpoint_kind,
                question=result.questions[0] if result.questions else "¿Qué detalle falta?",
                options=[],
                required=True,
            )
            self.human_checkpoint_manager.pause_plan(plan, checkpoint)
        elif result.can_continue and plan.status in {"planning", "waiting_user_input", "waiting_approval"}:
            plan.status = "running"
        return self.save_plan(plan)

    def create_human_checkpoint(
        self,
        plan: WorkflowExecutionPlan,
        step_id: str | None,
        *,
        kind: HumanCheckpointKind,
        question: str,
        options: list[str] | None = None,
        required: bool = True,
    ) -> HumanCheckpoint:
        checkpoint = self.human_checkpoint_manager.create_checkpoint(
            workflow_id=plan.workflow_id,
            step_id=step_id,
            kind=kind,
            question=question,
            options=options,
            required=required,
        )
        self.human_checkpoint_manager.pause_plan(plan, checkpoint)
        self.save_plan(plan)
        return checkpoint

    def resolve_human_checkpoint(
        self,
        plan: WorkflowExecutionPlan,
        checkpoint_id: str,
        *,
        user_response: str | None = None,
        approved: bool | None = None,
        state_updates: dict[str, Any] | None = None,
    ) -> WorkflowExecutionPlan:
        self.human_checkpoint_manager.resolve_checkpoint(
            plan,
            checkpoint_id,
            user_response=user_response,
            approved=approved,
            state_updates=state_updates,
        )
        step = self._get_step_for_checkpoint(plan, checkpoint_id)
        if step is not None and step.status in {
            "completed",
            "approved",
            "rejected",
            "needs_revision",
        }:
            self._advance_current_step(plan, step.id)
        return self.save_plan(plan)

    def build_human_checkpoint_payload(
        self,
        plan: WorkflowExecutionPlan,
        step_id: str | None,
        *,
        kind: HumanCheckpointKind,
        question: str,
        options: list[str] | None = None,
        required: bool = True,
    ) -> dict[str, Any]:
        checkpoint = self.create_human_checkpoint(
            plan,
            step_id,
            kind=kind,
            question=question,
            options=options,
            required=required,
        )
        return self.human_checkpoint_manager.to_agent_response_payload(checkpoint)

    def _plan_dir(self, session_id: str | None = None) -> Path:
        if session_id:
            return self.base_dir / session_id
        return self.base_dir / "standalone"

    def _plan_markdown_path(
        self, workflow_id: str, *, session_id: str | None = None
    ) -> Path:
        return self._plan_dir(session_id) / f"{workflow_id}.md"

    def _plan_json_path(self, workflow_id: str, *, session_id: str | None = None) -> Path:
        return self._plan_dir(session_id) / f"{workflow_id}.json"

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _new_workflow_id(self) -> str:
        from uuid import uuid4

        return uuid4().hex

    def _coerce_step(self, step: WorkflowPlanStep | dict[str, Any]) -> WorkflowPlanStep:
        if isinstance(step, WorkflowPlanStep):
            return step
        return WorkflowPlanStep.model_validate(step)

    def _get_step(self, plan: WorkflowExecutionPlan, step_id: str) -> WorkflowPlanStep:
        for step in plan.steps:
            if step.id == step_id:
                return step
        raise KeyError(f"workflow step not found: {step_id}")

    def _get_step_for_checkpoint(
        self, plan: WorkflowExecutionPlan, checkpoint_id: str
    ) -> WorkflowPlanStep | None:
        for checkpoint in plan.checkpoints:
            if checkpoint.get("checkpoint_id") == checkpoint_id:
                step_id = checkpoint.get("step_id")
                if step_id is None:
                    return None
                return self._get_step(plan, step_id)
        return None

    def _set_current_step(self, plan: WorkflowExecutionPlan, step_id: str) -> None:
        for index, step in enumerate(plan.steps):
            if step.id == step_id:
                plan.current_step_index = index
                return

    def _advance_current_step(self, plan: WorkflowExecutionPlan, step_id: str) -> None:
        for index, step in enumerate(plan.steps):
            if step.id == step_id:
                plan.current_step_index = min(index + 1, len(plan.steps))
                return

    def _last_result(self, plan: WorkflowExecutionPlan) -> str | None:
        for step in reversed(plan.steps):
            if step.result_summary:
                return step.result_summary
            if step.error:
                return step.error
            if step.question:
                return step.question
        return None

    def _pretty_key(self, key: str) -> str:
        return key.replace("_", " ").capitalize()

    def _format_value(self, value: Any) -> str:
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False)
        return str(value)

    def _plan_from_markdown(
        self,
        markdown: str,
        workflow_id: str,
        session_id: str | None,
    ) -> WorkflowExecutionPlan:
        lines = [line.rstrip() for line in markdown.splitlines()]
        workflow_name = self._extract_after_heading(lines, "# Workflow Plan:") or "unknown"
        user_goal = self._extract_section(lines, "## Objetivo") or ""
        raw_status = self._extract_section(lines, "## Estado") or "planning"
        status: WorkflowPlanStatus = raw_status if raw_status in {
            "planning",
            "waiting_user_input",
            "waiting_approval",
            "running",
            "blocked",
            "completed",
            "failed",
            "cancelled",
        } else "planning"
        steps = self._extract_steps(lines)
        state = self._extract_state(lines)
        return WorkflowExecutionPlan(
            workflow_id=workflow_id,
            workflow_name=workflow_name,
            session_id=session_id,
            user_goal=user_goal,
            status=status,
            steps=steps,
            current_step_index=0,
            state=state,
            notes=[],
            created_at=self._now(),
            updated_at=self._now(),
        )

    def _extract_after_heading(self, lines: list[str], prefix: str) -> str | None:
        for line in lines:
            if line.startswith(prefix):
                return line[len(prefix) :].strip()
        return None

    def _extract_section(self, lines: list[str], header: str) -> str | None:
        try:
            start = lines.index(header) + 1
        except ValueError:
            return None
        values: list[str] = []
        for line in lines[start:]:
            if line.startswith("## "):
                break
            if line.strip():
                values.append(line.strip())
        return "\n".join(values).strip() or None

    def _extract_steps(self, lines: list[str]) -> list[WorkflowPlanStep]:
        steps: list[WorkflowPlanStep] = []
        in_steps = False
        for line in lines:
            if line.startswith("## Pasos"):
                in_steps = True
                continue
            if in_steps and line.startswith("## "):
                break
            if in_steps and line.startswith("- ["):
                checked = line.startswith("- [x]")
                title = line.split("] ", 1)[1].strip()
                steps.append(
                    WorkflowPlanStep(
                        title=title,
                        kind="step",
                        status="completed" if checked else "pending",
                    )
                )
        return steps

    def _extract_state(self, lines: list[str]) -> dict[str, Any]:
        state: dict[str, Any] = {}
        try:
            start = lines.index("## Datos") + 1
        except ValueError:
            return state
        for line in lines[start:]:
            if line.startswith("## "):
                break
            if ":" in line:
                key, value = line.split(":", 1)
                state[key.strip().lower().replace(" ", "_")] = value.strip()
        return state
