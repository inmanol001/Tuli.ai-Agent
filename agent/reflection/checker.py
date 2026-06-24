import re

from agent.capabilities.tools.schemas import ToolCall
from agent.executor.results import ToolResult
from agent.reflection.schemas import ReflectionDecision, RetryState


DETERMINISTIC_ERROR_RE = re.compile(
    r"(validation|missing argument|requires a query|blocked|risk not allowed|"
    r"tool inactive|tool not found|not registered|not declared|missing valid)",
    re.I,
)
TRANSIENT_ERROR_RE = re.compile(
    r"(timeout|connection|temporary|rate limit|network|unavailable)",
    re.I,
)


class ReflectionChecker:
    def evaluate(
        self,
        tool_call: ToolCall,
        tool_result: ToolResult,
        retry_state: RetryState,
    ) -> ReflectionDecision:
        if tool_result.success:
            return ReflectionDecision(reason="tool_success")

        error = tool_result.error or ""
        if tool_result.metadata.get("blocked") is True:
            return ReflectionDecision(
                should_stop=True,
                reason="blocked_tool",
                user_message=self._stop_message(tool_call, error),
            )

        if DETERMINISTIC_ERROR_RE.search(error):
            return ReflectionDecision(
                should_stop=True,
                reason="deterministic_error",
                user_message=self._stop_message(tool_call, error),
            )

        if TRANSIENT_ERROR_RE.search(error):
            if retry_state.can_retry:
                return ReflectionDecision(
                    should_retry=True,
                    reason="transient_error",
                    user_message="La herramienta fallo temporalmente; reintentando.",
                )
            return ReflectionDecision(
                should_stop=True,
                reason="max_retries_exhausted",
                user_message=(
                    "La herramienta fallo varias veces por un problema temporal. "
                    "Me detuve despues de 2 reintentos."
                ),
            )

        return ReflectionDecision(
            should_stop=True,
            reason="unclassified_error",
            user_message=self._stop_message(tool_call, error),
        )

    def _stop_message(self, tool_call: ToolCall, error: str) -> str:
        detail = error or "error desconocido"
        return f"No pude completar {tool_call.tool_name}: {detail}"
