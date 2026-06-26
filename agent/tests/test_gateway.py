from pathlib import Path
import subprocess
from types import SimpleNamespace

from agent.models.action_models import ModelAction
from agent.capabilities.tools.schemas import ToolCall
from agent.gateway.gateway import Gateway
from agent.gateway.message_types import AgentResponse
from agent.gateway.gateway_logger import GatewayLogger
from agent.gateway.pipeline import Pipeline
from agent.gateway.session_manager import SessionManager
from agent.context_builder.builder import ContextBuilder
from agent.action_macros.executor import ActionMacroExecutor
from agent.action_macros.finalizer import ActionMacroFinalizer
from agent.action_macros.selector import ActionMacroSelector
from agent.executor.results import ToolResult
from agent.memory.sqlite_store import SQLiteStore
from agent.models.main_model import MainModel
from agent.models.tool_finalizer import ToolFinalizerResult
from agent.models.tool_planner import ToolPlannerResult
from agent.response_action.controller import ResponseController
from agent.router.router_schema import RouterDecision, RouterResult
from agent.reflection.schemas import ReflectionDecision
from agent.workflows.plan_manager import WorkflowPlanManager
from agent.workflows.plan_schemas import WorkflowPlanStep
from agent.workflows.schemas import FullWorkflowResult, FullWorkflowState


class FakeRouter:
    def route(self, user_text: str) -> RouterResult:
        if "youtube" in user_text.lower() and "omega" in user_text.lower():
            decision = RouterDecision(
                intent="action",
                domain="browser",
                action="search",
                route="action_ready",
                needs_tool=True,
                suggested_plugins=["browser"],
                suggested_skills=["browser_search"],
                suggested_tools=["browser_search"],
            )
        elif "YouTube" in user_text:
            decision = RouterDecision(
                intent="action",
                domain="browser",
                action="search",
                route="clarification",
                needs_tool=True,
                needs_clarification=True,
                missing_info=["search_query"],
                suggested_plugins=["browser"],
                suggested_skills=["browser_search"],
                suggested_tools=["browser_search"],
            )
        elif "ventana" in user_text.lower():
            decision = RouterDecision(
                intent="action",
                domain="macos",
                action="window_native_tiling",
                route="action_ready",
                needs_tool=True,
                suggested_plugins=["macos"],
                suggested_skills=["macos_windows"],
                suggested_tools=["window_native_tiling"],
            )
        else:
            decision = RouterDecision(route="chat")
        return RouterResult(
            decision=decision,
            model_used="fake",
            raw="{}",
            corrected=True,
        )


class ObservationRouter:
    def route(self, user_text: str) -> RouterResult:
        mapping = {
            "qué app está abierta": ("observe_frontmost", "macos_observe_frontmost"),
            "qué ventanas hay abiertas": ("visible_windows", "macos_visible_windows"),
            "revisa permisos de mac": ("permissions_check", "macos_permissions_check"),
            "qué apps puedo abrir": ("list_apps", "macos_list_apps"),
        }
        action, tool = mapping[user_text]
        return RouterResult(
            decision=RouterDecision(
                intent="action",
                domain="macos",
                action=action,
                route="action_ready",
                needs_tool=True,
                suggested_plugins=["macos"],
                suggested_skills=["macos_observation"],
                suggested_tools=[tool],
            ),
            model_used="fake",
            raw="{}",
            corrected=True,
        )


class SpacesRouter:
    def route(self, user_text: str) -> RouterResult:
        mapping = {
            "cambia al siguiente escritorio": ("space_next", "macos_space_next", "low"),
            "cambia al escritorio anterior": ("space_previous", "macos_space_previous", "low"),
            "abre mission control": ("space_mission_control", "macos_space_mission_control", "low"),
            "estado de spaces": ("space_status", "macos_space_status", "low"),
            "cambia al escritorio 2": (
                "space_switch_desktop_number",
                "macos_space_switch_desktop_number",
                "medium",
            ),
        }
        action, tool, risk = mapping[user_text]
        return RouterResult(
            decision=RouterDecision(
                intent="action",
                domain="macos",
                action=action,
                route="action_ready",
                needs_tool=True,
                risk_level=risk,
                suggested_plugins=["macos"],
                suggested_skills=["macos_spaces"],
                suggested_tools=[tool],
            ),
            model_used="fake",
            raw="{}",
            corrected=True,
        )


class FakeMainModel(MainModel):
    def respond(self, context):
        return "Respuesta MVP"


class FakeLoopMainModel(MainModel):
    def plan_or_act(self, context):
        return ModelAction(
            kind="tool_call",
            tool_call=ToolCall(
                tool_name="browser_search",
                arguments={"query": context.user_message, "target": "youtube"},
                risk_level="low",
                requires_confirmation=False,
            ),
        )

    def finalize_from_tool_result(self, context, tool_call, tool_result):
        return f"Resultado final para {tool_result.data['query']}"

    def respond(self, context):
        return "Respuesta chat"


class FakeSlowFinalizeModel(FakeLoopMainModel):
    def finalize_from_tool_result(self, context, tool_call, tool_result):
        raise AssertionError("finalize_from_tool_result should not be called for browser_search mock")


class FakeClarifyActionModel(MainModel):
    def plan_or_act(self, context):
        return ModelAction(
            kind="clarification_question",
            text="Claro. ¿Qué detalle te falta para continuar?",
        )

    def respond(self, context):
        return "Respuesta chat"


class FakeFinalAnswerModel(MainModel):
    def plan_or_act(self, context):
        return ModelAction(
            kind="final_answer",
            text="Puedo ayudarte con eso sin usar ninguna tool.",
        )

    def respond(self, context):
        return "Respuesta chat"


class FakeRagMainModel(MainModel):
    def respond_with_rag(self, context):
        return f"Respuesta RAG con {context.rag_snippets[0]['source']}"

    def respond(self, context):
        return "Respuesta chat"


class FakeRagRetriever:
    def retrieve(self, query):
        return [
            {
                "source": "agent/knowledge/docs/json.md",
                "text": "Procedimiento JSON local.",
                "score": 0.9,
            }
        ]


class FakeToolFinalizer:
    def __init__(self, result: ToolFinalizerResult | None = None):
        self.result = result or ToolFinalizerResult(
            model_used="fake-tool-finalizer",
            text="Respuesta final natural.",
        )
        self.calls = []

    def finalize(self, *, user_message, tool_call, tool_result):
        self.calls.append(
            {
                "user_message": user_message,
                "tool_call": tool_call,
                "tool_result": tool_result,
            }
        )
        return self.result


class FakeToolPlanner:
    def __init__(self, result: ToolPlannerResult | None = None):
        self.result = result
        self.calls = []

    def plan(self, context):
        self.calls.append(context)
        if self.result is not None:
            return self.result
        tool_name = context.selected_tools[0]["name"]
        arguments = {}
        if tool_name == "browser_search":
            arguments = {"query": context.user_message, "target": "youtube"}
        elif tool_name == "open_app":
            arguments = {"app_name": "Google Chrome"}
        elif tool_name == "macos_space_switch_desktop_number":
            arguments = {"number": 2 if "2" in context.user_message else 3}
        return ToolPlannerResult(
            model_used="fake-tool-planner",
            tool_calls=[
                ToolCall(
                    tool_name=tool_name,
                    arguments=arguments,
                    risk_level=context.selected_tools[0].get("risk_level", "low"),
                    requires_confirmation=False,
                )
            ],
        )


class SequenceExecutor:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def execute(self, tool_call):
        self.calls.append(tool_call)
        if self.results:
            return self.results.pop(0)
        return ToolResult(
            tool_name=tool_call.tool_name,
            success=False,
            error="temporary network timeout",
        )


class CapturingResponseController:
    def __init__(self):
        self.calls = []

    def handle(self, context, session, debug=None):
        self.calls.append(
            {
                "route": context.router_decision.route,
                "pending_workflow": dict(session.pending_workflow or {}),
                "session_state_pending_workflow": context.session_state.get(
                    "pending_workflow"
                ),
            }
        )
        return AgentResponse(
            session_id=session.session_id,
            status="ok",
            text="workflow resumido",
            route=context.router_decision.route,
            debug=debug or {},
        )


class ResumeLoopController:
    def __init__(self, plan_manager: WorkflowPlanManager):
        self.plan_manager = plan_manager
        self.calls = []

    def run(self, workflow_plan, workflow, context, session, existing_plan=None):
        self.calls.append(
            {
                "workflow_plan": workflow_plan,
                "workflow": workflow,
                "context": context,
                "session_id": session.session_id,
                "existing_plan": existing_plan,
            }
        )
        if existing_plan is not None:
            existing_plan.current_step_index = min(1, len(existing_plan.steps))
            existing_plan.status = "running"
            self.plan_manager.save_plan(existing_plan)
            workflow_id = existing_plan.workflow_id
            plan_path = str(
                self.plan_manager._plan_markdown_path(
                    existing_plan.workflow_id, session_id=existing_plan.session_id
                )
            )
            state = FullWorkflowState(data=dict(existing_plan.state))
            workflow_name = existing_plan.workflow_name
        else:
            workflow_id = "wf-resume"
            plan_path = None
            state = FullWorkflowState()
            workflow_name = workflow_plan.workflow_name
        return FullWorkflowResult(
            workflow_name=workflow_name,
            inputs=dict(workflow_plan.inputs),
            state=state,
            workflow_id=workflow_id,
            plan_path=plan_path,
            status="completed",
            phases=[],
            success=True,
            simulation_mode=True,
            current_step_id=(
                existing_plan.steps[existing_plan.current_step_index].id
                if existing_plan is not None and existing_plan.current_step_index < len(existing_plan.steps)
                else None
            ),
        )


class ResumeRegistry:
    def get(self, name):
        return SimpleNamespace(name=name)


class ResumeFullWorkflowRunner:
    def __init__(self, plan_manager: WorkflowPlanManager):
        self.plan_manager = plan_manager
        self.registry = ResumeRegistry()
        self.loop_controller = ResumeLoopController(plan_manager)


def make_gateway(tmp_path: Path, *, router=None, response_controller=None) -> Gateway:
    return Gateway(
        session_manager=SessionManager(store=SQLiteStore(tmp_path / "memory.db")),
        router=router or FakeRouter(),
        response_controller=response_controller
        or ResponseController(main_model=FakeMainModel(), tool_planner=FakeToolPlanner()),
        logger=GatewayLogger(tmp_path / "logs"),
    )


def test_gateway_response_session_and_logs(tmp_path: Path):
    gateway = make_gateway(tmp_path)
    response = gateway.handle_message("hola")
    assert response.status == "ok"
    assert response.session_id
    assert (tmp_path / "logs" / "events.jsonl").exists()
    assert (tmp_path / "logs" / "router.jsonl").exists()
    assert response.tool_calls == []


def test_gateway_asks_clarification_for_ambiguous_youtube(tmp_path: Path):
    gateway = make_gateway(tmp_path)
    response = gateway.handle_message("busca música en YouTube", debug=True)
    assert response.status == "needs_clarification"
    assert response.needs_user_input is True
    assert response.tool_calls == []
    assert "Necesito saber qué quieres buscar." in response.text
    assert "Opciones:" in response.text
    assert "1." in response.text
    assert response.debug["clarification"]["source"] == "clarification_builder"
    assert response.debug["clarification"]["pending_clarification"] == "search_query"


def test_gateway_asks_clarification_for_ambiguous_window_action(tmp_path: Path):
    class WindowClarifyRouter:
        def route(self, user_text: str) -> RouterResult:
            return RouterResult(
                decision=RouterDecision(
                    intent="action",
                    domain="macos",
                    action="window_native_tiling",
                    route="clarification",
                    needs_tool=True,
                    needs_clarification=True,
                    missing_info=["window_action"],
                    suggested_plugins=["macos"],
                    suggested_skills=["macos_windows"],
                    suggested_tools=["window_native_tiling"],
                ),
                model_used="fake",
                raw="{}",
                corrected=True,
            )

    gateway = make_gateway(tmp_path, router=WindowClarifyRouter())
    response = gateway.handle_message("mueve la ventana")

    assert response.status == "needs_clarification"
    assert "acción quieres hacer con la ventana" in response.text
    assert "Opciones:" in response.text


def test_gateway_resolves_single_reference_and_asks_confirmation(tmp_path: Path):
    gateway = make_gateway(tmp_path)
    first = gateway.handle_message("vamos a trabajar con Canva")
    second = gateway.handle_message("ábrela", session_id=first.session_id, debug=True)

    assert second.status == "needs_clarification"
    assert second.route == "clarification"
    assert "Canva" in second.text
    assert "abrir Canva" in second.text
    assert second.debug["chat_clarification_guard"]["reason"] == "resolved_reference_confirmation"
    assert second.debug["chat_clarification_guard"]["resolved_reference"] == "Canva"


def test_gateway_ambiguous_reference_stays_in_clarification(tmp_path: Path):
    gateway = make_gateway(tmp_path)
    first = gateway.handle_message("tenemos dos opciones: Canva y GitHub")
    second = gateway.handle_message("ábrela", session_id=first.session_id, debug=True)

    assert second.status == "needs_clarification"
    assert second.route == "clarification"
    assert "Canva" in second.text
    assert "GitHub" in second.text
    assert second.debug["chat_clarification_guard"]["reason"] == "ambiguous_reference"
    assert "context_resolution" in second.debug


def test_gateway_action_ready_stays_conversational(tmp_path: Path, monkeypatch):
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    gateway = make_gateway(
        tmp_path,
        response_controller=ResponseController(
            main_model=FakeSlowFinalizeModel(),
            tool_planner=FakeToolPlanner(),
            tool_finalizer=FakeToolFinalizer(
                ToolFinalizerResult(
                    model_used="fake-tool-finalizer",
                    text="Respuesta natural final del finalizer.",
                )
            ),
        ),
    )
    response = gateway.handle_message("busca omega en youtube", debug=True)
    assert response.status == "ok"
    assert response.route == "action_ready"
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0]["tool_name"] == "browser_search"
    assert response.text == "Respuesta natural final del finalizer."
    assert (tmp_path / "logs" / "tool_calls.jsonl").exists()
    assert response.debug["tool_result"]["success"] is True
    assert response.debug["tool_finalizer"]["model_used"] == "fake-tool-finalizer"
    assert response.debug["tool_result"]["data"]["target"] == "youtube"
    assert calls[0][0][0] == "/usr/bin/open"
    assert calls[0][0][1].startswith("https://www.youtube.com/results?")


def test_gateway_runs_open_app_through_action_runner_and_keeps_internal_debug(tmp_path: Path):
    class OpenAppRouter:
        def route(self, user_text: str) -> RouterResult:
            return RouterResult(
                decision=RouterDecision(
                    intent="action",
                    domain="macos",
                    action="open_app",
                    route="action_ready",
                    needs_tool=True,
                    suggested_tools=["open_app"],
                ),
                model_used="fake",
                raw="{}",
                corrected=True,
            )

    class OpenAppPlanner:
        def __init__(self):
            self.calls = []

        def plan(self, context):
            self.calls.append(context)
            return ToolPlannerResult(
                model_used="fake",
                tool_calls=[
                    ToolCall(
                        tool_name="open_app",
                        arguments={"app_name": "Google Chrome"},
                        risk_level="low",
                        requires_confirmation=False,
                    )
                ],
            )

    class OpenAppExecutor:
        def __init__(self):
            self.calls = []

        def execute(self, tool_call):
            self.calls.append(tool_call)
            return ToolResult(
                tool_name=tool_call.tool_name,
                success=True,
                data={"app_name": "Google Chrome"},
            )

    class AlwaysSuccessReflectionChecker:
        def __init__(self):
            self.calls = []

        def evaluate(self, tool_call, tool_result, retry_state):
            self.calls.append((tool_call, tool_result, retry_state))
            return ReflectionDecision(
                should_stop=False,
                should_retry=False,
                reason="tool_success",
                user_message="ok",
            )

    response_controller = ResponseController(
        main_model=FakeMainModel(),
        tool_planner=OpenAppPlanner(),
        tool_finalizer=FakeToolFinalizer(
            ToolFinalizerResult(model_used="fake-tool-finalizer", text="Chrome listo.")
        ),
        executor=OpenAppExecutor(),
        reflection_checker=AlwaysSuccessReflectionChecker(),
        full_workflow_selector=FakeWorkflowSelector(FullWorkflowPlan(selected=False)),
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
        full_workflow_finalizer=FakeWorkflowFinalizer(),
        action_macro_selector=ActionMacroSelector(),
        action_macro_executor=ActionMacroExecutor(executor=OpenAppExecutor()),
        action_macro_finalizer=ActionMacroFinalizer(),
    )
    gateway = make_gateway(
        tmp_path,
        router=OpenAppRouter(),
        response_controller=response_controller,
    )

    response = gateway.handle_message("abre Chrome", debug=True)

    assert response.route == "action_ready"
    assert response.tool_calls[0]["tool_name"] == "open_app"
    assert response.debug["action_run"]["tool_call"]["tool_name"] == "open_app"
    assert response.debug["tool_result"]["success"] is True
    assert response_controller.tool_planner.calls
    assert len(response_controller.executor.calls) == 1


def test_gateway_forces_pending_workflow_back_to_action_ready(tmp_path: Path):
    response_controller = CapturingResponseController()
    gateway = make_gateway(
        tmp_path,
        response_controller=response_controller,
    )
    session = gateway.sessions.get_or_create("session-pending")
    session.pending_workflow = {
        "workflow_id": "wf-123",
        "checkpoint_id": "cp-456",
        "current_step_id": "step-789",
    }
    gateway.sessions.save_session_state(session.session_id)

    response = gateway.handle_message(
        "post cuadrado elegante",
        session_id=session.session_id,
    )

    assert response.route == "action_ready"
    assert response_controller.calls[0]["route"] == "action_ready"
    assert response_controller.calls[0]["pending_workflow"]["workflow_id"] == "wf-123"
    assert response_controller.calls[0]["session_state_pending_workflow"]["checkpoint_id"] == "cp-456"


def test_gateway_clears_pending_workflow_on_topic_change(tmp_path: Path):
    response_controller = CapturingResponseController()
    gateway = make_gateway(
        tmp_path,
        response_controller=response_controller,
    )
    session = gateway.sessions.get_or_create("session-cancel")
    session.pending_workflow = {
        "workflow_id": "wf-999",
        "checkpoint_id": "cp-999",
        "current_step_id": "step-999",
    }
    gateway.sessions.save_session_state(session.session_id)

    response = gateway.handle_message(
        "olvídalo, cuéntame un chiste",
        session_id=session.session_id,
    )

    assert response.route == "chat"
    assert response_controller.calls[0]["pending_workflow"] == {}
    assert response_controller.calls[0]["session_state_pending_workflow"] is None


def test_gateway_resolves_pending_workflow_and_continues_from_next_step(tmp_path: Path):
    plan_manager = WorkflowPlanManager(base_dir=tmp_path / "runtime" / "plans")
    plan = plan_manager.create_plan(
        workflow_name="design_canva_post",
        user_goal="Hazme un post en Canva para Bellamar",
        session_id="session-resume",
        steps=[
            WorkflowPlanStep(title="Definir requisitos", kind="ask_user"),
            WorkflowPlanStep(title="Diseñar post", kind="tool"),
        ],
        state={"topic": "Bellamar"},
    )
    checkpoint = plan_manager.create_human_checkpoint(
        plan,
        plan.steps[0].id,
        kind="missing_info",
        question="¿Lo quieres como post cuadrado, historia o flyer? ¿Y prefieres estilo elegante, playero o promocional?",
        options=[],
        required=True,
    )
    plan_manager.save_plan(plan)

    response_controller = ResponseController(
        full_workflow_runner=ResumeFullWorkflowRunner(plan_manager),
        full_workflow_finalizer=SimpleNamespace(
            finalize=lambda *, user_message, workflow_result: SimpleNamespace(
                text="workflow resumido",
                fallback=True,
                error=None,
                model_dump=lambda mode="json": {
                    "text": "workflow resumido",
                    "fallback": True,
                    "error": None,
                },
            )
        ),
    )
    gateway = make_gateway(
        tmp_path,
        response_controller=response_controller,
    )
    session = gateway.sessions.get_or_create("session-resume")
    session.pending_workflow = {
        "workflow_id": plan.workflow_id,
        "checkpoint_id": checkpoint.checkpoint_id,
        "current_step_id": plan.steps[0].id,
    }
    gateway.sessions.save_session_state(session.session_id)

    response = gateway.handle_message(
        "Post cuadrado, estilo Airbnb limpio, usa las fotos recientes",
        session_id=session.session_id,
        debug=True,
    )

    assert response.status == "ok"
    assert response.route == "action_ready"
    loaded = plan_manager.load_plan(plan.workflow_id, session_id="session-resume")
    assert loaded.steps[0].user_answer == "Post cuadrado, estilo Airbnb limpio, usa las fotos recientes"
    assert loaded.steps[0].status == "completed"
    assert loaded.current_step_index == 1
    assert session.pending_workflow is None
    assert response.debug["full_workflow"]["status"] == "completed"


def test_gateway_action_ready_uses_tool_finalizer_and_not_main_model_for_finalization(
    tmp_path: Path, monkeypatch
):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    finalizer = FakeToolFinalizer(
        ToolFinalizerResult(
            model_used="fake-tool-finalizer",
            text="Texto final desde el finalizer.",
        )
    )
    gateway = make_gateway(
        tmp_path,
        response_controller=ResponseController(
            main_model=FakeSlowFinalizeModel(),
            tool_planner=FakeToolPlanner(),
            tool_finalizer=finalizer,
        ),
    )

    response = gateway.handle_message("busca omega en youtube", debug=True)

    assert response.text == "Texto final desde el finalizer."
    assert len(finalizer.calls) == 1
    assert finalizer.calls[0]["user_message"] == "busca omega en youtube"
    assert response.debug["tool_finalizer"]["model_used"] == "fake-tool-finalizer"


def test_gateway_action_ready_supports_window_native_tiling(tmp_path: Path, monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="Safari||Window > Move & Resize > Right",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)
    finalizer = FakeToolFinalizer(
        ToolFinalizerResult(
            model_used="fake-tool-finalizer",
            text="Envié la acción nativa de macOS para colocar la ventana activa a la derecha.",
        )
    )
    gateway = make_gateway(
        tmp_path,
        router=FakeRouter(),
        response_controller=ResponseController(
            main_model=FakeSlowFinalizeModel(),
            tool_planner=FakeToolPlanner(
                ToolPlannerResult(
                    model_used="fake-tool-planner",
                    tool_calls=[
                        ToolCall(
                            tool_name="window_native_tiling",
                            arguments={"action": "right"},
                            risk_level="low",
                            requires_confirmation=False,
                        )
                    ],
                )
            ),
            tool_finalizer=finalizer,
        ),
    )

    response = gateway.handle_message("pon la ventana a la derecha", debug=True)

    assert response.status == "ok"
    assert response.route == "action_ready"
    assert [call["tool_name"] for call in response.tool_calls] == [
        "macos_observe_frontmost",
        "window_native_tiling",
    ]
    assert response.text == "Envié la acción para colocar la ventana activa a la derecha."
    assert response.debug["action_macro"]["workflow_name"] == "tile_active_window"
    assert response.debug["action_macro"]["steps"][1]["tool_result"]["data"]["action"] == "right"


def test_gateway_safety_confirmation_has_no_tool_calls(tmp_path: Path):
    class SafetyRouter:
        def route(self, user_text: str) -> RouterResult:
            return RouterResult(
                decision=RouterDecision(
                    intent="safety",
                    domain="safety",
                    action="confirm_before_action",
                    route="safety_confirmation",
                    risk_level="medium",
                ),
                model_used="fake",
                raw="{}",
                corrected=True,
            )

    gateway = make_gateway(tmp_path, router=SafetyRouter())
    response = gateway.handle_message("borra esos archivos")
    assert response.status == "needs_confirmation"
    assert response.tool_calls == []


def test_gateway_short_reply_advances_pending_clarification(tmp_path: Path, monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    gateway = make_gateway(
        tmp_path,
        response_controller=ResponseController(
            main_model=FakeLoopMainModel(),
            tool_planner=FakeToolPlanner(),
        ),
    )
    first = gateway.handle_message("busca música en YouTube")
    second = gateway.handle_message("omega", session_id=first.session_id)
    session = gateway.sessions.get_or_create(first.session_id)
    assert first.status == "needs_clarification"
    assert second.status == "ok"
    assert second.route == "action_ready"
    assert session.pending_clarification is None
    assert second.tool_calls[0]["tool_name"] == "browser_search"


def test_gateway_topic_change_clears_pending_confirmation(tmp_path: Path):
    class MixedRouter:
        def route(self, user_text: str) -> RouterResult:
            if "borra" in user_text:
                decision = RouterDecision(
                    intent="safety",
                    domain="safety",
                    action="confirm_before_action",
                    route="safety_confirmation",
                    risk_level="medium",
                )
            else:
                decision = RouterDecision(route="chat")
            return RouterResult(
                decision=decision,
                model_used="fake",
                raw="{}",
                corrected=True,
            )

    gateway = make_gateway(tmp_path, router=MixedRouter())
    first = gateway.handle_message("borra esos archivos")
    second = gateway.handle_message(
        "olvídalo, mejor dime un chiste", session_id=first.session_id
    )
    session = gateway.sessions.get_or_create(first.session_id)
    assert first.status == "needs_confirmation"
    assert second.status == "ok"
    assert session.pending_confirmation is None
    assert session.current_route == "chat"


def test_gateway_new_low_risk_action_clears_stale_pending_confirmation(tmp_path: Path):
    class MixedActionRouter:
        def route(self, user_text: str) -> RouterResult:
            if "borra" in user_text:
                decision = RouterDecision(
                    intent="safety",
                    domain="safety",
                    action="confirm_before_action",
                    route="safety_confirmation",
                    risk_level="medium",
                )
            else:
                decision = RouterDecision(
                    intent="action",
                    domain="macos",
                    action="observe_frontmost",
                    route="action_ready",
                    needs_tool=True,
                    risk_level="low",
                    suggested_plugins=["macos"],
                    suggested_skills=["macos_observation"],
                    suggested_tools=["macos_observe_frontmost"],
                )
            return RouterResult(
                decision=decision,
                model_used="fake",
                raw="{}",
                corrected=True,
            )

    gateway = make_gateway(
        tmp_path,
        router=MixedActionRouter(),
        response_controller=ResponseController(
            main_model=FakeMainModel(),
            tool_planner=FakeToolPlanner(),
            executor=SequenceExecutor(
                [
                    ToolResult(
                        tool_name="macos_observe_frontmost",
                        success=True,
                        data={"app_name": "Finder"},
                    )
                ]
            ),
        ),
    )
    first = gateway.handle_message("borra esos archivos")
    second = gateway.handle_message("qué app está abierta", session_id=first.session_id)
    session = gateway.sessions.get_or_create(first.session_id)

    assert first.status == "needs_confirmation"
    assert second.status == "ok"
    assert session.pending_confirmation is None


def test_gateway_action_ready_errors_when_tool_planner_returns_no_tool(tmp_path: Path):
    gateway = make_gateway(
        tmp_path,
        response_controller=ResponseController(
            main_model=FakeClarifyActionModel(),
            tool_planner=FakeToolPlanner(
                ToolPlannerResult(
                    model_used="fake-tool-planner",
                    content="cambiando al escritorio 1",
                    no_tool_reason="no_native_tool_call",
                )
            ),
        ),
    )
    response = gateway.handle_message("busca omega en youtube", debug=True)
    assert response.status == "error"
    assert response.tool_calls == []
    assert "No ejecuté la acción" in response.text
    assert response.debug["tool_planner"]["tool_calls"] == []


def test_gateway_action_ready_does_not_accept_fake_action_content(tmp_path: Path):
    gateway = make_gateway(
        tmp_path,
        response_controller=ResponseController(
            main_model=FakeFinalAnswerModel(),
            tool_planner=FakeToolPlanner(
                ToolPlannerResult(
                    model_used="fake-tool-planner",
                    content="¡Claro! Cambiando al escritorio 1.",
                    no_tool_reason="no_native_tool_call",
                )
            ),
        ),
    )
    response = gateway.handle_message("busca omega en youtube", debug=True)
    assert response.status == "error"
    assert response.tool_calls == []
    assert "Cambiando" not in response.text


def test_gateway_persists_pending_clarification_between_processes(tmp_path: Path):
    store = SQLiteStore(tmp_path / "memory.db")
    first_gateway = Gateway(
        session_manager=SessionManager(store=store),
        router=FakeRouter(),
        response_controller=ResponseController(
            main_model=FakeMainModel(),
            tool_planner=FakeToolPlanner(),
        ),
        logger=GatewayLogger(tmp_path / "first_logs"),
    )
    first = first_gateway.handle_message("busca música en YouTube")

    second_gateway = Gateway(
        session_manager=SessionManager(store=store),
        router=FakeRouter(),
        response_controller=ResponseController(
            main_model=FakeLoopMainModel(),
            tool_planner=FakeToolPlanner(),
        ),
        logger=GatewayLogger(tmp_path / "second_logs"),
    )
    second = second_gateway.handle_message("omega", session_id=first.session_id)
    restored = second_gateway.sessions.get_or_create(first.session_id)

    assert first.status == "needs_clarification"
    assert second.route == "action_ready"
    assert restored.pending_clarification is None
    assert second.tool_calls[0]["tool_name"] == "browser_search"


def test_gateway_records_tool_memory_for_tool_loop(tmp_path: Path, monkeypatch):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    gateway = make_gateway(
        tmp_path,
        response_controller=ResponseController(
            main_model=FakeLoopMainModel(),
            tool_planner=FakeToolPlanner(),
        ),
    )
    response = gateway.handle_message("busca omega en youtube")

    with gateway.sessions.store.connect() as conn:
        row = conn.execute(
            "SELECT * FROM tool_memory WHERE tool_name = 'browser_search'"
        ).fetchone()

    assert response.tool_calls
    assert row["success_count"] == 1
    assert "query=" in row["last_result_summary"].lower()


def test_gateway_rag_lookup_uses_snippets_without_tool_calls(tmp_path: Path):
    class RagRouter:
        def route(self, user_text: str) -> RouterResult:
            return RouterResult(
                decision=RouterDecision(
                    intent="rag",
                    domain="knowledge_base",
                    action="lookup",
                    route="rag_lookup",
                    needs_rag=True,
                ),
                model_used="fake",
                raw="{}",
                corrected=True,
            )

    gateway = Gateway(
        session_manager=SessionManager(store=SQLiteStore(tmp_path / "memory.db")),
        router=RagRouter(),
        pipeline=Pipeline(ContextBuilder(rag_retriever=FakeRagRetriever())),
        response_controller=ResponseController(main_model=FakeRagMainModel()),
        logger=GatewayLogger(tmp_path / "logs"),
    )

    response = gateway.handle_message("según mis notas sobre JSON", debug=True)

    assert response.status == "ok"
    assert response.route == "rag_lookup"
    assert response.tool_calls == []
    assert "Respuesta RAG" in response.text
    assert response.debug["context"]["rag_snippets"][0]["source"].endswith("json.md")


def test_gateway_reflection_retries_transient_error_then_succeeds(tmp_path: Path):
    executor = SequenceExecutor(
        [
            ToolResult(
                tool_name="browser_search",
                success=False,
                error="temporary network timeout",
            ),
            ToolResult(
                tool_name="browser_search",
                success=True,
                data={
                    "query": "omega",
                    "target": "youtube",
                    "url": "https://youtube.test/retry-ok",
                },
            ),
        ]
    )
    gateway = make_gateway(
        tmp_path,
        response_controller=ResponseController(
            main_model=FakeLoopMainModel(),
            tool_planner=FakeToolPlanner(),
            executor=executor,
        ),
    )

    response = gateway.handle_message("busca omega en youtube", debug=True)

    assert response.status == "ok"
    assert len(executor.calls) == 2
    assert response.debug["retry_count"] == 1
    assert response.debug["reflection"][0]["decision"]["should_retry"] is True
    assert response.debug["tool_result"]["success"] is True


def test_gateway_reflection_stops_after_two_retries(tmp_path: Path):
    executor = SequenceExecutor(
        [
            ToolResult(
                tool_name="browser_search",
                success=False,
                error="temporary network timeout",
            ),
            ToolResult(
                tool_name="browser_search",
                success=False,
                error="temporary network timeout",
            ),
            ToolResult(
                tool_name="browser_search",
                success=False,
                error="temporary network timeout",
            ),
        ]
    )
    gateway = make_gateway(
        tmp_path,
        response_controller=ResponseController(
            main_model=FakeLoopMainModel(),
            tool_planner=FakeToolPlanner(),
            executor=executor,
        ),
    )

    response = gateway.handle_message("busca omega en youtube", debug=True)

    assert response.status == "error"
    assert len(executor.calls) == 3
    assert response.debug["retry_count"] == 2
    assert response.debug["final_stop_reason"] == "max_retries_exhausted"
    assert "2 reintentos" in response.text


def test_gateway_reflection_does_not_retry_validation_error(tmp_path: Path):
    executor = SequenceExecutor(
        [
            ToolResult(
                tool_name="browser_search",
                success=False,
                error="browser_search requires a query argument",
                metadata={"blocked": True},
            )
        ]
    )
    gateway = make_gateway(
        tmp_path,
        response_controller=ResponseController(
            main_model=FakeLoopMainModel(),
            tool_planner=FakeToolPlanner(),
            executor=executor,
        ),
    )

    response = gateway.handle_message("busca omega en youtube", debug=True)

    assert response.status == "error"
    assert len(executor.calls) == 1
    assert response.debug["retry_count"] == 0
    assert response.debug["final_stop_reason"] == "blocked_tool"


def test_gateway_reflection_debug_only_when_debug_true(tmp_path: Path):
    executor = SequenceExecutor(
        [
            ToolResult(
                tool_name="browser_search",
                success=False,
                error="temporary network timeout",
            ),
            ToolResult(
                tool_name="browser_search",
                success=True,
                data={
                    "query": "omega",
                    "target": "youtube",
                    "url": "https://youtube.test/no-debug",
                },
            ),
        ]
    )
    gateway = make_gateway(
        tmp_path,
        response_controller=ResponseController(
            main_model=FakeLoopMainModel(),
            tool_planner=FakeToolPlanner(),
            executor=executor,
        ),
    )

    response = gateway.handle_message("busca omega en youtube")

    assert response.status == "ok"
    assert response.debug == {}


def test_gateway_observation_phrases_produce_expected_tool_calls(tmp_path: Path):
    cases = [
        (
            "qué app está abierta",
            ToolResult(
                tool_name="macos_observe_frontmost",
                success=True,
                data={"app_name": "Finder", "window_title": "Home"},
            ),
            "macos_observe_frontmost",
        ),
        (
            "qué ventanas hay abiertas",
            ToolResult(
                tool_name="macos_visible_windows",
                success=True,
                data={"count": 1, "partial": False, "windows": []},
            ),
            "macos_visible_windows",
        ),
        (
            "revisa permisos de mac",
            ToolResult(
                tool_name="macos_permissions_check",
                success=True,
                data={
                    "accessibility": True,
                    "screen_recording": False,
                    "automation": "unknown",
                },
            ),
            "macos_permissions_check",
        ),
        (
            "qué apps puedo abrir",
            ToolResult(
                tool_name="macos_list_apps",
                success=True,
                data={"known_apps": ["Safari"], "installed_apps": ["Safari"]},
            ),
            "macos_list_apps",
        ),
    ]

    for message, result, expected_tool in cases:
        gateway = make_gateway(
            tmp_path,
            router=ObservationRouter(),
            response_controller=ResponseController(
                main_model=FakeFinalAnswerModel(),
                tool_planner=FakeToolPlanner(),
                executor=SequenceExecutor([result]),
            ),
        )
        response = gateway.handle_message(message)

        assert response.status == "ok"
        assert response.tool_calls[0]["tool_name"] == expected_tool


def test_gateway_observe_screen_does_not_call_screenshot(tmp_path: Path):
    class ScreenRouter:
        def route(self, user_text: str) -> RouterResult:
            return RouterResult(
                decision=RouterDecision(
                    intent="refuse",
                    domain="macos",
                    action="screen_observation_unavailable",
                    route="refuse",
                    risk_level="medium",
                ),
                model_used="fake",
                raw="{}",
                corrected=True,
            )

    gateway = make_gateway(tmp_path, router=ScreenRouter())
    response = gateway.handle_message("observa mi pantalla")

    assert response.status == "refused"
    assert response.tool_calls == []


def test_gateway_spaces_phrases_produce_expected_tool_calls(tmp_path: Path):
    cases = [
        (
            "cambia al siguiente escritorio",
            ToolResult(
                tool_name="macos_space_next",
                success=True,
                data={"action": "space_next"},
            ),
            "macos_space_next",
        ),
        (
            "cambia al escritorio anterior",
            ToolResult(
                tool_name="macos_space_previous",
                success=True,
                data={"action": "space_previous"},
            ),
            "macos_space_previous",
        ),
        (
            "abre mission control",
            ToolResult(
                tool_name="macos_space_mission_control",
                success=True,
                data={"action": "space_mission_control"},
            ),
            "macos_space_mission_control",
        ),
        (
            "estado de spaces",
            ToolResult(
                tool_name="macos_space_status",
                success=True,
                data={"current_space": "unknown", "frontmost_app": "Finder"},
            ),
            "macos_space_status",
        ),
        (
            "cambia al escritorio 2",
            ToolResult(
                tool_name="macos_space_switch_desktop_number",
                success=True,
                data={"action": "space_switch_desktop_number", "number": 2},
            ),
            "macos_space_switch_desktop_number",
        ),
    ]

    for message, result, expected_tool in cases:
        gateway = make_gateway(
            tmp_path,
            router=SpacesRouter(),
            response_controller=ResponseController(
                main_model=FakeFinalAnswerModel(),
                tool_planner=FakeToolPlanner(),
                executor=SequenceExecutor([result]),
            ),
        )
        response = gateway.handle_message(message)

        assert response.status == "ok"
        assert response.tool_calls[0]["tool_name"] == expected_tool
        if expected_tool == "macos_space_switch_desktop_number":
            assert response.tool_calls[0]["arguments"] == {"number": 2}
            assert response.tool_calls[0]["requires_confirmation"] is False
