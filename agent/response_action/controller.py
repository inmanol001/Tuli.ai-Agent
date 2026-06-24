from agent.gateway.message_types import AgentResponse, ContextPackage
from agent.gateway.session_manager import SessionState
from agent.executor.executor import Executor
from agent.executor.results import ToolResult
from agent.models.main_model import MainModel
from agent.models.action_models import ModelAction
from agent.models.tool_finalizer import ToolFinalizerModel
from agent.models.tool_planner import ToolPlanner
from agent.reflection.checker import ReflectionChecker
from agent.reflection.messages import final_stop_message
from agent.reflection.retry_policy import make_retry_state
from agent.response_action.final_response import build_response
from agent.response_action.state_helpers import clear_pending_for_topic_change
from agent.workflows.finalizer import FullWorkflowFinalizer
from agent.workflows.runner import FullWorkflowRunner
from agent.workflows.selector import FullWorkflowSelector
from agent.action_macros.executor import ActionMacroExecutor
from agent.action_macros.finalizer import ActionMacroFinalizer
from agent.action_macros.selector import ActionMacroSelector


class ResponseController:
    def __init__(
        self,
        main_model: MainModel | None = None,
        tool_planner: ToolPlanner | None = None,
        tool_finalizer: ToolFinalizerModel | None = None,
        executor: Executor | None = None,
        reflection_checker: ReflectionChecker | None = None,
        full_workflow_selector: FullWorkflowSelector | None = None,
        full_workflow_runner: FullWorkflowRunner | None = None,
        full_workflow_finalizer: FullWorkflowFinalizer | None = None,
        action_macro_selector: ActionMacroSelector | None = None,
        action_macro_executor: ActionMacroExecutor | None = None,
        action_macro_finalizer: ActionMacroFinalizer | None = None,
        workflow_selector=None,
        workflow_executor=None,
        workflow_finalizer=None,
        max_retries: int = 2,
    ) -> None:
        self.main_model = main_model or MainModel()
        self.tool_planner = tool_planner or ToolPlanner()
        self.tool_finalizer = tool_finalizer or ToolFinalizerModel()
        self.executor = executor or Executor()
        self.reflection_checker = reflection_checker or ReflectionChecker()
        self.full_workflow_selector = full_workflow_selector or FullWorkflowSelector()
        self.full_workflow_runner = full_workflow_runner or FullWorkflowRunner(
            executor=self.executor,
        )
        self.full_workflow_finalizer = (
            full_workflow_finalizer or FullWorkflowFinalizer()
        )
        self.action_macro_selector = (
            action_macro_selector
            or workflow_selector
            or ActionMacroSelector()
        )
        self.action_macro_executor = (
            action_macro_executor
            or workflow_executor
            or ActionMacroExecutor(
                executor=self.executor,
                reflection_checker=self.reflection_checker,
                max_retries=max_retries,
            )
        )
        self.action_macro_finalizer = (
            action_macro_finalizer
            or workflow_finalizer
            or ActionMacroFinalizer()
        )
        self.workflow_selector = self.action_macro_selector
        self.workflow_executor = self.action_macro_executor
        self.workflow_finalizer = self.action_macro_finalizer
        self.max_retries = max_retries

    def handle(
        self,
        context: ContextPackage,
        session: SessionState,
        *,
        debug: dict | None = None,
    ) -> AgentResponse:
        route = context.router_decision.route
        if route == "clarification":
            return self.handle_clarification(context, session, debug=debug)
        if route == "memory_lookup":
            return self.handle_memory_lookup(context, session, debug=debug)
        if route == "rag_lookup":
            return self.handle_rag_lookup(context, session, debug=debug)
        if route == "safety_confirmation":
            return self.handle_safety_confirmation(context, session, debug=debug)
        if route == "action_ready":
            return self.handle_action_ready(context, session, debug=debug)
        if route == "refuse":
            return self.handle_refuse(context, session, debug=debug)

        return self.handle_chat(context, session, debug=debug)

    def handle_chat(
        self,
        context: ContextPackage,
        session: SessionState,
        *,
        debug: dict | None = None,
    ) -> AgentResponse:
        clear_pending_for_topic_change(session, context.user_message)
        text = self.main_model.respond(context)
        return build_response(session.session_id, "ok", text, "chat", debug=debug)

    def handle_clarification(
        self,
        context: ContextPackage,
        session: SessionState,
        *,
        debug: dict | None = None,
    ) -> AgentResponse:
        session.pending_clarification = ",".join(
            context.router_decision.missing_info or ["missing_details"]
        )
        if context.router_decision.action == "window_native_tiling":
            text = (
                "Claro. ¿Qué acción quieres hacer con la ventana activa: izquierda, derecha, "
                "centrar, llenar, esquina o volver al tamaño anterior?"
            )
        elif context.router_decision.domain == "browser":
            text = "Claro. ¿Qué tema o destino web quieres que abra o busque?"
        else:
            text = "Claro. ¿Qué detalle te falta para continuar?"
        return build_response(
            session.session_id,
            "needs_clarification",
            text,
            context.router_decision.route,
            needs_user_input=True,
            debug=debug,
        )

    def handle_action_ready(
        self,
        context: ContextPackage,
        session: SessionState,
        *,
        debug: dict | None = None,
    ) -> AgentResponse:
        session.pending_clarification = None
        action_debug = dict(debug or {})
        full_workflow_plan = self.full_workflow_selector.select(context)
        full_workflow_debug = full_workflow_plan.model_dump(mode="json")
        action_debug["full_workflow_selector"] = full_workflow_debug
        if full_workflow_plan.selected:
            if full_workflow_plan.status == "needs_clarification":
                clarification_text = "Claro. ¿Sobre qué tema quieres que prepare el post?"
                if full_workflow_plan.reason == "missing_workflow_target":
                    clarification_text = (
                        "Claro. ¿Quieres que prepare el post como texto solamente "
                        "o quieres crearlo como diseño en Canva?"
                    )
                elif full_workflow_plan.reason == "missing_topic":
                    clarification_text = (
                        "Claro. ¿Sobre qué tema quieres que prepare el post?"
                    )
                return build_response(
                    session.session_id,
                    "needs_clarification",
                    clarification_text,
                    context.router_decision.route,
                    needs_user_input=True,
                    debug=action_debug,
                )
            return self._run_full_workflow(
                context,
                session,
                full_workflow_plan,
                action_debug,
                debug=debug,
            )

        macro_plan = self.action_macro_selector.select(context)
        macro_debug = macro_plan.model_dump(mode="json")
        action_debug["action_macro_selector"] = macro_debug
        action_debug["workflow_selector"] = macro_debug
        if macro_plan.selected:
            return self._run_action_macro(
                context,
                session,
                macro_plan,
                action_debug,
                debug=debug,
            )
        planner_result = self.tool_planner.plan(context)
        action_debug["tool_planner"] = planner_result.model_dump(mode="json")

        if planner_result.error:
            return build_response(
                session.session_id,
                "error",
                f"No ejecuté la acción porque el modelo de herramientas falló: {planner_result.error}",
                context.router_decision.route,
                debug=action_debug,
            )

        if not planner_result.tool_calls:
            return build_response(
                session.session_id,
                "error",
                "No ejecuté la acción porque el modelo de herramientas no generó una llamada válida.",
                context.router_decision.route,
                debug=action_debug,
            )

        action = ModelAction(kind="tool_call", tool_call=planner_result.tool_calls[0])
        action_debug["model_action"] = action.model_dump(mode="json")
        return self._run_tool_action(context, session, action, action_debug, debug=debug)

    def _run_full_workflow(
        self,
        context: ContextPackage,
        session: SessionState,
        full_workflow_plan,
        action_debug: dict,
        *,
        debug: dict | None = None,
    ) -> AgentResponse:
        try:
            full_workflow_result = self.full_workflow_runner.run(full_workflow_plan)
        except Exception as exc:
            action_debug["full_workflow_error"] = str(exc)
            return build_response(
                session.session_id,
                "error",
                f"No ejecuté el full workflow porque falló el runner: {exc}",
                context.router_decision.route,
                debug=action_debug,
            )

        full_workflow_result_debug = full_workflow_result.model_dump(mode="json")
        action_debug["full_workflow"] = full_workflow_result_debug
        action_debug["workflow"] = full_workflow_result_debug

        finalizer_result = self.full_workflow_finalizer.finalize(
            user_message=context.user_message,
            workflow_result=full_workflow_result,
        )
        finalizer_debug = finalizer_result.model_dump(mode="json")
        action_debug["full_workflow_finalizer"] = finalizer_debug
        action_debug["workflow_finalizer"] = finalizer_debug

        return build_response(
            session.session_id,
            "ok" if full_workflow_result.status != "failed" else "error",
            finalizer_result.text,
            context.router_decision.route,
            debug=action_debug,
        )

    def _run_action_macro(
        self,
        context: ContextPackage,
        session: SessionState,
        macro_plan,
        action_debug: dict,
        *,
        debug: dict | None = None,
    ) -> AgentResponse:
        try:
            macro_result = self.action_macro_executor.run(macro_plan)
        except Exception as exc:
            action_debug["action_macro_error"] = str(exc)
            return build_response(
                session.session_id,
                "error",
                f"No ejecuté la action macro porque falló el ejecutor: {exc}",
                context.router_decision.route,
                debug=action_debug,
            )

        macro_result_debug = macro_result.model_dump(mode="json")
        action_debug["action_macro"] = macro_result_debug
        action_debug["workflow"] = macro_result_debug
        finalizer_result = self.action_macro_finalizer.finalize(
            user_message=context.user_message,
            workflow_result=macro_result,
        )
        finalizer_debug = finalizer_result.model_dump(mode="json")
        action_debug["action_macro_finalizer"] = finalizer_debug
        action_debug["workflow_finalizer"] = finalizer_debug
        tool_calls = [
            step.tool_call.model_dump(mode="json")
            for step in macro_result.steps
        ]
        return build_response(
            session.session_id,
            "ok" if macro_result.success else "error",
            finalizer_result.text,
            context.router_decision.route,
            tool_calls=tool_calls,
            debug=action_debug,
        )

    def _run_tool_action(
        self,
        context: ContextPackage,
        session: SessionState,
        action: ModelAction,
        action_debug: dict,
        *,
        debug: dict | None = None,
    ) -> AgentResponse:
        tool_call = action.tool_call
        if tool_call is None:
            return build_response(
                session.session_id,
                "error",
                "El modelo no devolvio un tool_call valido para action_ready.",
                context.router_decision.route,
                debug=action_debug,
            )

        tool_result, reflection_trace, stop_decision = self._execute_tool_call_with_reflection(
            tool_call
        )
        if debug:
            action_debug["reflection"] = reflection_trace
            action_debug["retry_count"] = max(0, len(reflection_trace) - 1)
            if reflection_trace:
                action_debug["retry_reason"] = reflection_trace[-1]["decision"]["reason"]
        action_debug["tool_result"] = tool_result.model_dump(mode="json")

        if stop_decision is not None:
            if debug:
                action_debug["final_stop_reason"] = stop_decision.reason
            return build_response(
                session.session_id,
                "error",
                final_stop_message(stop_decision),
                context.router_decision.route,
                tool_calls=[tool_call.model_dump(mode="json")],
                debug=action_debug,
            )

        finalizer_result = self.tool_finalizer.finalize(
            user_message=context.user_message,
            tool_call=tool_call,
            tool_result=tool_result,
        )
        action_debug["tool_finalizer"] = finalizer_result.model_dump(mode="json")
        final_text = finalizer_result.text
        return build_response(
            session.session_id,
            "ok" if tool_result.success else "error",
            final_text or "No hubo respuesta final tras ejecutar la tool.",
            context.router_decision.route,
            tool_calls=[tool_call.model_dump(mode="json")],
            debug=action_debug,
        )

    def _execute_tool_call_with_reflection(self, tool_call):
        previous_errors: list[str] = []
        reflection_trace = []
        for attempt_number in range(self.max_retries + 1):
            retry_state = make_retry_state(
                attempt_number,
                max_retries=self.max_retries,
                previous_errors=previous_errors,
            )
            tool_result = self.executor.execute(tool_call)
            decision = self.reflection_checker.evaluate(
                tool_call, tool_result, retry_state
            )
            reflection_trace.append(
                {
                    "attempt_number": attempt_number,
                    "execution_number": attempt_number + 1,
                    "tool_result": tool_result.model_dump(mode="json"),
                    "decision": decision.model_dump(mode="json"),
                }
            )
            if tool_result.error:
                previous_errors.append(tool_result.error)
            if decision.should_retry:
                continue
            if decision.should_stop:
                return tool_result, reflection_trace, decision
            return tool_result, reflection_trace, None
        return tool_result, reflection_trace, decision

    def handle_memory_lookup(
        self,
        context: ContextPackage,
        session: SessionState,
        *,
        debug: dict | None = None,
    ) -> AgentResponse:
        return build_response(
            session.session_id,
            "ok",
            "Ya tengo memoria persistente basica para sesiones e historial corto. La busqueda en memoria larga/RAG todavia no esta activa.",
            context.router_decision.route,
            debug=debug,
        )

    def handle_rag_lookup(
        self,
        context: ContextPackage,
        session: SessionState,
        *,
        debug: dict | None = None,
    ) -> AgentResponse:
        if not context.rag_snippets:
            return build_response(
                session.session_id,
                "ok",
                "No encontre informacion suficiente en la knowledge base local.",
                context.router_decision.route,
                debug=debug,
            )
        text = self.main_model.respond_with_rag(context)
        return build_response(
            session.session_id,
            "ok",
            text,
            context.router_decision.route,
            debug=debug,
        )

    def handle_safety_confirmation(
        self,
        context: ContextPackage,
        session: SessionState,
        *,
        debug: dict | None = None,
    ) -> AgentResponse:
        session.pending_confirmation = {"message": context.user_message}
        return build_response(
            session.session_id,
            "needs_confirmation",
            "Esa accion requiere confirmacion y no se ejecutara en la fase actual.",
            context.router_decision.route,
            needs_user_input=True,
            debug=debug,
        )

    def handle_refuse(
        self,
        context: ContextPackage,
        session: SessionState,
        *,
        debug: dict | None = None,
    ) -> AgentResponse:
        session.pending_clarification = None
        session.pending_confirmation = None
        return build_response(
            session.session_id,
            "refused",
            "No puedo ayudar con esa accion.",
            context.router_decision.route,
            debug=debug,
        )
