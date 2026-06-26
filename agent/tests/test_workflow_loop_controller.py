from __future__ import annotations

from types import SimpleNamespace

from agent.gateway.message_types import ContextPackage
from agent.gateway.session_manager import SessionState
from agent.router.router_schema import RouterDecision
from agent.workflows.definitions import DesignCanvaPostWorkflow
from agent.workflows.loop_controller import WorkflowLoopController
from agent.workflows.plan_manager import WorkflowPlanManager
from agent.workflows.schemas import FullWorkflowPlan, FullWorkflowStepDefinition
from agent.workflows.reasoner import WorkflowReasonerResult


class FakeExecutor:
    def __init__(self) -> None:
        self.calls = []

    def execute(self, tool_call):
        self.calls.append(tool_call)
        raise AssertionError("No se esperaba ejecutar tools en esta prueba")


class FakeToolPlanner:
    def plan(self, context):
        raise AssertionError("No se esperaba planner de tools en esta prueba")


class CountingReasoner:
    def __init__(self) -> None:
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
        return WorkflowReasonerResult(
            model_used="fake-reasoner",
            text=f"{phase_name} listo",
        )


class LimitWorkflow:
    name = "limit_workflow"

    def build_phases(self, inputs):
        return [
            FullWorkflowStepDefinition(
                phase_name=f"reason_{index}",
                kind="reason",
                description=f"Paso de razonamiento {index}",
                reason_task=f"razona el paso {index}",
                can_run_now=True,
            )
            for index in range(11)
        ]


def make_context(message: str) -> ContextPackage:
    return ContextPackage(
        system_prompt="system",
        user_message=message,
        router_decision=RouterDecision(route="action_ready"),
    )


def test_loop_controller_pauses_for_missing_canva_details(tmp_path):
    manager = WorkflowPlanManager(base_dir=tmp_path / "plans")
    controller = WorkflowLoopController(
        executor=FakeExecutor(),
        reasoner=CountingReasoner(),
        tool_planner=FakeToolPlanner(),
        plan_manager=manager,
    )

    plan = FullWorkflowPlan(
        selected=True,
        workflow_name="design_canva_post",
        inputs={"topic": "Día del Padre"},
        status="selected",
        simulation_mode=True,
    )

    result = controller.run(
        plan,
        DesignCanvaPostWorkflow(),
        make_context("haz un post en Canva del Día del Padre"),
        SessionState(session_id="session-1"),
    )

    assert result.status == "waiting_user_input"
    assert result.success is False
    assert result.stopped_reason == "missing_info"
    assert result.phases[0].status == "waiting_user_input"
    assert result.state.get_value("active_checkpoint") is not None

    saved_files = list((tmp_path / "plans" / "session-1").glob("*.json"))
    assert saved_files, "El plan runtime debería haberse persistido"


def test_loop_controller_pauses_for_missing_canva_details_with_specific_question(tmp_path):
    manager = WorkflowPlanManager(base_dir=tmp_path / "plans")
    controller = WorkflowLoopController(
        executor=FakeExecutor(),
        reasoner=CountingReasoner(),
        tool_planner=FakeToolPlanner(),
        plan_manager=manager,
    )

    plan = FullWorkflowPlan(
        selected=True,
        workflow_name="design_canva_post",
        inputs={"topic": "Bellamar"},
        status="selected",
        simulation_mode=True,
    )

    result = controller.run(
        plan,
        DesignCanvaPostWorkflow(),
        make_context("Hazme un post en Canva para Bellamar"),
        SessionState(session_id="session-1b"),
    )

    assert result.status == "waiting_user_input"
    assert result.needs_user_input is True
    assert result.question is not None
    assert "post cuadrado" in result.question or "flyer" in result.question
    assert "estilo" in result.question
    saved_files = list((tmp_path / "plans" / "session-1b").glob("*.json"))
    assert saved_files, "El plan runtime debería haberse persistido"


def test_loop_controller_stops_at_hard_limits(tmp_path):
    manager = WorkflowPlanManager(base_dir=tmp_path / "plans")
    reasoner = CountingReasoner()
    controller = WorkflowLoopController(
        executor=FakeExecutor(),
        reasoner=reasoner,
        tool_planner=FakeToolPlanner(),
        plan_manager=manager,
        max_steps=10,
    )

    plan = FullWorkflowPlan(
        selected=True,
        workflow_name="limit_workflow",
        inputs={},
        status="selected",
        simulation_mode=False,
    )

    result = controller.run(
        plan,
        LimitWorkflow(),
        make_context("haz una prueba de límites"),
        SessionState(session_id="session-2"),
    )

    assert result.status == "blocked"
    assert result.success is False
    assert result.stopped_reason == "workflow_limits_exceeded"
    assert len(reasoner.calls) == 10
    assert result.phases[-1].stop_reason == "workflow_limits_exceeded"
