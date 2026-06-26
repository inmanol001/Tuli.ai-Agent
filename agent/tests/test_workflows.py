from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from agent.capabilities.tools.schemas import ToolCall, ToolDefinition
from agent.gateway.message_types import ContextPackage
from agent.gateway.session_manager import SessionState
from agent.action_macros.schemas import ActionMacroPlan
from agent.executor.results import ToolResult
from agent.models.tool_planner import ToolPlannerResult
from agent.response_action.controller import ResponseController
from agent.router.router_schema import RouterDecision
from agent.workflows.finalizer import FullWorkflowFinalizer
from agent.workflows.plan_manager import WorkflowPlanManager
from agent.workflows.reasoner import WorkflowReasonerResult
from agent.workflows.runner import FullWorkflowRunner
from agent.workflows.schemas import (
    FullWorkflowPlan,
    FullWorkflowResult,
    FullWorkflowState,
    FullWorkflowStepDefinition,
)
from agent.workflows.selector import FullWorkflowSelector


def make_context(message: str) -> ContextPackage:
    return ContextPackage(
        system_prompt="system",
        user_message=message,
        router_decision=RouterDecision(route="action_ready"),
    )


def test_full_workflow_selector_picks_design_canva_post():
    plan = FullWorkflowSelector().select(
        make_context("haz un post en Canva del Día del Padre")
    )

    assert plan.selected is True
    assert plan.workflow_name == "design_canva_post"
    assert plan.status == "selected"
    assert plan.inputs["topic"] == "Día del Padre"
    assert plan.simulation_mode is True


def test_selector_selects_canva_workflow_when_canva_explicit():
    plan = FullWorkflowSelector().select(
        make_context("haz un post en Canva del Día del Padre")
    )

    assert plan.selected is True
    assert plan.workflow_name == "design_canva_post"
    assert plan.status == "selected"


def test_full_workflow_selector_requests_topic_when_missing():
    plan = FullWorkflowSelector().select(make_context("haz un post en Canva"))

    assert plan.selected is True
    assert plan.status == "needs_clarification"
    assert plan.missing_info == ["topic"]


def test_selector_requests_target_for_creative_asset_without_platform():
    plan = FullWorkflowSelector().select(
        make_context("haz un post del dia del padre")
    )

    assert plan.selected is True
    assert plan.workflow_name is None
    assert plan.status == "needs_clarification"
    assert plan.reason == "missing_workflow_target"
    assert "target_workflow_or_platform" in plan.missing_info


def test_full_workflow_selector_does_not_select_for_chat():
    plan = FullWorkflowSelector().select(make_context("hola"))

    assert plan.selected is False


class FakeExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, tool_call):
        self.calls.append(tool_call)
        raise AssertionError("design_canva_post should not call real tools in simulation mode")


class FakeReasoner:
    def __init__(self):
        self.calls = []

    def reason(self, *, workflow_name, phase_name, task, state, inputs):
        self.calls.append(
            {
                "workflow_name": workflow_name,
                "phase_name": phase_name,
                "task": task,
                "state": state.model_dump(mode="json"),
                "inputs": inputs,
            }
        )
        if phase_name == "brief_parse":
            return WorkflowReasonerResult(
                model_used="fake-reasoner",
                text="Tema principal: Día del Padre.",
            )
        return WorkflowReasonerResult(
            model_used="fake-reasoner",
            text="Prompt creativo base para Día del Padre.",
        )


class FakeWorkflowToolPlanner:
    def __init__(self):
        self.calls = []

    def plan(self, context):
        self.calls.append(context)
        hint = context.user_message
        query = "https://www.canva.com"
        if "chatgpt.com" in hint:
            query = "https://chatgpt.com"
        return ToolPlannerResult(
            model_used="fake-tool-planner",
            tool_calls=[
                ToolCall(
                    tool_name="browser_search",
                    arguments={"query": query, "target": "url"},
                )
            ],
        )


class FakeToolRegistry:
    def __init__(self):
        self.tools = {
            "browser_search": ToolDefinition(
                name="browser_search",
                description="Browser search",
                parameters={"type": "object", "properties": {}},
                declared=True,
                active=True,
            ),
            "click": ToolDefinition(
                name="click",
                description="Click",
                parameters={"type": "object", "properties": {}},
                declared=True,
                active=False,
            ),
        }

    def get(self, name):
        return self.tools.get(name)

    def find_active(self, names):
        return [
            tool
            for name in names
            if (tool := self.tools.get(name)) is not None and tool.active
        ]


class FakeWorkflowDefinition:
    def build_phases(self, inputs):
        return [
            FullWorkflowStepDefinition(
                phase_name="open_canva",
                kind="tool",
                description="Abrir Canva para preparar el workspace.",
                tool_goal="Abrir Canva con la tool disponible.",
                allowed_tools=["browser_search"],
                tool_arguments={"query": "https://www.canva.com", "target": "url"},
                expected_result="Canva abierto.",
                can_run_now=True,
            ),
            FullWorkflowStepDefinition(
                phase_name="future_click",
                kind="blocked_missing_tools",
                description="Fase futura bloqueada.",
                missing_tools=["click"],
            ),
        ]


class FakeWorkflowRegistry:
    def __init__(self):
        self.workflow = FakeWorkflowDefinition()

    def get(self, name):
        if name == "tool_phase_workflow":
            return self.workflow
        return None


class FakeWorkflowExecutor:
    def __init__(self):
        self.calls = []

    def execute(self, tool_call):
        self.calls.append(tool_call)
        return ToolResult(
            tool_name=tool_call.tool_name,
            success=True,
            data={"opened": True},
        )


def make_design_canva_runner():
    tool_planner = FakeWorkflowToolPlanner()
    executor = FakeWorkflowExecutor()
    runner = FullWorkflowRunner(
        executor=executor,
        reasoner=FakeReasoner(),
        tool_planner=tool_planner,
        tool_registry=FakeToolRegistry(),
    )
    plan = FullWorkflowPlan(
        selected=True,
        workflow_name="design_canva_post",
        inputs={
            "topic": "Día del Padre",
            "format": "post",
            "target_app": "Canva",
            "original_user_message": "haz un post en Canva del Día del Padre",
        },
        status="selected",
        reason="test",
        simulation_mode=True,
    )
    return runner, tool_planner, executor, plan


def test_full_workflow_runner_simulates_design_canva_post():
    runner, tool_planner, executor, plan = make_design_canva_runner()
    result = runner.run(plan)

    assert result.workflow_name == "design_canva_post"
    assert result.success is False
    assert result.status == "simulated"
    assert result.simulation_mode is True
    assert result.stopped_reason == "blocked_missing_tools"
    assert "screenshot" in result.missing_tools
    assert "browser_search" not in result.missing_tools
    assert len(result.phases) >= 5
    assert all(phase.phase_name for phase in result.phases)
    assert len(tool_planner.calls) == 2
    assert executor.calls[0].tool_name == "browser_search"
    assert executor.calls[1].tool_name == "browser_search"
    assert result.phases[2].phase_name == "workspace_setup"
    assert result.phases[2].kind == "tool"
    assert result.phases[2].status == "completed"
    assert result.phases[2].tool_calls
    assert result.phases[2].tool_results
    assert result.phases[2].action_runs
    assert result.phases[2].reflection_traces
    assert result.phases[2].retry_count == 0
    assert result.phases[3].phase_name == "open_chatgpt"
    assert result.phases[3].kind == "tool"
    assert result.phases[3].status == "completed"
    assert result.phases[3].tool_calls
    assert result.phases[3].tool_results
    assert result.phases[3].action_runs
    assert result.state.get_value("image_prompt") == "Prompt creativo base para Día del Padre."
    assert result.state.get_value("brief_summary") == "Tema principal: Día del Padre."


def test_full_workflow_runner_persists_runtime_plan_and_keeps_simulation_honest(tmp_path):
    runner, tool_planner, executor, plan = make_design_canva_runner()
    plan_manager = WorkflowPlanManager(base_dir=tmp_path / "runtime" / "plans")
    runner.plan_manager = plan_manager
    runner.loop_controller.plan_manager = plan_manager

    result = runner.run(
        plan,
        make_context("haz un post en Canva del Día del Padre"),
        SessionState(session_id="session-fullworkflow"),
    )

    assert result.workflow_name == "design_canva_post"
    assert result.plan_path is not None
    assert Path(result.plan_path).exists()
    assert "# Workflow Plan: design_canva_post" in Path(result.plan_path).read_text()
    assert result.phases
    assert "screenshot" in result.missing_tools
    assert result.success is False
    assert result.status == "simulated"
    assert tool_planner.calls
    assert executor.calls


def test_full_workflow_tool_phase_uses_tool_planner():
    runner, tool_planner, executor, plan = make_design_canva_runner()

    runner.run(plan)

    assert tool_planner.calls
    assert executor.calls
    assert executor.calls[0].tool_name == "browser_search"


def test_full_workflow_tool_phase_context_limits_selected_tools():
    runner, tool_planner, executor, plan = make_design_canva_runner()

    runner.run(plan)

    context = tool_planner.calls[0]
    assert [tool["name"] for tool in context.selected_tools] == ["browser_search"]
    assert "Workflow:" in context.user_message
    assert "Phase:" in context.user_message
    assert "Phase goal:" in context.user_message


def test_full_workflow_tool_phase_records_tool_calls_and_results():
    runner, tool_planner, executor, plan = make_design_canva_runner()

    result = runner.run(plan)

    tool_phases = [phase for phase in result.phases if phase.kind == "tool"]
    assert tool_phases

    first_tool_phase = tool_phases[0]
    assert first_tool_phase.status == "completed"
    assert first_tool_phase.tool_calls
    assert first_tool_phase.tool_results


def test_full_workflow_does_not_mark_active_browser_search_as_missing():
    runner, tool_planner, executor, plan = make_design_canva_runner()

    result = runner.run(plan)

    assert "browser_search" not in result.missing_tools


def test_full_workflow_still_marks_future_tools_as_missing():
    runner, tool_planner, executor, plan = make_design_canva_runner()

    result = runner.run(plan)

    assert "click" in result.missing_tools
    assert "type_text" in result.missing_tools
    assert "screenshot" in result.missing_tools
    assert "vision" in result.missing_tools


def test_full_workflow_runner_uses_tool_planner_for_tool_phase():
    tool_planner = FakeWorkflowToolPlanner()
    executor = FakeWorkflowExecutor()
    runner = FullWorkflowRunner(
        executor=executor,
        registry=FakeWorkflowRegistry(),
        tool_planner=tool_planner,
        tool_registry=FakeToolRegistry(),
    )

    result = runner.run(
        FullWorkflowPlan(
            selected=True,
            workflow_name="tool_phase_workflow",
            inputs={
                "topic": "Día del Padre",
                "original_user_message": "haz un post en Canva del Día del Padre",
            },
            status="selected",
            simulation_mode=True,
        )
    )

    assert tool_planner.calls
    phase_context = tool_planner.calls[0]
    assert [tool["name"] for tool in phase_context.selected_tools] == ["browser_search"]
    assert executor.calls[0].tool_name == "browser_search"
    phase = result.phases[0]
    assert phase.phase_name == "open_canva"
    assert phase.status == "completed"
    assert phase.tool_calls
    assert phase.tool_results
    assert "browser_search" not in result.missing_tools
    assert "click" in result.missing_tools


def test_full_workflow_finalizer_explains_simulation_and_missing_tools():
    result = FullWorkflowFinalizer().finalize(
        user_message="haz un post en Canva del Día del Padre",
        workflow_result=FullWorkflowResult(
            workflow_name="design_canva_post",
            inputs={"topic": "Día del Padre"},
            state=FullWorkflowState(
                data={
                    "image_prompt": "Prompt creativo base para Día del Padre.",
                    "copy_text": "Texto breve para Día del Padre.",
                }
            ),
            status="simulated",
            simulation_mode=True,
            phases=[],
            success=False,
            missing_tools=["screenshot", "vision", "click"],
            stopped_reason="blocked_missing_tools",
        ),
    )

    assert "Preparé y simulé el workflow de Canva" in result.text
    assert "Día del Padre" in result.text
    assert "screenshot" in result.text
    assert "vision" in result.text
    assert "click" in result.text
    assert "creado de verdad" in result.text
    assert "Prompt creativo base" in result.text or "Estado razonado" in result.text


class FakeFullWorkflowSelector:
    def __init__(self, plan):
        self.plan = plan
        self.calls = []

    def select(self, context):
        self.calls.append(context)
        return self.plan


class FakeFullWorkflowRunner:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def run(self, workflow_plan):
        self.calls.append(workflow_plan)
        return self.result


class FakeFullWorkflowFinalizer:
    def __init__(self, text="full workflow final"):
        self.calls = []
        self.text = text

    def finalize(self, *, user_message, workflow_result):
        self.calls.append(
            {"user_message": user_message, "workflow_result": workflow_result}
        )
        return SimpleNamespace(
            text=self.text,
            fallback=True,
            error=None,
            model_dump=lambda mode="json": {
                "text": self.text,
                "fallback": True,
                "error": None,
            },
        )


class FakeActionMacroSelector:
    def __init__(self, plan=None):
        self.calls = []
        self.plan = plan or ActionMacroPlan(selected=False)

    def select(self, context):
        self.calls.append(context)
        return self.plan


class FakeActionMacroExecutor:
    def __init__(self):
        self.calls = []

    def run(self, workflow_plan):
        self.calls.append(workflow_plan)
        raise AssertionError("action macros should not run when full workflow is selected")


class FakeToolPlanner:
    def __init__(self):
        self.calls = []

    def plan(self, context):
        self.calls.append(context)
        return ToolPlannerResult(model_used="fake", tool_calls=[])


def test_response_controller_uses_full_workflow_before_action_macros():
    full_plan = FullWorkflowPlan(
        selected=True,
        workflow_name="design_canva_post",
        inputs={"topic": "Día del Padre"},
        status="selected",
        simulation_mode=True,
    )
    full_result = FullWorkflowResult(
        workflow_name="design_canva_post",
        inputs={"topic": "Día del Padre"},
        status="simulated",
        simulation_mode=True,
        phases=[],
        success=False,
        missing_tools=["screenshot"],
        stopped_reason="blocked_missing_tools",
    )
    controller = ResponseController(
        full_workflow_selector=FakeFullWorkflowSelector(full_plan),
        full_workflow_runner=FakeFullWorkflowRunner(full_result),
        full_workflow_finalizer=FakeFullWorkflowFinalizer(),
        action_macro_selector=FakeActionMacroSelector(),
        action_macro_executor=FakeActionMacroExecutor(),
        tool_planner=FakeToolPlanner(),
    )

    response = controller.handle_action_ready(
        make_context("haz un post en Canva del Día del Padre"),
        SimpleNamespace(session_id="s1", pending_clarification=None),
        debug={},
    )

    assert response.text == "full workflow final"
    assert response.debug["full_workflow"]["workflow_name"] == "design_canva_post"
    assert response.debug["full_workflow_selector"]["workflow_name"] == "design_canva_post"
    assert response.debug["full_workflow_finalizer"]["text"] == "full workflow final"


def test_controller_asks_workflow_target_clarification():
    clarification_plan = FullWorkflowPlan(
        selected=True,
        workflow_name=None,
        status="needs_clarification",
        reason="missing_workflow_target",
        missing_info=["target_workflow_or_platform"],
        inputs={"topic": "dia del padre", "format": "post"},
        simulation_mode=True,
    )
    controller = ResponseController(
        full_workflow_selector=FakeFullWorkflowSelector(clarification_plan),
        full_workflow_runner=FakeFullWorkflowRunner(
            FullWorkflowResult(
                workflow_name="design_canva_post",
                inputs={},
                status="simulated",
                simulation_mode=True,
                phases=[],
                success=False,
            )
        ),
        full_workflow_finalizer=FakeFullWorkflowFinalizer(),
        action_macro_selector=FakeActionMacroSelector(),
        action_macro_executor=FakeActionMacroExecutor(),
        tool_planner=FakeToolPlanner(),
    )

    response = controller.handle_action_ready(
        make_context("haz un post del dia del padre"),
        SimpleNamespace(session_id="s1", pending_clarification=None),
        debug={},
    )

    assert response.status == "needs_clarification"
    assert "texto solamente" in response.text
    assert "Canva" in response.text


def test_response_controller_falls_back_to_action_macros_when_no_full_workflow():
    action_macro_selector = FakeActionMacroSelector()
    controller = ResponseController(
        full_workflow_selector=FakeFullWorkflowSelector(FullWorkflowPlan(selected=False)),
        full_workflow_runner=FakeFullWorkflowRunner(
            FullWorkflowResult(
                workflow_name="design_canva_post",
                inputs={},
                status="simulated",
                simulation_mode=True,
                phases=[],
                success=False,
            )
        ),
        full_workflow_finalizer=FakeFullWorkflowFinalizer(),
        action_macro_selector=action_macro_selector,
        action_macro_executor=FakeActionMacroExecutor(),
        tool_planner=FakeToolPlanner(),
    )

    controller.handle_action_ready(
        make_context("pon la ventana a la derecha"),
        SimpleNamespace(session_id="s1", pending_clarification=None),
        debug={},
    )

    assert len(action_macro_selector.calls) == 1
