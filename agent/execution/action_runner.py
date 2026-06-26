from __future__ import annotations

from agent.capabilities.tools.schemas import ToolCall
from agent.executor.executor import Executor
from agent.execution.schemas import ActionAttemptResult, ActionRunResult
from agent.reflection.checker import ReflectionChecker
from agent.reflection.retry_policy import make_retry_state


class ActionRunner:
    def __init__(
        self,
        executor: Executor,
        reflection_checker: ReflectionChecker,
        max_retries: int = 2,
    ) -> None:
        self.executor = executor
        self.reflection_checker = reflection_checker
        self.max_retries = max_retries

    def run_tool_call(self, tool_call: ToolCall) -> ActionRunResult:
        previous_errors: list[str] = []
        attempts: list[ActionAttemptResult] = []
        reflection_trace: list[dict[str, object]] = []
        final_tool_result = None
        stop_reason: str | None = None

        for attempt_number in range(self.max_retries + 1):
            retry_state = make_retry_state(
                attempt_number,
                max_retries=self.max_retries,
                previous_errors=previous_errors,
            )
            tool_result = self.executor.execute(tool_call)
            final_tool_result = tool_result
            reflection_decision = self.reflection_checker.evaluate(
                tool_call,
                tool_result,
                retry_state,
            )

            attempt = ActionAttemptResult(
                attempt_number=attempt_number,
                execution_number=attempt_number + 1,
                tool_call=tool_call.model_dump(mode="json"),
                tool_result=tool_result.model_dump(mode="json"),
                reflection_decision=reflection_decision.model_dump(mode="json"),
            )
            attempts.append(attempt)

            trace_entry = attempt.model_dump(mode="json")
            trace_entry["decision"] = trace_entry["reflection_decision"]
            reflection_trace.append(trace_entry)

            if tool_result.error:
                previous_errors.append(tool_result.error)

            if tool_result.success:
                return ActionRunResult(
                    tool_call=tool_call,
                    final_tool_result=tool_result,
                    attempts=attempts,
                    success=True,
                    stopped=False,
                    stop_reason=None,
                    retry_count=max(0, len(attempts) - 1),
                    reflection_trace=reflection_trace,
                )

            if reflection_decision.should_retry:
                continue

            if reflection_decision.should_stop:
                stop_reason = reflection_decision.reason
                return ActionRunResult(
                    tool_call=tool_call,
                    final_tool_result=tool_result,
                    attempts=attempts,
                    success=False,
                    stopped=True,
                    stop_reason=stop_reason,
                    retry_count=max(0, len(attempts) - 1),
                    reflection_trace=reflection_trace,
                )

            return ActionRunResult(
                tool_call=tool_call,
                final_tool_result=tool_result,
                attempts=attempts,
                success=False,
                stopped=False,
                stop_reason=None,
                retry_count=max(0, len(attempts) - 1),
                reflection_trace=reflection_trace,
            )

        if final_tool_result is None:
            final_tool_result = self.executor.execute(tool_call)

        return ActionRunResult(
            tool_call=tool_call,
            final_tool_result=final_tool_result,
            attempts=attempts,
            success=final_tool_result.success,
            stopped=True,
            stop_reason=stop_reason or "max_retries_exhausted",
            retry_count=max(0, len(attempts) - 1),
            reflection_trace=reflection_trace,
        )
