from __future__ import annotations

from typing import Any

from agent.action_macros.executor import ActionMacroExecutor
from agent.capabilities.tools.registry import ToolRegistry
from agent.execution.action_runner import ActionRunner
from agent.executor.executor import Executor
from agent.gateway.message_types import ContextPackage
from agent.models.tool_planner import ToolPlanner
from agent.reflection.checker import ReflectionChecker
from agent.router.router_schema import RouterDecision
from agent.workflows.loop_controller import WorkflowLoopController
from agent.workflows.plan_manager import WorkflowPlanManager
from agent.workflows.plan_schemas import WorkflowPlanStep
from agent.workflows.reasoner import WorkflowReasoner
from agent.workflows.registry import FullWorkflowRegistry
from agent.workflows.requirement_checker import RequirementChecker, RequirementContext
from agent.workflows.schemas import (
    FullWorkflowPhaseResult,
    FullWorkflowPhaseSpec,
    FullWorkflowPlan,
    FullWorkflowResult,
    FullWorkflowState,
    FullWorkflowStepKind,
)


class FullWorkflowRunner:
    def __init__(
        self,
        executor: Executor,
        action_runner: ActionRunner | None = None,
        registry: FullWorkflowRegistry | None = None,
        reasoner: WorkflowReasoner | None = None,
        action_macro_executor: ActionMacroExecutor | None = None,
        tool_planner: ToolPlanner | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.executor = executor
        self.reflection_checker = ReflectionChecker()
        self.requirement_checker = RequirementChecker()
        self.action_runner = action_runner or ActionRunner(
            executor=self.executor,
            reflection_checker=self.reflection_checker,
        )
        self.registry = registry or FullWorkflowRegistry()
        self.reasoner = reasoner or WorkflowReasoner()
        self.action_macro_executor = action_macro_executor
        self.tool_planner = tool_planner or ToolPlanner()
        self.tool_registry = tool_registry or ToolRegistry()
        self.plan_manager = WorkflowPlanManager()
        self.loop_controller = WorkflowLoopController(
            executor=self.executor,
            action_runner=self.action_runner,
            action_macro_executor=self.action_macro_executor,
            reasoner=self.reasoner,
            tool_planner=self.tool_planner,
            tool_registry=self.tool_registry,
            plan_manager=self.plan_manager,
            reflection_checker=self.reflection_checker,
        )

    def run(
        self,
        workflow_plan: FullWorkflowPlan,
        context: ContextPackage | None = None,
        session: Any | None = None,
    ) -> FullWorkflowResult:
        workflow_name = workflow_plan.workflow_name or ""
        workflow = self.registry.get(workflow_name)
        if workflow is None:
            return FullWorkflowResult(
                workflow_name=workflow_name or "unknown",
                inputs=dict(workflow_plan.inputs),
                status="failed",
                success=False,
                simulation_mode=workflow_plan.simulation_mode,
                error=f"full_workflow_not_found:{workflow_name}",
            )

        try:
            step_defs = list(workflow.build_phases(dict(workflow_plan.inputs)))
        except Exception as exc:
            return FullWorkflowResult(
                workflow_name=workflow_name,
                inputs=dict(workflow_plan.inputs),
                status="failed",
                success=False,
                simulation_mode=workflow_plan.simulation_mode,
                error=str(exc),
            )

        live_plan = self._create_runtime_plan(workflow_name, workflow_plan, step_defs)

        if context is not None and session is not None and live_plan.steps:
            requirement_result = self.requirement_checker.check(
                RequirementContext(
                    workflow_name=workflow_name,
                    user_goal=context.user_message,
                    step_kind=live_plan.steps[0].kind,
                    step_title=live_plan.steps[0].title,
                    state=dict(live_plan.state),
                    requires_visual_validation=live_plan.steps[0].kind == "verify",
                    requires_approval=live_plan.steps[0].kind == "approval",
                )
            )
            self.plan_manager.apply_requirement_check(
                live_plan,
                live_plan.steps[0].id,
                requirement_result,
            )
            if not requirement_result.can_continue:
                self.plan_manager.save_plan(live_plan)
                status = "waiting_approval" if requirement_result.needs_approval else "waiting_user_input"
                return FullWorkflowResult(
                    workflow_name=workflow_name,
                    inputs=dict(workflow_plan.inputs),
                    state=FullWorkflowState(data=dict(live_plan.state)),
                    workflow_id=live_plan.workflow_id,
                    plan_path=str(
                        self.plan_manager._plan_markdown_path(
                            live_plan.workflow_id, session_id=live_plan.session_id
                        )
                    ),
                    status=status,
                    phases=[],
                    success=False,
                    simulation_mode=workflow_plan.simulation_mode,
                    needs_user_input=requirement_result.needs_user_input,
                    needs_approval=requirement_result.needs_approval,
                    question=(
                        requirement_result.questions[0]
                        if requirement_result.questions
                        else requirement_result.approval_request
                    ),
                    approval_request=requirement_result.approval_request,
                    checkpoint_id=live_plan.active_checkpoint_id,
                    current_step_id=(
                        live_plan.steps[live_plan.current_step_index].id
                        if live_plan.current_step_index < len(live_plan.steps)
                        else None
                    ),
                    stopped_reason=requirement_result.reason,
                    missing_tools=list(workflow_plan.missing_tools),
                    error=None,
                )

            live_plan = self.plan_manager.save_plan(live_plan)
            return self.loop_controller.run(
                workflow_plan,
                workflow,
                context,
                session,
                existing_plan=live_plan,
            )

        state = FullWorkflowState(
            data={
                "topic": workflow_plan.inputs.get("topic"),
                "content_type": workflow_plan.inputs.get("format", "post"),
                "platform": workflow_plan.inputs.get("target_app", "canva"),
                **dict(workflow_plan.inputs),
            }
        )
        results: list[FullWorkflowPhaseResult] = []
        missing_tools: set[str] = set(workflow_plan.missing_tools)
        blocked = False
        simulated = False
        failed = False

        for step_def in step_defs:
            step_plan = live_plan.steps[len(results)] if len(live_plan.steps) > len(results) else None
            if step_plan is not None:
                live_plan = self.plan_manager.mark_step_running(live_plan, step_plan.id)
            phase_result = self._run_step(
                step_def,
                workflow_name,
                state,
                workflow_plan.inputs,
            )
            results.append(phase_result)
            missing_tools.update(phase_result.missing_tools)
            if phase_result.status == "blocked_missing_tools":
                blocked = True
            if phase_result.status == "simulated":
                simulated = True
            if phase_result.status == "failed":
                failed = True
            for key, value in phase_result.state_updates.items():
                state.set_value(key, value)
                live_plan.state[key] = value
            if step_plan is not None:
                self._apply_phase_result_to_plan(live_plan, step_plan.id, phase_result)
                live_plan = self.plan_manager.save_plan(live_plan)

        status = "completed"
        success = True
        stopped_reason = None
        if failed:
            status = "failed"
            success = False
            stopped_reason = next(
                (phase.stop_reason for phase in results if phase.status == "failed"),
                "phase_failed",
            )
        elif blocked or simulated:
            status = "simulated"
            success = False
            stopped_reason = "blocked_missing_tools" if blocked else "simulation_only"

        return FullWorkflowResult(
            workflow_name=workflow_name,
            inputs=dict(workflow_plan.inputs),
            state=state,
            status=status,
            phases=results,
            success=success,
            simulation_mode=workflow_plan.simulation_mode,
            stopped_reason=stopped_reason,
            missing_tools=sorted(missing_tools),
        )

    def _create_runtime_plan(
        self,
        workflow_name: str,
        workflow_plan: FullWorkflowPlan,
        step_defs: list[FullWorkflowPhaseSpec],
    ):
        runtime_plan = self.plan_manager.create_plan(
            workflow_name=workflow_name,
            user_goal=workflow_plan.inputs.get("original_user_message")
            or workflow_plan.inputs.get("topic")
            or workflow_name,
            steps=[self._to_runtime_step(step_def) for step_def in step_defs],
            state=dict(workflow_plan.inputs),
            session_id=workflow_plan.inputs.get("session_id"),
            status="planning",
        )
        runtime_plan.status = "running"
        return self.plan_manager.save_plan(runtime_plan)

    def _to_runtime_step(self, step_def: FullWorkflowPhaseSpec) -> WorkflowPlanStep:
        return WorkflowPlanStep(
            title=step_def.description,
            kind=step_def.kind,
            description=step_def.description,
            expected_result=step_def.expected_result,
            selected_tool=step_def.tool_name
            or (step_def.allowed_tools[0] if step_def.allowed_tools else None),
            selected_macro=step_def.tool_name
            if step_def.kind in {"action_macro", "macro"}
            else None,
        )

    def _apply_phase_result_to_plan(
        self,
        plan,
        step_id: str,
        phase_result: FullWorkflowPhaseResult,
    ) -> None:
        step = next((item for item in plan.steps if item.id == step_id), None)
        if step is None:
            return
        if phase_result.status == "completed":
            step.status = "completed"
            step.result_summary = phase_result.summary or phase_result.reasoning_output
            step.error = None
        elif phase_result.status == "failed":
            step.status = "failed"
            step.error = phase_result.error or phase_result.stop_reason
        elif phase_result.status == "blocked_missing_tools":
            step.status = "blocked"
            step.error = phase_result.stop_reason
        elif phase_result.status == "waiting_user_input":
            step.status = "waiting_user_input"
            step.question = phase_result.summary
            step.requires_user_input = True
        elif phase_result.status == "waiting_approval":
            step.status = "waiting_approval"
            step.approval_request = phase_result.summary
            step.requires_approval = True
        else:
            step.status = "skipped" if phase_result.status == "simulated" else step.status
        if phase_result.state_updates:
            plan.state.update(phase_result.state_updates)
        if phase_result.status in {"completed", "simulated"}:
            plan.current_step_index = min(plan.current_step_index + 1, len(plan.steps))
            if plan.current_step_index >= len(plan.steps) and plan.status == "running":
                plan.status = "completed"
        elif phase_result.status in {"failed", "blocked_missing_tools"}:
            plan.status = "failed" if phase_result.status == "failed" else "blocked"

    def _run_step(
        self,
        step_def: FullWorkflowPhaseSpec,
        workflow_name: str,
        state: FullWorkflowState,
        inputs: dict[str, Any],
    ) -> FullWorkflowPhaseResult:
        status: FullWorkflowStepKind = step_def.kind
        missing_tools = list(step_def.missing_tools)

        if status == "reason":
            return self._run_reason_step(step_def, workflow_name, state, inputs)

        if status == "tool":
            return self._run_tool_step(step_def, workflow_name, state, inputs)

        if status == "action_macro":
            return self._run_action_macro_step(step_def, missing_tools)

        if status == "observe":
            return self._run_observe_step(step_def, missing_tools)

        if status == "verify":
            return self._run_verify_step(step_def, missing_tools)

        if status == "wait":
            return self._run_wait_step(step_def, missing_tools)

        if status == "branch":
            return self._run_branch_step(step_def, workflow_name, state, inputs, missing_tools)

        if status == "blocked_missing_tools":
            return FullWorkflowPhaseResult(
                phase_name=step_def.phase_name,
                kind=step_def.kind,
                status="blocked_missing_tools",
                summary=step_def.description,
                simulated_actions=list(step_def.simulated_actions),
                missing_tools=missing_tools,
                stop_reason="blocked_missing_tools",
            )

        return FullWorkflowPhaseResult(
            phase_name=step_def.phase_name,
            kind=step_def.kind,
            status="simulated",
            summary=step_def.description,
            simulated_actions=list(step_def.simulated_actions),
            missing_tools=missing_tools,
        )

    def _run_reason_step(
        self,
        step_def: FullWorkflowPhaseSpec,
        workflow_name: str,
        state: FullWorkflowState,
        inputs: dict[str, Any],
    ) -> FullWorkflowPhaseResult:
        task = step_def.reason_task or step_def.description
        reason_result = self.reasoner.reason(
            workflow_name=workflow_name,
            phase_name=step_def.phase_name,
            task=task,
            state=state,
            inputs=inputs,
        )
        if reason_result.error and not reason_result.text:
            return FullWorkflowPhaseResult(
                phase_name=step_def.phase_name,
                kind=step_def.kind,
                status="failed",
                summary=step_def.description,
                reasoning_output=reason_result.text,
                error=reason_result.error,
                stopped=True,
                stop_reason="reasoner_failed",
                missing_tools=list(step_def.missing_tools),
            )

        state_updates = {}
        if step_def.output_key:
            state_updates[step_def.output_key] = reason_result.text

        return FullWorkflowPhaseResult(
            phase_name=step_def.phase_name,
            kind=step_def.kind,
            status="completed",
            summary=step_def.description,
            reasoning_output=reason_result.text,
            state_updates=state_updates,
            missing_tools=list(step_def.missing_tools),
        )

    def _run_tool_step(
        self,
        step_def: FullWorkflowPhaseSpec,
        workflow_name: str,
        state: FullWorkflowState,
        inputs: dict[str, Any],
    ) -> FullWorkflowPhaseResult:
        allowed_tools = list(step_def.allowed_tools)
        if not allowed_tools and step_def.tool_name:
            allowed_tools = [step_def.tool_name]

        if not step_def.can_run_now:
            return FullWorkflowPhaseResult(
                phase_name=step_def.phase_name,
                kind=step_def.kind,
                status="blocked_missing_tools",
                summary=step_def.description,
                simulated_actions=list(step_def.simulated_actions),
                missing_tools=list(step_def.missing_tools) or allowed_tools or ["tool"],
                stop_reason="blocked_missing_tools",
            )

        active_tools = self.tool_registry.find_active(allowed_tools)
        missing_tools = []
        for name in allowed_tools:
            tool = self.tool_registry.get(name)
            if tool is None or not tool.active:
                missing_tools.append(name)

        if not active_tools:
            return FullWorkflowPhaseResult(
                phase_name=step_def.phase_name,
                kind=step_def.kind,
                status="blocked_missing_tools",
                summary=step_def.description,
                simulated_actions=list(step_def.simulated_actions),
                missing_tools=missing_tools or list(step_def.missing_tools) or allowed_tools,
                stop_reason="blocked_missing_tools",
            )

        phase_context = ContextPackage(
            system_prompt=(
                "You are the tool-calling hands for one phase of a local workflow. "
                "Choose the best available tool call for this phase. "
                "Do not answer normally if a matching tool is available. "
                "Do not invent tool results."
            ),
            user_message=(
                f"Original user request: {inputs.get('original_user_message', '')}\n"
                f"Workflow: {workflow_name}\n"
                f"Phase: {step_def.phase_name}\n"
                f"Phase goal: {step_def.tool_goal or step_def.description}\n"
                f"Expected result: {step_def.expected_result or ''}\n"
                f"Workflow state: {state.model_dump(mode='json')}\n"
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
            return FullWorkflowPhaseResult(
                phase_name=step_def.phase_name,
                kind=step_def.kind,
                status="failed",
                summary=step_def.description,
                error=planner_result.error,
                stopped=True,
                stop_reason="tool_planner_failed",
                missing_tools=missing_tools,
            )

        if not planner_result.tool_calls:
            return FullWorkflowPhaseResult(
                phase_name=step_def.phase_name,
                kind=step_def.kind,
                status="failed",
                summary=step_def.description,
                error="tool_planner_returned_no_tool_calls",
                stopped=True,
                stop_reason="tool_planner_returned_no_tool_calls",
                missing_tools=missing_tools,
            )

        tool_results = []
        action_runs = []
        reflection_traces = []
        retry_count = 0
        for call in planner_result.tool_calls:
            action_run = self.action_runner.run_tool_call(call)
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

        if any(not action_run["success"] for action_run in action_runs):
            return FullWorkflowPhaseResult(
                phase_name=step_def.phase_name,
                kind=step_def.kind,
                status="failed",
                summary=step_def.description,
                tool_calls=[
                    call.model_dump(mode="json") for call in planner_result.tool_calls
                ],
                tool_results=[
                    result.model_dump(mode="json") for result in tool_results
                ],
                action_runs=action_runs,
                reflection_traces=reflection_traces,
                retry_count=retry_count,
                error=next(
                    (result.error for result in tool_results if not result.success),
                    None,
                ),
                stopped=True,
                stop_reason=next(
                    (action_run.get("stop_reason") for action_run in action_runs if not action_run["success"]),
                    "tool_failed",
                ),
                missing_tools=missing_tools,
            )

        return FullWorkflowPhaseResult(
            phase_name=step_def.phase_name,
            kind=step_def.kind,
            status="completed",
            summary=step_def.description,
            tool_calls=[
                call.model_dump(mode="json") for call in planner_result.tool_calls
            ],
            tool_results=[result.model_dump(mode="json") for result in tool_results],
            action_runs=action_runs,
            reflection_traces=reflection_traces,
            retry_count=retry_count,
            missing_tools=missing_tools,
        )

    def _run_action_macro_step(
        self, step_def: FullWorkflowPhaseSpec, missing_tools: list[str]
    ) -> FullWorkflowPhaseResult:
        if self.action_macro_executor is None:
            return FullWorkflowPhaseResult(
                phase_name=step_def.phase_name,
                kind=step_def.kind,
                status="blocked_missing_tools",
                summary=step_def.description,
                simulated_actions=list(step_def.simulated_actions),
                missing_tools=missing_tools,
                stop_reason="blocked_missing_tools",
            )
        return FullWorkflowPhaseResult(
            phase_name=step_def.phase_name,
            kind=step_def.kind,
            status="simulated",
            summary=step_def.description,
            simulated_actions=list(step_def.simulated_actions),
            missing_tools=missing_tools,
        )

    def _run_observe_step(
        self, step_def: FullWorkflowPhaseSpec, missing_tools: list[str]
    ) -> FullWorkflowPhaseResult:
        return FullWorkflowPhaseResult(
            phase_name=step_def.phase_name,
            kind=step_def.kind,
            status="simulated" if not step_def.can_run_now else "completed",
            summary=step_def.description,
            simulated_actions=list(step_def.simulated_actions),
            missing_tools=missing_tools,
        )

    def _run_verify_step(
        self, step_def: FullWorkflowPhaseSpec, missing_tools: list[str]
    ) -> FullWorkflowPhaseResult:
        return FullWorkflowPhaseResult(
            phase_name=step_def.phase_name,
            kind=step_def.kind,
            status="blocked_missing_tools",
            summary=step_def.description,
            simulated_actions=list(step_def.simulated_actions),
            missing_tools=missing_tools,
            stop_reason="blocked_missing_tools",
        )

    def _run_wait_step(
        self, step_def: FullWorkflowPhaseSpec, missing_tools: list[str]
    ) -> FullWorkflowPhaseResult:
        return FullWorkflowPhaseResult(
            phase_name=step_def.phase_name,
            kind=step_def.kind,
            status="simulated",
            summary=step_def.description,
            simulated_actions=list(step_def.simulated_actions),
            missing_tools=missing_tools,
        )

    def _run_branch_step(
        self,
        step_def: FullWorkflowPhaseSpec,
        workflow_name: str,
        state: FullWorkflowState,
        inputs: dict[str, Any],
        missing_tools: list[str],
    ) -> FullWorkflowPhaseResult:
        branch_task = step_def.reason_task or step_def.description
        reason_result = self.reasoner.reason(
            workflow_name=workflow_name,
            phase_name=step_def.phase_name,
            task=branch_task,
            state=state,
            inputs=inputs,
        )
        state_updates = {}
        if step_def.output_key:
            state_updates[step_def.output_key] = reason_result.text
        return FullWorkflowPhaseResult(
            phase_name=step_def.phase_name,
            kind=step_def.kind,
            status="completed",
            summary=step_def.description,
            reasoning_output=reason_result.text,
            state_updates=state_updates,
            simulated_actions=list(step_def.simulated_actions),
            missing_tools=missing_tools,
        )
