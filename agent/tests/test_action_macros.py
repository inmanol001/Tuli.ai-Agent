from __future__ import annotations

from types import SimpleNamespace

from agent.capabilities.tools.schemas import ToolCall
from agent.executor.results import ToolResult
from agent.gateway.message_types import ContextPackage
from agent.execution.schemas import ActionAttemptResult, ActionRunResult
from agent.models.tool_finalizer import ToolFinalizerResult
from agent.models.tool_planner import ToolPlannerResult
from agent.response_action.controller import ResponseController
from agent.router.router_schema import RouterDecision
from agent.action_macros.executor import ActionMacroExecutor as WorkflowExecutor
from agent.action_macros.finalizer import ActionMacroFinalizer as WorkflowFinalizer
from agent.action_macros.schemas import (
    ActionMacroPlan as WorkflowPlan,
    ActionMacroResult as WorkflowResult,
    ActionMacroStepResult as WorkflowStepResult,
)
from agent.action_macros.selector import ActionMacroSelector as WorkflowSelector
from agent.reflection.schemas import ReflectionDecision


def make_context(message: str) -> ContextPackage:
    return ContextPackage(
        system_prompt="system",
        user_message=message,
        router_decision=RouterDecision(route="action_ready"),
    )


def step(tool_name: str, arguments: dict | None = None, *, success: bool = True, data=None, error=None):
    return WorkflowStepResult(
        step_index=0,
        tool_call=ToolCall(tool_name=tool_name, arguments=arguments or {}),
        tool_result=ToolResult(
            tool_name=tool_name,
            success=success,
            data=data or {},
            error=error,
        ),
        success=success,
        stopped=not success,
        stop_reason=None if success else f"step_failed:{tool_name}",
    )


def action_run(
    tool_call: ToolCall,
    *,
    success: bool = True,
    data=None,
    error=None,
    stopped: bool = False,
    stop_reason: str | None = None,
    retry_count: int = 0,
) -> ActionRunResult:
    tool_result = ToolResult(
        tool_name=tool_call.tool_name,
        success=success,
        data=data or {},
        error=error,
    )
    attempt = ActionAttemptResult(
        attempt_number=0,
        execution_number=1,
        tool_call=tool_call.model_dump(mode="json"),
        tool_result=tool_result.model_dump(mode="json"),
        reflection_decision=ReflectionDecision(
            should_stop=stopped and not success,
            reason=stop_reason or ("tool_success" if success else "deterministic_error"),
            user_message="",
        ).model_dump(mode="json"),
    )
    return ActionRunResult(
        tool_call=tool_call,
        final_tool_result=tool_result,
        attempts=[attempt],
        success=success,
        stopped=stopped,
        stop_reason=stop_reason,
        retry_count=retry_count,
        reflection_trace=[attempt.model_dump(mode="json")],
    )


def test_selector_picks_open_app_and_tile_window_for_chrome_right():
    plan = WorkflowSelector().select(make_context("abre Chrome y ponlo a la derecha"))
    assert plan.selected is True
    assert plan.workflow_name == "open_app_and_tile_window"
    assert plan.inputs == {"app_name": "Google Chrome", "window_action": "right"}


def test_selector_picks_open_app_and_tile_window_for_finder_center():
    plan = WorkflowSelector().select(make_context("abre Finder y céntralo"))
    assert plan.selected is True
    assert plan.workflow_name == "open_app_and_tile_window"
    assert plan.inputs == {"app_name": "Finder", "window_action": "center"}


def test_selector_picks_tile_active_window_for_simple_window_action():
    plan = WorkflowSelector().select(make_context("pon la ventana a la derecha"))
    assert plan.selected is True
    assert plan.workflow_name == "tile_active_window"
    assert plan.inputs == {"window_action": "right"}


def test_selector_detects_top_left_corner_before_generic_top_or_left():
    plan = WorkflowSelector().select(
        make_context("manda la ventana a la esquina superior izquierda")
    )
    assert plan.selected is True
    assert plan.workflow_name == "tile_active_window"
    assert plan.inputs == {"window_action": "top-left"}


def test_selector_does_not_select_for_chat():
    plan = WorkflowSelector().select(make_context("hola"))
    assert plan.selected is False


def test_selector_does_not_select_for_open_app_only():
    plan = WorkflowSelector().select(make_context("abre Chrome"))
    assert plan.selected is False


def test_selector_picks_open_browser_and_search_for_search_intent():
    plan = WorkflowSelector().select(make_context("busca gatos"))
    assert plan.selected is True
    assert plan.workflow_name == "open_browser_and_search"
    assert plan.inputs == {"query": "gatos", "target": "web"}


def test_selector_picks_play_random_youtube_video():
    plan = WorkflowSelector().select(make_context("Ponme un video random en YouTube"))
    assert plan.selected is True
    assert plan.workflow_name == "play_random_youtube_video"
    assert plan.inputs == {"query": "random video"}


def test_selector_picks_open_work_setup():
    plan = WorkflowSelector().select(make_context("Abre mi setup de trabajo"))
    assert plan.selected is True
    assert plan.workflow_name == "open_work_setup"
    assert plan.inputs == {"open_chatgpt": True}


def test_selector_picks_open_browser_and_search_for_explicit_browser_query():
    plan = WorkflowSelector().select(make_context("abre el navegador y busca pandas"))
    assert plan.selected is True
    assert plan.workflow_name == "open_browser_and_search"
    assert plan.inputs == {"query": "pandas", "target": "web"}


class FakeExecutor:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def execute(self, tool_call):
        self.calls.append(tool_call)
        if self.results:
            return self.results.pop(0)
        return ToolResult(tool_name=tool_call.tool_name, success=False, error="missing result")


class FakeActionRunner:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def run_tool_call(self, tool_call):
        self.calls.append(tool_call)
        if self.results:
            return self.results.pop(0)
        return action_run(
            tool_call,
            success=False,
            stopped=True,
            stop_reason="missing_result",
            error="missing result",
        )


def test_workflow_executor_runs_open_app_then_observe_then_tile():
    executor = FakeExecutor(
        [
            ToolResult(tool_name="open_app", success=True, data={"app_name": "Google Chrome"}),
            ToolResult(
                tool_name="macos_observe_frontmost",
                success=True,
                data={"app_name": "Google Chrome", "window_title": "Chrome"},
            ),
            ToolResult(
                tool_name="window_native_tiling",
                success=True,
                data={"action": "right", "verified": False},
            ),
        ]
    )
    result = WorkflowExecutor(executor=executor).run(
        WorkflowPlan(
            selected=True,
            workflow_name="open_app_and_tile_window",
            inputs={"app_name": "Google Chrome", "window_action": "right"},
        )
    )

    assert [call.tool_name for call in executor.calls] == [
        "open_app",
        "macos_observe_frontmost",
        "window_native_tiling",
    ]
    assert result.success is True
    assert len(result.steps) == 3


def test_workflow_executor_stops_when_open_app_fails():
    executor = FakeExecutor(
        [
            ToolResult(tool_name="open_app", success=False, error="could not open"),
        ]
    )
    result = WorkflowExecutor(executor=executor).run(
        WorkflowPlan(
            selected=True,
            workflow_name="open_app_and_tile_window",
            inputs={"app_name": "Google Chrome", "window_action": "right"},
        )
    )

    assert [call.tool_name for call in executor.calls] == ["open_app"]
    assert result.success is False
    assert result.stopped_reason == "step_failed:open_app"
    assert len(result.steps) == 1


def test_workflow_executor_marks_window_tiling_failure():
    executor = FakeExecutor(
        [
            ToolResult(tool_name="open_app", success=True, data={"app_name": "Google Chrome"}),
            ToolResult(
                tool_name="macos_observe_frontmost",
                success=True,
                data={"app_name": "Google Chrome"},
            ),
            ToolResult(tool_name="window_native_tiling", success=False, error="no permission"),
        ]
    )
    result = WorkflowExecutor(executor=executor).run(
        WorkflowPlan(
            selected=True,
            workflow_name="open_app_and_tile_window",
            inputs={"app_name": "Google Chrome", "window_action": "right"},
        )
    )

    assert result.success is False
    assert result.stopped_reason == "step_failed:window_native_tiling"


def test_workflow_executor_runs_tile_active_window_with_observe_then_tile():
    executor = FakeExecutor(
        [
            ToolResult(
                tool_name="macos_observe_frontmost",
                success=True,
                data={"app_name": "Safari", "window_title": "Safari"},
            ),
            ToolResult(tool_name="window_native_tiling", success=True, data={"action": "right"}),
        ]
    )
    result = WorkflowExecutor(executor=executor).run(
        WorkflowPlan(
            selected=True,
            workflow_name="tile_active_window",
            inputs={"window_action": "right"},
        )
    )

    assert [call.tool_name for call in executor.calls] == [
        "macos_observe_frontmost",
        "window_native_tiling",
    ]
    assert result.success is True


def test_workflow_executor_stops_when_tile_active_window_has_no_frontmost_window():
    executor = FakeExecutor(
        [
            ToolResult(
                tool_name="macos_observe_frontmost",
                success=True,
                data={"app_name": None, "window_title": None},
            )
        ]
    )
    result = WorkflowExecutor(executor=executor).run(
        WorkflowPlan(
            selected=True,
            workflow_name="tile_active_window",
            inputs={"window_action": "right"},
        )
    )

    assert result.success is False
    assert result.stopped_reason == "no_frontmost_window"
    assert [call.tool_name for call in executor.calls] == ["macos_observe_frontmost"]


def test_workflow_executor_runs_play_random_youtube_video_through_action_runner():
    open_call = ToolCall(tool_name="open_app", arguments={"app_name": "Google Chrome"})
    search_call = ToolCall(
        tool_name="browser_search",
        arguments={"query": "random video", "target": "youtube"},
    )
    runner = FakeActionRunner(
        [
            action_run(open_call, success=True, data={"app_name": "Google Chrome"}),
            action_run(
                search_call,
                success=True,
                data={"query": "random video", "target": "youtube", "url": "https://www.youtube.com/results?search_query=random+video"},
            ),
        ]
    )
    result = WorkflowExecutor(executor=FakeExecutor([]), action_runner=runner).run(
        WorkflowPlan(
            selected=True,
            workflow_name="play_random_youtube_video",
            inputs={"query": "random video"},
        )
    )

    assert [call.tool_name for call in runner.calls] == ["open_app", "browser_search"]
    assert len(result.steps) == 2
    assert result.success is True
    assert result.steps[0].action_run is not None
    assert result.steps[1].action_run is not None


def test_workflow_executor_runs_open_work_setup_through_action_runner():
    chrome_call = ToolCall(tool_name="open_app", arguments={"app_name": "Google Chrome"})
    vscode_call = ToolCall(tool_name="open_app", arguments={"app_name": "Visual Studio Code"})
    terminal_call = ToolCall(tool_name="open_app", arguments={"app_name": "Terminal"})
    chatgpt_call = ToolCall(
        tool_name="open_url",
        arguments={"url": "https://chatgpt.com"},
    )
    runner = FakeActionRunner(
        [
            action_run(chrome_call, success=True, data={"app_name": "Google Chrome"}),
            action_run(vscode_call, success=True, data={"app_name": "Visual Studio Code"}),
            action_run(terminal_call, success=True, data={"app_name": "Terminal"}),
            action_run(chatgpt_call, success=True, data={"url": "https://chatgpt.com"}),
        ]
    )
    result = WorkflowExecutor(executor=FakeExecutor([]), action_runner=runner).run(
        WorkflowPlan(
            selected=True,
            workflow_name="open_work_setup",
            inputs={"open_chatgpt": True},
        )
    )

    assert [call.tool_name for call in runner.calls] == [
        "open_app",
        "open_app",
        "open_app",
        "open_url",
    ]
    assert len(result.steps) == 4
    assert result.success is True


def test_workflow_executor_stops_when_action_runner_stops():
    open_call = ToolCall(tool_name="open_app", arguments={"app_name": "Google Chrome"})
    runner = FakeActionRunner(
        [
            action_run(
                open_call,
                success=False,
                stopped=True,
                stop_reason="deterministic_error",
                error="could not open",
            )
        ]
    )
    result = WorkflowExecutor(executor=FakeExecutor([]), action_runner=runner).run(
        WorkflowPlan(
            selected=True,
            workflow_name="play_random_youtube_video",
            inputs={"query": "random video"},
        )
    )

    assert result.success is False
    assert result.stopped_reason == "step_failed:open_app"
    assert len(result.steps) == 1
    assert result.steps[0].action_run is not None


def test_workflow_executor_runs_open_browser_and_search_through_action_runner():
    search_call = ToolCall(
        tool_name="browser_search",
        arguments={"query": "pandas", "target": "web"},
    )
    runner = FakeActionRunner([action_run(search_call, success=True, data={"url": "https://google.test"})])
    result = WorkflowExecutor(executor=FakeExecutor([]), action_runner=runner).run(
        WorkflowPlan(
            selected=True,
            workflow_name="open_browser_and_search",
            inputs={"query": "pandas", "target": "web"},
        )
    )

    assert [call.tool_name for call in runner.calls] == ["browser_search"]
    assert len(result.steps) == 1
    assert result.success is True
    assert result.steps[0].action_run is not None


def test_workflow_finalizer_success_messages_are_honest():
    result = WorkflowFinalizer().finalize(
        user_message="abre Chrome y ponlo a la derecha",
        workflow_result=WorkflowResult(
            workflow_name="open_app_and_tile_window",
            inputs={"app_name": "Google Chrome", "window_action": "right"},
            steps=[
                step("open_app", {"app_name": "Google Chrome"}, data={"app_name": "Google Chrome"}),
                step(
                    "macos_observe_frontmost",
                    {},
                    data={"app_name": "Google Chrome", "window_title": "Chrome"},
                ),
                step(
                    "window_native_tiling",
                    {"action": "right"},
                    data={"action": "right", "verified": False},
                ),
            ],
            success=True,
        ),
    )

    assert "Google Chrome" in result.text
    assert "colocar la ventana activa a la derecha" in result.text
    assert "verifiqué" not in result.text.lower()


def test_workflow_finalizer_tile_success_uses_action_phrase():
    result = WorkflowFinalizer().finalize(
        user_message="pon la ventana a la derecha",
        workflow_result=WorkflowResult(
            workflow_name="tile_active_window",
            inputs={"window_action": "right"},
            steps=[
                step(
                    "macos_observe_frontmost",
                    {},
                    data={"app_name": "Safari", "window_title": "Safari"},
                ),
                step("window_native_tiling", {"action": "right"}, data={"action": "right"}),
            ],
            success=True,
        ),
    )

    assert result.text == "Envié la acción para colocar la ventana activa a la derecha."


def test_workflow_finalizer_open_app_failure_mentions_app_and_error():
    result = WorkflowFinalizer().finalize(
        user_message="abre Chrome y ponlo a la derecha",
        workflow_result=WorkflowResult(
            workflow_name="open_app_and_tile_window",
            inputs={"app_name": "Google Chrome", "window_action": "right"},
            steps=[
                step("open_app", {"app_name": "Google Chrome"}, success=False, error="not authorized"),
            ],
            success=False,
            stopped_reason="step_failed:open_app",
        ),
    )

    assert result.text == "No pude completar la action macro porque no se pudo abrir Google Chrome: not authorized"


def test_workflow_finalizer_window_failure_mentions_moving_window():
    result = WorkflowFinalizer().finalize(
        user_message="abre Chrome y ponlo a la derecha",
        workflow_result=WorkflowResult(
            workflow_name="open_app_and_tile_window",
            inputs={"app_name": "Google Chrome", "window_action": "right"},
            steps=[
                step("open_app", {"app_name": "Google Chrome"}, data={"app_name": "Google Chrome"}),
                step("macos_observe_frontmost", {}, data={"app_name": "Google Chrome"}),
                step(
                    "window_native_tiling",
                    {"action": "right"},
                    success=False,
                    error="menu item not found",
                ),
            ],
            success=False,
            stopped_reason="step_failed:window_native_tiling",
        ),
    )

    assert result.text == "Abrí Google Chrome, pero no pude mover la ventana activa: menu item not found"


class FakeWorkflowSelector:
    def __init__(self, plan):
        self.plan = plan
        self.calls = []

    def select(self, context):
        self.calls.append(context)
        return self.plan


class FakeWorkflowExecutor:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, workflow_plan):
        self.calls.append(workflow_plan)
        return self.result


class FakeWorkflowFinalizer:
    def __init__(self, result_text="workflow final"):
        self.calls = []
        self.result_text = result_text

    def finalize(self, *, user_message, workflow_result):
        self.calls.append(
            {"user_message": user_message, "workflow_result": workflow_result}
        )
        return SimpleNamespace(text=self.result_text, fallback=True, error=None, model_dump=lambda mode="json": {"text": self.result_text, "fallback": True, "error": None})


class FakeToolPlanner:
    def __init__(self):
        self.calls = []

    def plan(self, context):
        self.calls.append(context)
        return ToolPlannerResult(
            model_used="fake",
            tool_calls=[
                ToolCall(
                    tool_name="browser_search",
                    arguments={"query": context.user_message},
                    risk_level="low",
                )
            ],
        )


class FakeToolFinalizer:
    def __init__(self):
        self.calls = []

    def finalize(self, *, user_message, tool_call, tool_result):
        self.calls.append(
            {"user_message": user_message, "tool_call": tool_call, "tool_result": tool_result}
        )
        return ToolFinalizerResult(
            model_used="fake",
            text="tool final",
            fallback=True,
            error=None,
        )


def test_response_controller_uses_workflow_before_tool_planner():
    workflow_plan = WorkflowPlan(
        selected=True,
        workflow_name="tile_active_window",
        inputs={"window_action": "right"},
    )
    workflow_result = WorkflowResult(
        workflow_name="tile_active_window",
        inputs={"window_action": "right"},
        steps=[
            step(
                "macos_observe_frontmost",
                {},
                data={"app_name": "Safari", "window_title": "Safari"},
            ),
            step("window_native_tiling", {"action": "right"}, data={"action": "right"}),
        ],
        success=True,
    )
    controller = ResponseController(
        tool_planner=FakeToolPlanner(),
        workflow_selector=FakeWorkflowSelector(workflow_plan),
        workflow_executor=FakeWorkflowExecutor(workflow_result),
        workflow_finalizer=FakeWorkflowFinalizer(),
        tool_finalizer=FakeToolFinalizer(),
    )

    response = controller.handle_action_ready(make_context("pon la ventana a la derecha"), SimpleNamespace(session_id="s1", pending_clarification=None), debug={})

    assert response.text == "workflow final"
    assert controller.tool_planner.calls == []


def test_response_controller_falls_back_to_tool_planner_when_no_workflow():
    planner = FakeToolPlanner()
    controller = ResponseController(
        tool_planner=planner,
        workflow_selector=FakeWorkflowSelector(WorkflowPlan(selected=False)),
        workflow_executor=FakeWorkflowExecutor(WorkflowResult(workflow_name="tile_active_window", inputs={}, success=False)),
        workflow_finalizer=FakeWorkflowFinalizer(),
        tool_finalizer=FakeToolFinalizer(),
    )
    controller.handle_action_ready(make_context("busca gatos"), SimpleNamespace(session_id="s1", pending_clarification=None), debug={})
    assert len(planner.calls) == 1


def test_response_controller_debug_includes_workflow_details():
    workflow_plan = WorkflowPlan(
        selected=True,
        workflow_name="tile_active_window",
        inputs={"window_action": "right"},
    )
    workflow_result = WorkflowResult(
        workflow_name="tile_active_window",
        inputs={"window_action": "right"},
        steps=[
            step(
                "macos_observe_frontmost",
                {},
                data={"app_name": "Safari", "window_title": "Safari"},
            ),
            step("window_native_tiling", {"action": "right"}, data={"action": "right"}),
        ],
        success=True,
    )
    controller = ResponseController(
        tool_planner=FakeToolPlanner(),
        workflow_selector=FakeWorkflowSelector(workflow_plan),
        workflow_executor=FakeWorkflowExecutor(workflow_result),
        workflow_finalizer=FakeWorkflowFinalizer(),
        tool_finalizer=FakeToolFinalizer(),
    )
    response = controller.handle_action_ready(
        make_context("pon la ventana a la derecha"),
        SimpleNamespace(session_id="s1", pending_clarification=None),
        debug={},
    )

    assert "action_macro_selector" in response.debug
    assert "action_macro" in response.debug
    assert "action_macro_finalizer" in response.debug
    assert len(response.tool_calls) == 2


def test_response_controller_runs_play_random_youtube_video_macro_through_action_runner():
    open_call = ToolCall(tool_name="open_app", arguments={"app_name": "Google Chrome"})
    search_call = ToolCall(
        tool_name="browser_search",
        arguments={"query": "random video", "target": "youtube"},
    )
    runner = FakeActionRunner(
        [
            action_run(open_call, success=True, data={"app_name": "Google Chrome"}),
            action_run(
                search_call,
                success=True,
                data={
                    "query": "random video",
                    "target": "youtube",
                    "url": "https://www.youtube.com/results?search_query=random+video",
                },
            ),
        ]
    )
    controller = ResponseController(
        full_workflow_selector=FakeWorkflowSelector(FullWorkflowPlan(selected=False)),
        full_workflow_runner=FakeWorkflowExecutor(
            FullWorkflowResult(
                workflow_name="design_canva_post",
                inputs={},
                status="simulated",
                simulation_mode=True,
                phases=[],
                success=False,
            )
        ),
        full_workflow_finalizer=FakeWorkflowFinalizer(),
        action_macro_selector=WorkflowSelector(),
        action_macro_executor=WorkflowExecutor(
            executor=FakeExecutor([]),
            action_runner=runner,
        ),
        action_macro_finalizer=WorkflowFinalizer(),
        tool_planner=FakeToolPlanner(),
    )

    response = controller.handle_action_ready(
        make_context("Ponme un video random en YouTube"),
        SimpleNamespace(session_id="s1", pending_clarification=None),
        debug={},
    )

    assert response.text == "Abrí YouTube en Chrome y dejé un video aleatorio listo."
    assert [call.tool_name for call in runner.calls] == ["open_app", "browser_search"]
    assert controller.tool_planner.calls == []


def test_response_controller_runs_open_work_setup_macro_through_action_runner():
    runner = FakeActionRunner(
        [
            action_run(
                ToolCall(tool_name="open_app", arguments={"app_name": "Google Chrome"}),
                success=True,
                data={"app_name": "Google Chrome"},
            ),
            action_run(
                ToolCall(tool_name="open_app", arguments={"app_name": "Visual Studio Code"}),
                success=True,
                data={"app_name": "Visual Studio Code"},
            ),
            action_run(
                ToolCall(tool_name="open_app", arguments={"app_name": "Terminal"}),
                success=True,
                data={"app_name": "Terminal"},
            ),
            action_run(
                ToolCall(tool_name="open_url", arguments={"url": "https://chatgpt.com"}),
                success=True,
                data={"url": "https://chatgpt.com"},
            ),
        ]
    )
    controller = ResponseController(
        full_workflow_selector=FakeWorkflowSelector(FullWorkflowPlan(selected=False)),
        full_workflow_runner=FakeWorkflowExecutor(
            FullWorkflowResult(
                workflow_name="design_canva_post",
                inputs={},
                status="simulated",
                simulation_mode=True,
                phases=[],
                success=False,
            )
        ),
        full_workflow_finalizer=FakeWorkflowFinalizer(),
        action_macro_selector=WorkflowSelector(),
        action_macro_executor=WorkflowExecutor(
            executor=FakeExecutor([]),
            action_runner=runner,
        ),
        action_macro_finalizer=WorkflowFinalizer(),
        tool_planner=FakeToolPlanner(),
    )

    response = controller.handle_action_ready(
        make_context("Abre mi setup de trabajo"),
        SimpleNamespace(session_id="s1", pending_clarification=None),
        debug={},
    )

    assert response.text == "Abrí tu setup de trabajo: Chrome, Visual Studio Code y Terminal."
    assert [call.tool_name for call in runner.calls] == [
        "open_app",
        "open_app",
        "open_app",
        "open_url",
    ]
    assert controller.tool_planner.calls == []
