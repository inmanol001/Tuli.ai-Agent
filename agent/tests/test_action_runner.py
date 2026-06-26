from agent.capabilities.tools.schemas import ToolCall
from agent.executor.results import ToolResult
from agent.execution.action_runner import ActionRunner
from agent.reflection.schemas import ReflectionDecision


class FakeExecutor:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def execute(self, tool_call):
        self.calls.append(tool_call)
        if self.results:
            return self.results.pop(0)
        return ToolResult(tool_name=tool_call.tool_name, success=False, error="missing result")


class SequencedReflectionChecker:
    def __init__(self, decisions):
        self.decisions = list(decisions)
        self.calls = []

    def evaluate(self, tool_call, tool_result, retry_state):
        self.calls.append((tool_call, tool_result, retry_state))
        if self.decisions:
            return self.decisions.pop(0)
        return ReflectionDecision(should_stop=True, reason="fallback_stop", user_message="stop")


def test_action_runner_retries_then_succeeds():
    executor = FakeExecutor(
        [
            ToolResult(tool_name="browser_search", success=False, error="temporary network timeout"),
            ToolResult(tool_name="browser_search", success=True, data={"url": "https://example.test"}),
        ]
    )
    checker = SequencedReflectionChecker(
        [
            ReflectionDecision(
                should_retry=True,
                reason="transient_error",
                user_message="reintentando",
            ),
            ReflectionDecision(reason="tool_success"),
        ]
    )

    result = ActionRunner(executor=executor, reflection_checker=checker, max_retries=2).run_tool_call(
        ToolCall(tool_name="browser_search", arguments={"query": "test"})
    )

    assert result.success is True
    assert result.stopped is False
    assert result.retry_count == 1
    assert len(result.attempts) == 2
    assert [call.tool_name for call in executor.calls] == ["browser_search", "browser_search"]
    assert result.reflection_trace[0]["decision"]["reason"] == "transient_error"


def test_action_runner_stops_when_reflection_says_stop():
    executor = FakeExecutor(
        [
            ToolResult(tool_name="browser_search", success=False, error="validation failed"),
        ]
    )
    checker = SequencedReflectionChecker(
        [
            ReflectionDecision(
                should_stop=True,
                reason="deterministic_error",
                user_message="No pude completar browser_search: validation failed",
            )
        ]
    )

    result = ActionRunner(executor=executor, reflection_checker=checker).run_tool_call(
        ToolCall(tool_name="browser_search", arguments={"query": "test"})
    )

    assert result.success is False
    assert result.stopped is True
    assert result.stop_reason == "deterministic_error"
    assert len(result.attempts) == 1
    assert len(executor.calls) == 1
    assert result.final_tool_result.error == "validation failed"


def test_action_runner_stops_after_max_retries_for_transient_error():
    executor = FakeExecutor(
        [
            ToolResult(tool_name="browser_search", success=False, error="temporary network timeout"),
            ToolResult(tool_name="browser_search", success=False, error="temporary network timeout"),
            ToolResult(tool_name="browser_search", success=False, error="temporary network timeout"),
        ]
    )
    checker = SequencedReflectionChecker(
        [
            ReflectionDecision(
                should_retry=True,
                reason="transient_error",
                user_message="reintentando",
            ),
            ReflectionDecision(
                should_retry=True,
                reason="transient_error",
                user_message="reintentando",
            ),
            ReflectionDecision(
                should_retry=True,
                reason="transient_error",
                user_message="reintentando",
            ),
        ]
    )

    result = ActionRunner(executor=executor, reflection_checker=checker, max_retries=2).run_tool_call(
        ToolCall(tool_name="browser_search", arguments={"query": "test"})
    )

    assert result.success is False
    assert result.stopped is True
    assert result.stop_reason == "max_retries_exhausted"
    assert result.retry_count == 2
    assert len(result.attempts) == 3
    assert [call.tool_name for call in executor.calls] == [
        "browser_search",
        "browser_search",
        "browser_search",
    ]
    assert len(result.reflection_trace) == 3
