from __future__ import annotations

from typing import Any

from agent.action_macros.executor import ActionMacroExecutor
from agent.action_macros.schemas import ActionMacroPlan
from agent.capabilities.tools.registry import ToolRegistry
from agent.execution.action_runner import ActionRunner
from agent.executor.executor import Executor
from agent.gateway.message_types import ContextPackage
from agent.gateway.session_manager import SessionState
from agent.models.tool_planner import ToolPlanner
from agent.reflection.checker import ReflectionChecker
from agent.router.router_schema import RouterDecision
from agent.workflows.plan_manager import WorkflowPlanManager
from agent.workflows.plan_schemas import WorkflowExecutionPlan, WorkflowPlanStep
from agent.workflows.reasoner import WorkflowReasoner
from agent.workflows.schemas import (
    FullWorkflowPhaseResult,
    FullWorkflowPlan,
    FullWorkflowResult,
    FullWorkflowState,
    FullWorkflowStepDefinition,
)


class WorkflowLoopController:
    """Run a full workflow with a live runtime plan and hard execution limits."""

    def __init__(
        self,
        executor: Executor,
        action_runner: ActionRunner | None = None,
        action_macro_executor: ActionMacroExecutor | None = None,
        reasoner: WorkflowReasoner | None = None,
        tool_planner: ToolPlanner | None = None,
        tool_registry: ToolRegistry | None = None,
        plan_manager: WorkflowPlanManager | None = None,
        reflection_checker: ReflectionChecker | None = None,
        max_steps: int = 10,
        max_tool_calls: int = 15,
        max_retries_per_tool: int = 2,
        max_reasoning_steps: int = 5,
    ) -> None:
        self.executor = executor
        self.reflection_checker = reflection_checker or ReflectionChecker()
        self.action_runner = action_runner or ActionRunner(
            executor=self.executor,
            reflection_checker=self.reflection_checker,
            max_retries=max_retries_per_tool,
        )
        self.action_macro_executor = action_macro_executor or ActionMacroExecutor(
            executor=self.executor,
            reflection_checker=self.reflection_checker,
            action_runner=self.action_runner,
            max_retries=max_retries_per_tool,
        )
        self.reasoner = reasoner or WorkflowReasoner()
        self.tool_planner = tool_planner or ToolPlanner()
        self.tool_registry = tool_registry or ToolRegistry()
        self.plan_manager = plan_manager or WorkflowPlanManager()
        self.max_steps = max_steps
        self.max_tool_calls = max_tool_calls
        self.max_retries_per_tool = max_retries_per_tool
        self.max_reasoning_steps = max_reasoning_steps

    def run(
        self,
        plan: FullWorkflowPlan,
        workflow: Any,
        context: ContextPackage,
        session: SessionState,
        existing_plan: WorkflowExecutionPlan | None = None,
    ) -> FullWorkflowResult:
        workflow_name = plan.workflow_name or getattr(workflow, "name", "unknown")

        try:
            step_defs = list(workflow.build_phases(dict(plan.inputs)))
        except Exception as exc:
            return FullWorkflowResult(
                workflow_name=workflow_name,
                inputs=dict(plan.inputs),
                state=FullWorkflowState(data=dict(plan.inputs)),
                workflow_id=plan.workflow_id,
                plan_path=str(
                    self.plan_manager._plan_markdown_path(
                        plan.workflow_id, session_id=plan.session_id
                    )
                ),
                status="failed",
                phases=[],
                success=False,
                simulation_mode=plan.simulation_mode,
                error=str(exc),
            )

        live_plan = (
            self._hydrate_existing_plan(existing_plan, workflow_name)
            if existing_plan is not None
            else self._create_live_plan(
                plan=plan,
                workflow_name=workflow_name,
                context=context,
                session=session,
                step_defs=step_defs,
            )
        )

        phases: list[FullWorkflowPhaseResult] = []
        missing_tools = set(plan.missing_tools)
        tool_call_count = 0
        reasoning_count = 0

        while live_plan.current_step_index < len(live_plan.steps):
            if len(phases) >= self.max_steps:
                return self._limit_result(
                    live_plan=live_plan,
                    workflow_name=workflow_name,
                    plan=plan,
                    phases=phases,
                    missing_tools=missing_tools,
                    tool_call_count=tool_call_count,
                    reasoning_count=reasoning_count,
                )

            step_index = live_plan.current_step_index
            step_plan = live_plan.steps[step_index]
            step_def = step_defs[step_index]
            live_plan = self.plan_manager.mark_step_running(live_plan, step_plan.id)

            requirement_result = self.plan_manager.check_requirements(
                live_plan,
                step_plan.id,
                requires_visual_validation=step_def.kind == "verify",
                requires_approval=step_def.kind == "approval",
                correction_request=step_def.kind == "ask_user",
            )
            if not requirement_result.can_continue:
                paused_phase = self._paused_phase_result(
                    step_def=step_def,
                    step_plan=step_plan,
                    live_plan=live_plan,
                )
                phases.append(paused_phase)
                missing_tools.update(step_def.missing_tools)
                return self._paused_result(
                    live_plan=live_plan,
                    workflow_name=workflow_name,
                    plan=plan,
                    phases=phases,
                    missing_tools=missing_tools,
                    phase_result=paused_phase,
                )

            phase_result, tool_delta, reasoning_delta = self._run_step(
                plan=plan,
                live_plan=live_plan,
                workflow_name=workflow_name,
                context=context,
                session=session,
                step_plan=step_plan,
                step_def=step_def,
                tool_call_count=tool_call_count,
                reasoning_count=reasoning_count,
            )
            phases.append(phase_result)
            missing_tools.update(phase_result.missing_tools)
            tool_call_count += tool_delta
            reasoning_count += reasoning_delta
            live_plan = self._apply_phase_result_to_plan(
                live_plan,
                step_plan.id,
                phase_result,
            )

            if phase_result.status in {"waiting_user_input", "waiting_approval"}:
                return self._paused_result(
                    live_plan=live_plan,
                    workflow_name=workflow_name,
                    plan=plan,
                    phases=phases,
                    missing_tools=missing_tools,
                    phase_result=phase_result,
                )

            if phase_result.status == "blocked_missing_tools":
                status = "simulated" if plan.simulation_mode else "blocked"
                return self._final_result(
                    live_plan=live_plan,
                    workflow_name=workflow_name,
                    plan=plan,
                    phases=phases,
                    missing_tools=missing_tools,
                    success=False,
                    status=status,
                    stopped_reason=phase_result.stop_reason or "blocked_missing_tools",
                )

            if phase_result.status == "blocked" and phase_result.stop_reason == "workflow_limits_exceeded":
                return self._final_result(
                    live_plan=live_plan,
                    workflow_name=workflow_name,
                    plan=plan,
                    phases=phases,
                    missing_tools=missing_tools,
                    success=False,
                    status="blocked",
                    stopped_reason="workflow_limits_exceeded",
                )

            if phase_result.status in {"failed", "blocked"}:
                return self._final_result(
                    live_plan=live_plan,
                    workflow_name=workflow_name,
                    plan=plan,
                    phases=phases,
                    missing_tools=missing_tools,
                    success=False,
                    status="failed",
                    stopped_reason=phase_result.stop_reason or phase_result.error or "workflow_failed",
                )

        return self._final_result(
            live_plan=live_plan,
            workflow_name=workflow_name,
            plan=plan,
            phases=phases,
            missing_tools=missing_tools,
            success=True,
            status="completed",
            stopped_reason=None,
        )

    def _hydrate_existing_plan(
        self,
        existing_plan: WorkflowExecutionPlan,
        workflow_name: str,
    ) -> WorkflowExecutionPlan:
        existing_plan.workflow_name = existing_plan.workflow_name or workflow_name
        if existing_plan.status in {"planning", "selected"}:
            existing_plan.status = "running"
        return self.plan_manager.save_plan(existing_plan)

    def _create_live_plan(
        self,
        *,
        plan: FullWorkflowPlan,
        workflow_name: str,
        context: ContextPackage,
        session: SessionState,
        step_defs: list[FullWorkflowStepDefinition],
    ) -> WorkflowExecutionPlan:
        live_plan = self.plan_manager.create_plan(
            workflow_name=workflow_name,
            user_goal=context.user_message,
            session_id=session.session_id,
            steps=[self._to_plan_step(step_def) for step_def in step_defs],
            state={
                **dict(plan.inputs),
                "original_user_message": context.user_message,
                "workflow_name": workflow_name,
                "inputs": dict(plan.inputs),
            },
            status="planning",
        )
        live_plan.status = "running"
        return self.plan_manager.save_plan(live_plan)

    def _apply_phase_result_to_plan(
        self,
        plan: WorkflowExecutionPlan,
        step_id: str,
        phase_result: FullWorkflowPhaseResult,
    ) -> WorkflowExecutionPlan:
        if phase_result.state_updates:
            plan.state.update(phase_result.state_updates)

        if phase_result.status in {"completed", "simulated"}:
            plan = self.plan_manager.mark_step_completed(
                plan,
                step_id,
                result_summary=phase_result.summary or phase_result.reasoning_output,
            )
        elif phase_result.status == "waiting_user_input":
            plan = self.plan_manager.mark_step_waiting_user_input(
                plan,
                step_id,
                question=phase_result.question or phase_result.summary,
            )
        elif phase_result.status == "waiting_approval":
            plan = self.plan_manager.mark_step_waiting_approval(
                plan,
                step_id,
                approval_request=phase_result.approval_request or phase_result.summary,
            )
        elif phase_result.status == "failed":
            plan = self.plan_manager.mark_step_failed(
                plan,
                step_id,
                error=phase_result.error or phase_result.stop_reason or "workflow_failed",
            )
        elif phase_result.status == "blocked_missing_tools" or (
            phase_result.status == "blocked" and phase_result.stop_reason == "workflow_limits_exceeded"
        ):
            plan = self.plan_manager.mark_step_blocked(
                plan,
                step_id,
                reason=phase_result.stop_reason or "blocked_missing_tools",
            )
        elif phase_result.status == "blocked":
            plan = self.plan_manager.mark_step_blocked(
                plan,
                step_id,
                reason=phase_result.stop_reason or phase_result.error or "workflow_blocked",
            )
        else:
            self.plan_manager.save_plan(plan)

        if phase_result.status in {"completed", "simulated"}:
            plan.status = "running" if plan.current_step_index < len(plan.steps) else "completed"
            self.plan_manager.save_plan(plan)
        return plan

    def _to_plan_step(self, step_def: FullWorkflowStepDefinition) -> WorkflowPlanStep:
        return WorkflowPlanStep(
            title=step_def.description or step_def.phase_name,
            kind=step_def.kind,
            description=step_def.description,
            expected_result=step_def.expected_result,
            selected_tool=step_def.tool_name
            or (step_def.allowed_tools[0] if step_def.allowed_tools else None),
            selected_macro=step_def.tool_name
            if step_def.kind in {"action_macro", "macro"}
            else None,
        )

    def _run_step(
        self,
        *,
        plan: FullWorkflowPlan,
        live_plan: WorkflowExecutionPlan,
        workflow_name: str,
        context: ContextPackage,
        session: SessionState,
        step_plan: WorkflowPlanStep,
        step_def: FullWorkflowStepDefinition,
        tool_call_count: int,
        reasoning_count: int,
    ) -> tuple[FullWorkflowPhaseResult, int, int]:
        if step_def.kind == "reason":
            return self._run_reason_step(
                live_plan=live_plan,
                workflow_name=workflow_name,
                step_def=step_def,
                reasoning_count=reasoning_count,
            )
        if step_def.kind == "tool":
            return self._run_tool_step(
                live_plan=live_plan,
                workflow_name=workflow_name,
                context=context,
                session=session,
                step_def=step_def,
                tool_call_count=tool_call_count,
            )
        if step_def.kind in {"action_macro", "macro"}:
            return self._run_macro_step(
                live_plan=live_plan,
                workflow_name=workflow_name,
                step_def=step_def,
                tool_call_count=tool_call_count,
            )
        if step_def.kind == "observe":
            return self._run_observe_step(
                live_plan=live_plan,
                workflow_name=workflow_name,
                step_def=step_def,
                reasoning_count=reasoning_count,
            )
        if step_def.kind == "verify":
            return self._run_verify_step(
                live_plan=live_plan,
                workflow_name=workflow_name,
                step_def=step_def,
                reasoning_count=reasoning_count,
            )
        if step_def.kind == "wait":
            return self._run_wait_step(step_def)
        if step_def.kind == "branch":
            return self._run_branch_step(
                live_plan=live_plan,
                workflow_name=workflow_name,
                step_def=step_def,
                reasoning_count=reasoning_count,
            )
        if step_def.kind == "ask_user":
            return self._run_ask_user_step(live_plan=live_plan, step_def=step_def, step_plan=step_plan)
        if step_def.kind == "approval":
            return self._run_approval_step(
                live_plan=live_plan,
                step_def=step_def,
                step_plan=step_plan,
            )

        return (
            FullWorkflowPhaseResult(
                phase_name=step_def.phase_name,
                kind=step_def.kind,
                status="completed",
                summary=step_def.description,
                missing_tools=list(step_def.missing_tools),
                state_updates=self._base_state_updates(step_def),
            ),
            0,
            0,
        )

    def _run_reason_step(
        self,
        *,
        live_plan: WorkflowExecutionPlan,
        workflow_name: str,
        step_def: FullWorkflowStepDefinition,
        reasoning_count: int,
    ) -> tuple[FullWorkflowPhaseResult, int, int]:
        if reasoning_count >= self.max_reasoning_steps:
            return self._limit_phase(step_def, "reasoning"), 0, 0

        task = step_def.reason_task or step_def.description
        reason_result = self.reasoner.reason(
            workflow_name=workflow_name,
            phase_name=step_def.phase_name,
            task=task,
            state=FullWorkflowState(data=dict(live_plan.state)),
            inputs=dict(live_plan.state),
        )
        if reason_result.error and not reason_result.text:
            return (
                FullWorkflowPhaseResult(
                    phase_name=step_def.phase_name,
                    kind=step_def.kind,
                    status="failed",
                    summary=step_def.description,
                    reasoning_output=reason_result.text,
                    error=reason_result.error,
                    stopped=True,
                    stop_reason="reasoner_failed",
                    missing_tools=list(step_def.missing_tools),
                ),
                0,
                1,
            )

        state_updates = self._base_state_updates(step_def)
        state_updates["last_reasoning"] = reason_result.text
        if step_def.output_key:
            state_updates[step_def.output_key] = reason_result.text

        return (
            FullWorkflowPhaseResult(
                phase_name=step_def.phase_name,
                kind=step_def.kind,
                status="completed",
                summary=step_def.description,
                reasoning_output=reason_result.text,
                state_updates=state_updates,
                missing_tools=list(step_def.missing_tools),
            ),
            0,
            1,
        )

    def _run_branch_step(
        self,
        *,
        live_plan: WorkflowExecutionPlan,
        workflow_name: str,
        step_def: FullWorkflowStepDefinition,
        reasoning_count: int,
    ) -> tuple[FullWorkflowPhaseResult, int, int]:
        if reasoning_count >= self.max_reasoning_steps:
            return self._limit_phase(step_def, "reasoning"), 0, 0

        task = step_def.reason_task or step_def.description
        reason_result = self.reasoner.reason(
            workflow_name=workflow_name,
            phase_name=step_def.phase_name,
            task=task,
            state=FullWorkflowState(data=dict(live_plan.state)),
            inputs=dict(live_plan.state),
        )
        state_updates = self._base_state_updates(step_def)
        state_updates["last_branch"] = reason_result.text
        if step_def.output_key:
            state_updates[step_def.output_key] = reason_result.text

        return (
            FullWorkflowPhaseResult(
                phase_name=step_def.phase_name,
                kind=step_def.kind,
                status="completed",
                summary=step_def.description,
                reasoning_output=reason_result.text,
                state_updates=state_updates,
                missing_tools=list(step_def.missing_tools),
            ),
            0,
            1,
        )

    def _run_tool_step(
        self,
        *,
        live_plan: WorkflowExecutionPlan,
        workflow_name: str,
        context: ContextPackage,
        session: SessionState,
        step_def: FullWorkflowStepDefinition,
        tool_call_count: int,
    ) -> tuple[FullWorkflowPhaseResult, int, int]:
        allowed_tools = list(step_def.allowed_tools)
        if not allowed_tools and step_def.tool_name:
            allowed_tools = [step_def.tool_name]

        if not step_def.can_run_now:
            return (
                FullWorkflowPhaseResult(
                    phase_name=step_def.phase_name,
                    kind=step_def.kind,
                    status="blocked_missing_tools",
                    summary=step_def.description,
                    simulated_actions=list(step_def.simulated_actions),
                    missing_tools=list(step_def.missing_tools) or allowed_tools or ["tool"],
                    stopped=True,
                    stop_reason="blocked_missing_tools",
                ),
                0,
                0,
            )

        active_tools = self.tool_registry.find_active(allowed_tools)
        missing_tools = [
            name
            for name in allowed_tools
            if self.tool_registry.get(name) is None or not self.tool_registry.get(name).active
        ]
        if not active_tools:
            return (
                FullWorkflowPhaseResult(
                    phase_name=step_def.phase_name,
                    kind=step_def.kind,
                    status="blocked_missing_tools",
                    summary=step_def.description,
                    simulated_actions=list(step_def.simulated_actions),
                    missing_tools=missing_tools or list(step_def.missing_tools) or allowed_tools,
                    stopped=True,
                    stop_reason="blocked_missing_tools",
                ),
                0,
                0,
            )

        phase_context = ContextPackage(
            system_prompt=(
                "You are the tool-calling hands for one phase of a local workflow. "
                "Choose the best available tool call for this phase. "
                "Do not answer normally if a matching tool is available. "
                "Do not invent tool results."
            ),
            user_message=(
                f"Original user request: {context.user_message}\n"
                f"Workflow: {workflow_name}\n"
                f"Session: {session.session_id}\n"
                f"Phase: {step_def.phase_name}\n"
                f"Phase goal: {step_def.tool_goal or step_def.description}\n"
                f"Expected result: {step_def.expected_result or ''}\n"
                f"Workflow state: {live_plan.state}\n"
                f"Tool argument hints: {step_def.tool_arguments}"
            ),
            router_decision=RouterDecision(
                intent="action",
                domain="workflow",
                action="workflow_tool_phase",
                route="action_ready",
                needs_tool=True,
                risk_level="low",
            ),
            recent_history=[],
            session_state={
                "pending_clarification": None,
                "pending_confirmation": None,
                "previous_route": "action_ready",
                "current_route": "action_ready",
            },
            selected_plugins=[],
            selected_skills=[],
            selected_tools=[tool.model_dump(mode="json") for tool in active_tools],
            rag_snippets=[],
            safety_rules=[
                "Use only the tools selected for this workflow phase.",
                "Do not invent tool results.",
                "If no matching tool exists, return no tool call.",
            ],
            task_instruction=step_def.tool_goal or step_def.description,
        )

        planner_result = self.tool_planner.plan(phase_context)
        if planner_result.error:
            return (
                FullWorkflowPhaseResult(
                    phase_name=step_def.phase_name,
                    kind=step_def.kind,
                    status="failed",
                    summary=step_def.description,
                    error=planner_result.error,
                    stopped=True,
                    stop_reason="tool_planner_failed",
                    missing_tools=missing_tools,
                ),
                0,
                0,
            )

        if not planner_result.tool_calls:
            return (
                FullWorkflowPhaseResult(
                    phase_name=step_def.phase_name,
                    kind=step_def.kind,
                    status="failed",
                    summary=step_def.description,
                    error="tool_planner_returned_no_tool_calls",
                    stopped=True,
                    stop_reason="tool_planner_returned_no_tool_calls",
                    missing_tools=missing_tools,
                ),
                0,
                0,
            )

        tool_results = []
        action_runs = []
        reflection_traces = []
        retry_count = 0
        executed_calls = 0
        for call in planner_result.tool_calls:
            if tool_call_count + executed_calls + 1 > self.max_tool_calls:
                return (
                    FullWorkflowPhaseResult(
                        phase_name=step_def.phase_name,
                        kind=step_def.kind,
                        status="blocked",
                        summary=step_def.description,
                        tool_calls=[tool.model_dump(mode="json") for tool in planner_result.tool_calls],
                        tool_results=[result.model_dump(mode="json") for result in tool_results],
                        action_runs=action_runs,
                        reflection_traces=reflection_traces,
                        retry_count=retry_count,
                        stopped=True,
                        stop_reason="workflow_limits_exceeded",
                        missing_tools=missing_tools,
                    ),
                    executed_calls,
                    0,
                )

            action_run = self.action_runner.run_tool_call(call)
            executed_calls += 1
            action_runs.append(action_run.model_dump(mode="json"))
            reflection_traces.append(
                {
                    "tool_call": call.model_dump(mode="json"),
                    "reflection_trace": action_run.reflection_trace,
                    "retry_count": action_run.retry_count,
                    "stop_reason": action_run.stop_reason,
                }
            )
            retry_count += action_run.retry_count
            tool_results.append(action_run.final_tool_result)

            if not action_run.success:
                return (
                    FullWorkflowPhaseResult(
                        phase_name=step_def.phase_name,
                        kind=step_def.kind,
                        status="failed",
                        summary=step_def.description,
                        tool_calls=[tool.model_dump(mode="json") for tool in planner_result.tool_calls],
                        tool_results=[result.model_dump(mode="json") for result in tool_results],
                        action_runs=action_runs,
                        reflection_traces=reflection_traces,
                        retry_count=retry_count,
                        error=action_run.final_tool_result.error,
                        stopped=True,
                        stop_reason=action_run.stop_reason or f"tool_failed:{call.tool_name}",
                        missing_tools=missing_tools,
                    ),
                    executed_calls,
                    0,
                )

        return (
            FullWorkflowPhaseResult(
                phase_name=step_def.phase_name,
                kind=step_def.kind,
                status="completed",
                summary=step_def.description,
                tool_calls=[tool.model_dump(mode="json") for tool in planner_result.tool_calls],
                tool_results=[result.model_dump(mode="json") for result in tool_results],
                action_runs=action_runs,
                reflection_traces=reflection_traces,
                retry_count=retry_count,
                missing_tools=missing_tools,
                state_updates=self._base_state_updates(step_def),
            ),
            executed_calls,
            0,
        )

    def _run_macro_step(
        self,
        *,
        live_plan: WorkflowExecutionPlan,
        workflow_name: str,
        step_def: FullWorkflowStepDefinition,
        tool_call_count: int,
    ) -> tuple[FullWorkflowPhaseResult, int, int]:
        macro_name = step_def.tool_name or step_def.phase_name
        macro = self.action_macro_executor.registry.get(macro_name)
        if macro is None:
            if step_def.missing_tools:
                return (
                    FullWorkflowPhaseResult(
                        phase_name=step_def.phase_name,
                        kind=step_def.kind,
                        status="blocked_missing_tools",
                        summary=step_def.description,
                        simulated_actions=list(step_def.simulated_actions),
                        missing_tools=list(step_def.missing_tools),
                        stopped=True,
                        stop_reason="blocked_missing_tools",
                    ),
                    0,
                    0,
                )
            return (
                FullWorkflowPhaseResult(
                    phase_name=step_def.phase_name,
                    kind=step_def.kind,
                    status="failed",
                    summary=step_def.description,
                    error=f"action_macro_not_found:{macro_name}",
                    stopped=True,
                    stop_reason=f"action_macro_not_found:{macro_name}",
                    missing_tools=list(step_def.missing_tools),
                ),
                0,
                0,
            )

        macro_steps = macro.build_steps(dict(step_def.tool_arguments))
        if tool_call_count + len(macro_steps) > self.max_tool_calls:
            return (
                FullWorkflowPhaseResult(
                    phase_name=step_def.phase_name,
                    kind=step_def.kind,
                    status="blocked",
                    summary=step_def.description,
                    simulated_actions=list(step_def.simulated_actions),
                    missing_tools=list(step_def.missing_tools),
                    stopped=True,
                    stop_reason="workflow_limits_exceeded",
                ),
                0,
                0,
            )

        macro_result = self.action_macro_executor.run(
            ActionMacroPlan(
                selected=True,
                workflow_name=macro_name,
                inputs=dict(step_def.tool_arguments),
                reason=step_def.description,
            )
        )
        if not macro_result.success and macro_result.stopped_reason == "blocked_missing_tools":
            phase_status = "blocked_missing_tools"
        elif macro_result.success:
            phase_status = "completed"
        else:
            phase_status = "failed"

        return (
            FullWorkflowPhaseResult(
                phase_name=step_def.phase_name,
                kind=step_def.kind,
                status=phase_status,  # type: ignore[assignment]
                summary=step_def.description,
                tool_calls=[step.tool_call.model_dump(mode="json") for step in macro_result.steps],
                tool_results=[step.tool_result.model_dump(mode="json") for step in macro_result.steps],
                action_runs=[step.action_run or {} for step in macro_result.steps],
                reflection_traces=[
                    {
                        "action_run": step.action_run,
                        "reflection_trace": step.reflection_trace,
                        "retry_count": step.retry_count,
                        "stop_reason": step.stop_reason,
                    }
                    for step in macro_result.steps
                ],
                retry_count=sum(step.retry_count for step in macro_result.steps),
                error=macro_result.error,
                stopped=not macro_result.success,
                stop_reason=macro_result.stopped_reason,
                missing_tools=list(step_def.missing_tools),
                state_updates=self._base_state_updates(step_def),
            ),
            len(macro_steps),
            0,
        )

    def _run_observe_step(
        self,
        *,
        live_plan: WorkflowExecutionPlan,
        workflow_name: str,
        step_def: FullWorkflowStepDefinition,
        reasoning_count: int,
    ) -> tuple[FullWorkflowPhaseResult, int, int]:
        if not step_def.can_run_now and step_def.missing_tools:
            return (
                FullWorkflowPhaseResult(
                    phase_name=step_def.phase_name,
                    kind=step_def.kind,
                    status="blocked_missing_tools",
                    summary=step_def.description,
                    simulated_actions=list(step_def.simulated_actions),
                    missing_tools=list(step_def.missing_tools),
                    stopped=True,
                    stop_reason="blocked_missing_tools",
                ),
                0,
                0,
            )
        return self._run_reason_step(
            live_plan=live_plan,
            workflow_name=workflow_name,
            step_def=step_def,
            reasoning_count=reasoning_count,
        )

    def _run_verify_step(
        self,
        *,
        live_plan: WorkflowExecutionPlan,
        workflow_name: str,
        step_def: FullWorkflowStepDefinition,
        reasoning_count: int,
    ) -> tuple[FullWorkflowPhaseResult, int, int]:
        if not step_def.can_run_now and step_def.missing_tools:
            return (
                FullWorkflowPhaseResult(
                    phase_name=step_def.phase_name,
                    kind=step_def.kind,
                    status="blocked_missing_tools",
                    summary=step_def.description,
                    simulated_actions=list(step_def.simulated_actions),
                    missing_tools=list(step_def.missing_tools),
                    stopped=True,
                    stop_reason="blocked_missing_tools",
                ),
                0,
                0,
            )
        return self._run_reason_step(
            live_plan=live_plan,
            workflow_name=workflow_name,
            step_def=step_def,
            reasoning_count=reasoning_count,
        )

    def _run_wait_step(
        self,
        step_def: FullWorkflowStepDefinition,
    ) -> tuple[FullWorkflowPhaseResult, int, int]:
        return (
            FullWorkflowPhaseResult(
                phase_name=step_def.phase_name,
                kind=step_def.kind,
                status="completed",
                summary=step_def.description,
                simulated_actions=list(step_def.simulated_actions),
                missing_tools=list(step_def.missing_tools),
                state_updates=self._base_state_updates(step_def),
            ),
            0,
            0,
        )

    def _run_ask_user_step(
        self,
        *,
        live_plan: WorkflowExecutionPlan,
        step_def: FullWorkflowStepDefinition,
        step_plan: WorkflowPlanStep,
    ) -> tuple[FullWorkflowPhaseResult, int, int]:
        question = step_def.description or step_plan.title
        kind = "preference" if "prefer" in question.lower() else "missing_info"
        checkpoint = self.plan_manager.create_human_checkpoint(
            live_plan,
            step_plan.id,
            kind=kind,
            question=question,
            options=[],
            required=True,
        )
        return (
            FullWorkflowPhaseResult(
                phase_name=step_def.phase_name,
                kind=step_def.kind,
                status="waiting_user_input",
                summary=step_def.description,
                missing_tools=list(step_def.missing_tools),
                stopped=True,
                stop_reason=checkpoint.kind,
                state_updates=self._base_state_updates(step_def),
            ),
            0,
            0,
        )

    def _run_approval_step(
        self,
        *,
        live_plan: WorkflowExecutionPlan,
        step_def: FullWorkflowStepDefinition,
        step_plan: WorkflowPlanStep,
    ) -> tuple[FullWorkflowPhaseResult, int, int]:
        question = step_def.description or step_plan.title
        checkpoint = self.plan_manager.create_human_checkpoint(
            live_plan,
            step_plan.id,
            kind="approval",
            question=question,
            options=["approve", "reject"],
            required=True,
        )
        return (
            FullWorkflowPhaseResult(
                phase_name=step_def.phase_name,
                kind=step_def.kind,
                status="waiting_approval",
                summary=step_def.description,
                missing_tools=list(step_def.missing_tools),
                stopped=True,
                stop_reason=checkpoint.kind,
                state_updates=self._base_state_updates(step_def),
            ),
            0,
            0,
        )

    def _paused_phase_result(
        self,
        *,
        step_def: FullWorkflowStepDefinition,
        step_plan: WorkflowPlanStep,
        live_plan: WorkflowExecutionPlan,
    ) -> FullWorkflowPhaseResult:
        checkpoint = live_plan.state.get("active_checkpoint") or {}
        kind = checkpoint.get("kind")
        status = (
            "waiting_approval"
            if kind in {"approval", "safety_confirmation", "visual_validation"}
            or live_plan.status == "waiting_approval"
            else "waiting_user_input"
        )
        question = checkpoint.get("question")
        approval_request = checkpoint.get("approval_request")
        return FullWorkflowPhaseResult(
            phase_name=step_def.phase_name,
            kind=step_def.kind,
            status=status,  # type: ignore[assignment]
            summary=step_def.description,
            question=question if status == "waiting_user_input" else None,
            approval_request=approval_request if status == "waiting_approval" else None,
            checkpoint_id=checkpoint.get("checkpoint_id") or live_plan.active_checkpoint_id,
            requires_user_input=status == "waiting_user_input",
            requires_approval=status == "waiting_approval",
            missing_tools=list(step_def.missing_tools),
            stopped=True,
            stop_reason=kind or live_plan.status,
            state_updates=self._base_state_updates(step_def),
        )

    def _paused_result(
        self,
        *,
        live_plan: WorkflowExecutionPlan,
        workflow_name: str,
        plan: FullWorkflowPlan,
        phases: list[FullWorkflowPhaseResult],
        missing_tools: set[str],
        phase_result: FullWorkflowPhaseResult,
    ) -> FullWorkflowResult:
        self.plan_manager.save_plan(live_plan)
        checkpoint = live_plan.state.get("active_checkpoint") or {}
        checkpoint_id = phase_result.checkpoint_id or checkpoint.get("checkpoint_id") or live_plan.active_checkpoint_id
        current_step_id = checkpoint.get("step_id")
        if current_step_id is None and live_plan.current_step_index < len(live_plan.steps):
            current_step_id = live_plan.steps[live_plan.current_step_index].id
        status = phase_result.status if phase_result.status in {"waiting_user_input", "waiting_approval"} else "blocked"
        return FullWorkflowResult(
            workflow_name=workflow_name,
            inputs=dict(plan.inputs),
            state=FullWorkflowState(data=dict(live_plan.state)),
            workflow_id=live_plan.workflow_id,
            plan_path=str(
                self.plan_manager._plan_markdown_path(
                    live_plan.workflow_id, session_id=live_plan.session_id
                )
            ),
            status=status,  # type: ignore[assignment]
            phases=phases,
            success=False,
            simulation_mode=plan.simulation_mode,
            needs_user_input=phase_result.requires_user_input or phase_result.status == "waiting_user_input",
            needs_approval=phase_result.requires_approval or phase_result.status == "waiting_approval",
            question=phase_result.question or checkpoint.get("question"),
            approval_request=phase_result.approval_request or checkpoint.get("approval_request"),
            checkpoint_id=checkpoint_id,
            current_step_id=current_step_id,
            stopped_reason=phase_result.stop_reason,
            missing_tools=sorted(missing_tools),
            error=None,
        )

    def _final_result(
        self,
        *,
        live_plan: WorkflowExecutionPlan,
        workflow_name: str,
        plan: FullWorkflowPlan,
        phases: list[FullWorkflowPhaseResult],
        missing_tools: set[str],
        success: bool,
        status: str,
        stopped_reason: str | None,
    ) -> FullWorkflowResult:
        live_plan.status = status
        self.plan_manager.save_plan(live_plan)
        return FullWorkflowResult(
            workflow_name=workflow_name,
            inputs=dict(plan.inputs),
            state=FullWorkflowState(data=dict(live_plan.state)),
            workflow_id=live_plan.workflow_id,
            plan_path=str(
                self.plan_manager._plan_markdown_path(
                    live_plan.workflow_id, session_id=live_plan.session_id
                )
            ),
            status=status,  # type: ignore[assignment]
            phases=phases,
            success=success,
            simulation_mode=plan.simulation_mode,
            needs_user_input=False,
            needs_approval=False,
            question=None,
            approval_request=None,
            checkpoint_id=None,
            current_step_id=(
                live_plan.steps[live_plan.current_step_index].id
                if live_plan.current_step_index < len(live_plan.steps)
                else None
            ),
            stopped_reason=stopped_reason,
            missing_tools=sorted(missing_tools),
            error=None if success else stopped_reason,
        )

    def _limit_result(
        self,
        *,
        live_plan: WorkflowExecutionPlan,
        workflow_name: str,
        plan: FullWorkflowPlan,
        phases: list[FullWorkflowPhaseResult],
        missing_tools: set[str],
        tool_call_count: int,
        reasoning_count: int,
    ) -> FullWorkflowResult:
        phases.append(
            FullWorkflowPhaseResult(
                phase_name="workflow_limits",
                kind="wait",
                status="blocked",
                summary="Se alcanzó un límite estricto del workflow.",
                stopped=True,
                stop_reason="workflow_limits_exceeded",
            )
        )
        return self._final_result(
            live_plan=live_plan,
            workflow_name=workflow_name,
            plan=plan,
            phases=phases,
            missing_tools=missing_tools,
            success=False,
            status="blocked",
            stopped_reason="workflow_limits_exceeded",
        )

    def _limit_phase(
        self,
        step_def: FullWorkflowStepDefinition,
        reason: str,
    ) -> FullWorkflowPhaseResult:
        return FullWorkflowPhaseResult(
            phase_name=step_def.phase_name,
            kind=step_def.kind,
            status="blocked",
            summary=step_def.description,
            stopped=True,
            stop_reason="workflow_limits_exceeded",
            error=reason,
        )

    def _base_state_updates(self, step_def: FullWorkflowStepDefinition) -> dict[str, Any]:
        return {
            "last_step_kind": step_def.kind,
            "last_step_phase": step_def.phase_name,
        }
