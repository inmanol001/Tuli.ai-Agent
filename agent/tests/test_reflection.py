from agent.capabilities.tools.schemas import ToolCall
from agent.executor.results import ToolResult
from agent.reflection.checker import ReflectionChecker
from agent.reflection.schemas import RetryState


def call() -> ToolCall:
    return ToolCall(
        tool_name="browser_search",
        arguments={"query": "omega", "target": "youtube"},
        risk_level="low",
    )


def test_reflection_success_does_not_retry():
    decision = ReflectionChecker().evaluate(
        call(),
        ToolResult(tool_name="browser_search", success=True),
        RetryState(attempt_number=0, max_retries=2),
    )
    assert decision.should_retry is False
    assert decision.should_stop is False
    assert decision.reason == "tool_success"


def test_reflection_blocked_tool_stops_without_retry():
    decision = ReflectionChecker().evaluate(
        call(),
        ToolResult(
            tool_name="browser_search",
            success=False,
            error="Tool inactive in current phase",
            metadata={"blocked": True},
        ),
        RetryState(attempt_number=0, max_retries=2),
    )
    assert decision.should_retry is False
    assert decision.should_stop is True
    assert decision.reason == "blocked_tool"


def test_reflection_missing_argument_stops_without_retry():
    decision = ReflectionChecker().evaluate(
        call(),
        ToolResult(
            tool_name="browser_search",
            success=False,
            error="browser_search requires a query argument",
        ),
        RetryState(attempt_number=0, max_retries=2),
    )
    assert decision.should_retry is False
    assert decision.should_stop is True
    assert decision.reason == "deterministic_error"


def test_reflection_transient_error_retries_until_max_retries():
    checker = ReflectionChecker()
    first = checker.evaluate(
        call(),
        ToolResult(
            tool_name="browser_search",
            success=False,
            error="temporary network timeout",
        ),
        RetryState(attempt_number=0, max_retries=2),
    )
    last = checker.evaluate(
        call(),
        ToolResult(
            tool_name="browser_search",
            success=False,
            error="temporary network timeout",
        ),
        RetryState(attempt_number=2, max_retries=2),
    )
    assert first.should_retry is True
    assert first.should_stop is False
    assert last.should_retry is False
    assert last.should_stop is True
    assert last.reason == "max_retries_exhausted"
