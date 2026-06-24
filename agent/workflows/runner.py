from __future__ import annotations

from typing import Any

from agent.action_macros.executor import ActionMacroExecutor
from agent.capabilities.tools.registry import ToolRegistry
from agent.executor.executor import Executor
from agent.gateway.message_types import ContextPackage
from agent.models.tool_planner import ToolPlanner
from agent.router.router_schema import RouterDecision
from agent.workflows.reasoner import WorkflowReasoner
from agent.workflows.registry import FullWorkflowRegistry
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
        registry: FullWorkflowRegistry | None = None,
        reasoner: WorkflowReasoner | None = None,
        action_macro_executor: ActionMacroExecutor | None = None,
        tool_planner: ToolPlanner | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.executor = executor
        self.registry = registry or FullWorkflowRegistry()
        self.reasoner = reasoner or WorkflowReasoner()
        self.action_macro_executor = action_macro_executor
        self.tool_planner = tool_planner or ToolPlanner()
        self.tool_registry = tool_registry or ToolRegistry()

    def run(self, workflow_plan: FullWorkflowPlan) -> FullWorkflowResult:
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
            step_defs = workflow.build_phases(workflow_plan.inputs)
        except Exception as exc:
            return FullWorkflowResult(
                workflow_name=workflow_name,
                inputs=dict(workflow_plan.inputs),
                status="failed",
                success=False,
                simulation_mode=workflow_plan.simulation_mode,
                error=str(exc),
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
        for call in planner_result.tool_calls:
            tool_results.append(self.executor.execute(call))

        if any(not result.success for result in tool_results):
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
                error=next(
                    (result.error for result in tool_results if not result.success),
                    None,
                ),
                stopped=True,
                stop_reason="tool_failed",
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
