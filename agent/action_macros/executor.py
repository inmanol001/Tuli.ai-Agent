from __future__ import annotations

from agent.executor.executor import Executor
from agent.executor.results import ToolResult
from agent.action_macros.registry import ActionMacroRegistry
from agent.action_macros.schemas import (
    ActionMacroPlan,
    ActionMacroResult,
    ActionMacroStepResult,
)


class ActionMacroExecutor:
    def __init__(
        self,
        executor: Executor,
        reflection_checker=None,
        max_retries: int = 2,
        registry: ActionMacroRegistry | None = None,
    ) -> None:
        self.executor = executor
        self.reflection_checker = reflection_checker
        self.max_retries = max_retries
        self.registry = registry or ActionMacroRegistry()

    def run(self, macro_plan: ActionMacroPlan) -> ActionMacroResult:
        macro_name = macro_plan.workflow_name or ""
        macro = self.registry.get(macro_name)
        if macro is None:
            return ActionMacroResult(
                workflow_name=macro_name or "unknown",
                inputs=dict(macro_plan.inputs),
                success=False,
                error=f"action_macro_not_found:{macro_name}",
            )

        try:
            steps = macro.build_steps(macro_plan.inputs)
        except Exception as exc:
            return ActionMacroResult(
                workflow_name=macro_name,
                inputs=dict(macro_plan.inputs),
                success=False,
                error=str(exc),
            )

        results: list[ActionMacroStepResult] = []
        for step_index, tool_call in enumerate(steps):
            tool_result = self.executor.execute(tool_call)
            stopped, stop_reason = self._step_stop_reason(
                macro_name, step_index, tool_result
            )
            step_result = ActionMacroStepResult(
                step_index=step_index,
                tool_call=tool_call,
                tool_result=tool_result,
                success=tool_result.success and not stopped,
                stopped=stopped,
                stop_reason=stop_reason,
            )
            results.append(step_result)
            if stopped or not tool_result.success:
                return ActionMacroResult(
                    workflow_name=macro_name,
                    inputs=dict(macro_plan.inputs),
                    steps=results,
                    success=False,
                    stopped_reason=stop_reason or f"step_failed:{tool_call.tool_name}",
                )

        return ActionMacroResult(
            workflow_name=macro_name,
            inputs=dict(macro_plan.inputs),
            steps=results,
            success=True,
        )

    def _step_stop_reason(
        self, workflow_name: str, step_index: int, tool_result: ToolResult
    ) -> tuple[bool, str | None]:
        if workflow_name == "tile_active_window" and step_index == 0:
            data = tool_result.data or {}
            has_frontmost = bool(data.get("app_name") or data.get("window_title"))
            if not tool_result.success:
                return True, "step_failed:macos_observe_frontmost"
            if not has_frontmost:
                return True, "no_frontmost_window"
        if not tool_result.success:
            return True, f"step_failed:{tool_result.tool_name}"
        return False, None


WorkflowExecutor = ActionMacroExecutor
