from agent.gateway.message_types import AgentResponse, ContextPackage
from agent.gateway.session_manager import SessionState
from agent.executor.executor import Executor
from agent.execution.action_runner import ActionRunner
from agent.models.main_model import MainModel
from agent.models.action_models import ModelAction
from agent.models.tool_finalizer import ToolFinalizerModel
from agent.models.tool_planner import ToolPlanner
from agent.reflection.checker import ReflectionChecker
from agent.reflection.messages import final_stop_message
from agent.reflection.schemas import ReflectionDecision
from agent.response_action.final_response import build_response
from agent.response_action.state_helpers import clear_pending_for_topic_change
from agent.workflows.finalizer import FullWorkflowFinalizer
from agent.workflows.runner import FullWorkflowRunner
from agent.workflows.selector import FullWorkflowSelector
from agent.workflows.schemas import FullWorkflowPlan
from agent.action_macros.executor import ActionMacroExecutor
from agent.action_macros.finalizer import ActionMacroFinalizer
from agent.action_macros.selector import ActionMacroSelector
from agent.clarification.context_resolver import ContextResolver
from agent.gateway.tool_fallbacks import fallback_browser_search_call, fallback_action_guard_call, fallback_web_result_reference_call
from agent.clarification.chat_guard import ChatSafetyClarificationGuard
from agent.clarification.builder import ClarificationBuilder
from agent.action_guard.intent_guard import ActionIntentGuard
from agent.response_action.state_helpers import is_clear_topic_change


class ResponseController:
    def __init__(
        self,
        main_model: MainModel | None = None,
        tool_planner: ToolPlanner | None = None,
        tool_finalizer: ToolFinalizerModel | None = None,
        executor: Executor | None = None,
        reflection_checker: ReflectionChecker | None = None,
        action_runner: ActionRunner | None = None,
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
        self.clarification_builder = ClarificationBuilder()
        self.chat_clarification_guard = ChatSafetyClarificationGuard()
        self.action_intent_guard = ActionIntentGuard()
        self.context_resolver = ContextResolver()
        self.tool_planner = tool_planner or ToolPlanner()
        self.tool_finalizer = tool_finalizer or ToolFinalizerModel()
        self.executor = executor or Executor()
        self.reflection_checker = reflection_checker or ReflectionChecker()
        self.action_runner = action_runner or ActionRunner(
            executor=self.executor,
            reflection_checker=self.reflection_checker,
            max_retries=max_retries,
        )
        self.full_workflow_selector = full_workflow_selector or FullWorkflowSelector()
        self.full_workflow_runner = full_workflow_runner or FullWorkflowRunner(
            executor=self.executor,
            action_runner=self.action_runner,
        )
        if hasattr(self.full_workflow_runner, "action_runner"):
            self.full_workflow_runner.action_runner = self.action_runner
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
                action_runner=self.action_runner,
                max_retries=max_retries,
            )
        )
        if hasattr(self.action_macro_executor, "action_runner"):
            self.action_macro_executor.action_runner = self.action_runner
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
        preflight = self.handle_chat_preflight(context, session, debug=debug)
        if preflight is not None:
            return preflight

        action_debug = dict(debug or {})
        action_debug.update(self._chat_preflight_debug(context, session))
        text = self.main_model.respond(context)
        return build_response(session.session_id, "ok", text, "chat", debug=action_debug)

    def handle_chat_preflight(
        self,
        context: ContextPackage,
        session: SessionState,
        *,
        debug: dict | None = None,
    ) -> AgentResponse | None:
        """
        Ejecuta los guards de chat sin llamar al MainModel.

        Usado por:
        - handle_chat: antes de MainModel.respond()
        - Gateway.stream_message: antes de MainModel.respond_stream()

        Si retorna None, es chat real y puede responder el modelo.
        """
        clear_pending_for_topic_change(session, context.user_message)

        action_debug = dict(debug or {})
        web_result_fallback = fallback_web_result_reference_call(context)
        if web_result_fallback is not None:
            fallback_tool_call, fallback_reason = web_result_fallback
            action_debug["tool_planner_fallback"] = fallback_reason
            action_debug["tool_planner_fallback_tool_call"] = fallback_tool_call.model_dump(mode="json")
            action_context = context.model_copy(deep=True)
            action_context.router_decision.route = "action_ready"
            action_context.router_decision.intent = "action"
            action_context.router_decision.needs_tool = True
            action_context.router_decision.suggested_tools = ["browser_search"]
            action_debug["web_result_reference_recovered"] = True
            return self.handle_action_ready(action_context, session, debug=action_debug)

        guard = self.chat_clarification_guard.evaluate(context, session)
        action_debug["chat_clarification_guard"] = guard.model_dump(mode="json")
        if guard.context_resolution:
            action_debug["context_resolution"] = guard.context_resolution

        if guard.reason == "recent_tool_result_available":
            text = self._answer_recent_tool_result_status(guard.context_resolution)
            return build_response(
                session.session_id,
                "ok",
                text,
                "chat",
                debug=action_debug,
            )

        if guard.should_clarify:
            clarified_context = context.model_copy(
                update={
                    "router_decision": context.router_decision.model_copy(
                        update={
                            "route": "clarification",
                            "needs_clarification": True,
                            "missing_info": guard.missing_info,
                        }
                    ),
                    "session_state": {
                        **context.session_state,
                        "pending_clarification": guard.pending_clarification,
                    },
                }
            )
            clarification = self.clarification_builder.build(
                clarified_context,
                missing_info_override=guard.missing_info,
                reason_hint=guard.reason,
            )
            session.pending_clarification = clarification.pending_clarification
            action_debug["clarification"] = clarification.model_dump(mode="json")
            return build_response(
                session.session_id,
                "needs_clarification",
                clarification.text,
                "clarification",
                needs_user_input=True,
                debug=action_debug,
            )

        action_intent = self.action_intent_guard.evaluate(context)
        action_debug["action_intent_guard"] = action_intent.model_dump(mode="json")

        if action_intent.suggested_route == "clarification":
            clarified_context = context.model_copy(
                update={
                    "router_decision": context.router_decision.model_copy(
                        update={
                            "route": "clarification",
                            "needs_clarification": True,
                            "missing_info": action_intent.missing_info,
                        }
                    ),
                    "session_state": {
                        **context.session_state,
                        "pending_clarification": self._pending_from_action_intent(action_intent),
                    },
                }
            )
            clarification = self.clarification_builder.build(
                clarified_context,
                missing_info_override=action_intent.missing_info,
                reason_hint=action_intent.reason,
            )
            session.pending_clarification = clarification.pending_clarification
            action_debug["clarification"] = clarification.model_dump(mode="json")
            return build_response(
                session.session_id,
                "needs_clarification",
                clarification.text,
                "clarification",
                needs_user_input=True,
                debug=action_debug,
            )

        if action_intent.action_required and action_intent.suggested_route == "action_ready":
            action_context = context.model_copy(
                update={
                    "router_decision": context.router_decision.model_copy(
                        update={
                            "intent": "action",
                            "domain": "action_guard",
                            "action": action_intent.action_type or "action_required",
                            "route": "action_ready",
                            "needs_tool": True,
                            "needs_clarification": False,
                            "missing_info": [],
                            "suggested_tools": action_intent.suggested_tools,
                            "context_needed": [
                                f"target:{action_intent.target}",
                                f"action_type:{action_intent.action_type}",
                            ],
                        }
                    ),
                    "task_instruction": (
                        context.task_instruction
                        + "\nActionGuard recovered an explicit action from chat route. "
                        + f"Action type: {action_intent.action_type}. "
                        + f"Target: {action_intent.target}. "
                        + "Use the recovered target exactly."
                    ),
                }
            )
            action_debug["action_guard_recovered"] = True
            return self.handle_action_ready(action_context, session, debug=action_debug)

        return None

    def _pending_from_action_intent(self, action_intent) -> str:
        action_type = getattr(action_intent, "action_type", None)
        tools = set(getattr(action_intent, "suggested_tools", []) or [])
        missing = set(getattr(action_intent, "missing_info", []) or [])

        if action_type == "window_move" or "window_native_tiling" in tools:
            return "window_action"
        if action_type == "search" or "web_search" in tools:
            return "search_query"
        if action_type == "open":
            if "open_app" in tools and "browser_search" not in tools:
                return "target_app"
            return "target_url"

        if "window_action" in missing:
            return "window_action"
        if "target_app" in missing:
            return "target_app"
        if "search_query" in missing:
            return "search_query"

        # "target" es demasiado genérico. En una frase tipo "abre la página",
        # el target faltante debe ser URL/sitio, no un pending abstracto.
        if "target" in missing:
            if "open_app" in tools and "browser_search" not in tools:
                return "target_app"
            if "web_search" in tools:
                return "search_query"
            return "target_url"

        return "missing_details"

    def _chat_preflight_debug(
        self,
        context: ContextPackage,
        session: SessionState,
    ) -> dict:
        """
        Debug liviano para chat real.
        No debe producir efectos ni llamar modelos.
        """
        guard = self.chat_clarification_guard.evaluate(context, session)
        data = {
            "chat_clarification_guard": guard.model_dump(mode="json"),
        }
        if guard.context_resolution:
            data["context_resolution"] = guard.context_resolution

        if not guard.should_clarify and guard.reason != "recent_tool_result_available":
            action_intent = self.action_intent_guard.evaluate(context)
            data["action_intent_guard"] = action_intent.model_dump(mode="json")

        return data


    def _answer_recent_tool_result_status(self, context_resolution: dict | None) -> str:
        recent_tool_result = (context_resolution or {}).get("recent_tool_result")
        if not recent_tool_result:
            return "No puedo confirmarlo porque no tengo un resultado reciente de herramienta."

        if not recent_tool_result.get("success", False):
            error = recent_tool_result.get("error")
            if error:
                return f"No. El ultimo resultado de herramienta fallo: {error}"
            return "No. El ultimo resultado de herramienta indica que la accion fallo."

        tool_name = recent_tool_result.get("tool_name")
        data = recent_tool_result.get("data") or {}
        if tool_name == "browser_search":
            url = data.get("url")
            opened = data.get("opened")
            if opened is True and url:
                return f"Si. El ultimo resultado de herramienta indica que se abrio correctamente: {url}"
            if url:
                return f"Si. El ultimo resultado de herramienta devolvio esta pagina: {url}"
            return "Si. El ultimo resultado de herramienta indica que la accion web se completo correctamente."

        if tool_name == "open_app":
            app_name = data.get("app_name")
            if app_name:
                return f"Si. El ultimo resultado de herramienta indica que se abrio {app_name}."
            return "Si. El ultimo resultado de herramienta indica que la aplicacion se abrio."

        if tool_name == "macos_visible_windows":
            count = data.get("count", data.get("visible_windows_count"))
            if count is not None:
                return f"Si. El ultimo resultado de herramienta listo {count} ventana(s) visible(s)."
            return "Si. El ultimo resultado de herramienta listo las ventanas visibles."

        return "Si. El ultimo resultado de herramienta indica que la accion se completo correctamente."

    def handle_clarification(
        self,
        context: ContextPackage,
        session: SessionState,
        *,
        debug: dict | None = None,
    ) -> AgentResponse:
        clarification = self.clarification_builder.build(context)
        session.pending_clarification = clarification.pending_clarification
        action_debug = dict(debug or {})
        action_debug["clarification"] = clarification.model_dump(mode="json")
        return build_response(
            session.session_id,
            "needs_clarification",
            clarification.text,
            context.router_decision.route,
            needs_user_input=True,
            debug=action_debug,
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

        if action_debug.get("web_result_reference_recovered") is True:
            fallback_tool_call_data = action_debug.get("tool_planner_fallback_tool_call")
            if isinstance(fallback_tool_call_data, dict):
                from agent.capabilities.tools.schemas import ToolCall

                fallback_tool_call = ToolCall(**fallback_tool_call_data)
                action = ModelAction(kind="tool_call", tool_call=fallback_tool_call)
                action_debug["model_action"] = action.model_dump(mode="json")
                return self._run_tool_action(
                    context,
                    session,
                    action,
                    action_debug,
                    debug=debug,
                )

        # Si Gateway ya resolvió que una frase como "llévame a ese sitio"
        # se refiere al último resultado web, no vuelvas a pedir aclaración.
        # Construye la tool directamente usando el historial reciente.
        if context.router_decision.action == "open_recent_web_reference":
            recent_reference_call = fallback_web_result_reference_call(context)
            if recent_reference_call is not None:
                fallback_tool_call, fallback_reason = recent_reference_call
                action_debug["tool_planner_fallback"] = fallback_reason
                action_debug["tool_planner_fallback_tool_call"] = fallback_tool_call.model_dump(mode="json")
                action_debug["recent_web_reference_recovered"] = True
                action = ModelAction(kind="tool_call", tool_call=fallback_tool_call)
                action_debug["model_action"] = action.model_dump(mode="json")
                return self._run_tool_action(
                    context,
                    session,
                    action,
                    action_debug,
                    debug=debug,
                )

        resolution = self.context_resolver.resolve(context, session)

        if (
            resolution.has_vague_reference
            and resolution.confidence == "high"
            and resolution.resolved_reference
        ):
            clarification_context = context.model_copy(
                update={
                    "router_decision": context.router_decision.model_copy(
                        update={
                            "route": "clarification",
                            "needs_clarification": True,
                            "missing_info": ["resolved_reference_confirmation"],
                        }
                    ),
                    "session_state": {
                        **context.session_state,
                        "pending_clarification": "resolved_reference_confirmation",
                    },
                }
            )
            clarification = self.clarification_builder.build(
                clarification_context,
                missing_info_override=["resolved_reference_confirmation"],
                reason_hint="resolved_reference_confirmation",
            )
            session.pending_clarification = clarification.pending_clarification
            action_debug = dict(debug or {})
            action_debug["context_resolution"] = resolution.model_dump(mode="json")
            action_debug["clarification"] = clarification.model_dump(mode="json")
            return build_response(
                session.session_id,
                "needs_clarification",
                clarification.text,
                "clarification",
                needs_user_input=True,
                debug=action_debug,
            )
        action_debug["context_resolution"] = resolution.model_dump(mode="json")

        if resolution.reason == "explicit_platform_missing_content":
            clarification_context = context.model_copy(
                update={
                    "router_decision": context.router_decision.model_copy(
                        update={
                            "route": "clarification",
                            "needs_clarification": True,
                            "missing_info": ["target_content"],
                        }
                    ),
                    "session_state": {
                        **context.session_state,
                        "pending_clarification": "target_content",
                    },
                }
            )
            clarification = self.clarification_builder.build(
                clarification_context,
                missing_info_override=["target_content"],
                reason_hint="target_content",
            )
            session.pending_clarification = clarification.pending_clarification
            action_debug["clarification"] = clarification.model_dump(mode="json")
            return build_response(
                session.session_id,
                "needs_clarification",
                clarification.text,
                "clarification",
                needs_user_input=True,
                debug=action_debug,
            )

        if resolution.has_vague_reference and resolution.confidence == "ambiguous":
            clarification_context = context.model_copy(
                update={
                    "router_decision": context.router_decision.model_copy(
                        update={
                            "route": "clarification",
                            "needs_clarification": True,
                            "missing_info": ["ambiguous_reference"],
                        }
                    ),
                    "session_state": {
                        **context.session_state,
                        "pending_clarification": "ambiguous_reference",
                    },
                }
            )
            clarification = self.clarification_builder.build(
                clarification_context,
                missing_info_override=["ambiguous_reference"],
                reason_hint="ambiguous_reference",
            )
            session.pending_clarification = clarification.pending_clarification
            action_debug["clarification"] = clarification.model_dump(mode="json")
            return build_response(
                session.session_id,
                "needs_clarification",
                clarification.text,
                "clarification",
                needs_user_input=True,
                debug=action_debug,
            )

        if resolution.has_status_question and resolution.recent_tool_result is None:
            clarification_context = context.model_copy(
                update={
                    "router_decision": context.router_decision.model_copy(
                        update={
                            "route": "clarification",
                            "needs_clarification": True,
                            "missing_info": ["tool_result"],
                        }
                    ),
                    "session_state": {
                        **context.session_state,
                        "pending_clarification": "tool_result",
                    },
                }
            )
            clarification = self.clarification_builder.build(
                clarification_context,
                missing_info_override=["tool_result"],
                reason_hint=resolution.reason,
            )
            session.pending_clarification = clarification.pending_clarification
            action_debug["clarification"] = clarification.model_dump(mode="json")
            return build_response(
                session.session_id,
                "needs_clarification",
                clarification.text,
                "clarification",
                needs_user_input=True,
                debug=action_debug,
            )

        pending_workflow = self._get_pending_workflow(session)
        if pending_workflow:
            if is_clear_topic_change(context.user_message):
                action_debug["pending_workflow_cancelled"] = dict(pending_workflow)
                self._set_pending_workflow(session, None)
                session.pending_confirmation = None
                session.pending_clarification = None
            else:
                return self._resume_pending_workflow(
                    context,
                    session,
                    action_debug,
                    debug=debug,
                )

        full_workflow_plan = self.full_workflow_selector.select(context)
        full_workflow_debug = full_workflow_plan.model_dump(mode="json")
        action_debug["full_workflow_selector"] = full_workflow_debug
        if full_workflow_plan.selected:
            if full_workflow_plan.status == "needs_clarification":
                clarification_context = context.model_copy(
                    update={
                        "router_decision": context.router_decision.model_copy(
                            update={
                                "route": "clarification",
                                "needs_clarification": True,
                                "missing_info": full_workflow_plan.missing_info,
                            }
                        ),
                        "session_state": {
                            **context.session_state,
                            "pending_clarification": session.pending_clarification,
                        },
                    }
                )
                clarification = self.clarification_builder.build(
                    clarification_context,
                    missing_info_override=full_workflow_plan.missing_info,
                    reason_hint=full_workflow_plan.reason,
                )
                session.pending_clarification = clarification.pending_clarification
                action_debug["clarification"] = clarification.model_dump(mode="json")
                return build_response(
                    session.session_id,
                    "needs_clarification",
                    clarification.text,
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
            fallback = fallback_web_result_reference_call(context)
            if fallback is None:
                fallback = fallback_action_guard_call(action_debug)
            if fallback is None:
                fallback = fallback_browser_search_call(
                    context.user_message,
                    context.selected_tools,
                )
            if fallback is not None:
                fallback_tool_call, fallback_reason = fallback
                action_debug["tool_planner_fallback"] = fallback_reason
                action_debug["tool_planner_fallback_tool_call"] = fallback_tool_call.model_dump(mode="json")
                action = ModelAction(kind="tool_call", tool_call=fallback_tool_call)
                action_debug["model_action"] = action.model_dump(mode="json")
                return self._run_tool_action(context, session, action, action_debug, debug=debug)
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

    def _resume_pending_workflow(
        self,
        context: ContextPackage,
        session: SessionState,
        action_debug: dict,
        *,
        debug: dict | None = None,
    ) -> AgentResponse:
        pending_workflow = dict(self._get_pending_workflow(session) or {})
        workflow_id = pending_workflow.get("workflow_id")
        checkpoint_id = pending_workflow.get("checkpoint_id")
        if not workflow_id:
            self._set_pending_workflow(session, None)
            return build_response(
                session.session_id,
                "error",
                "No pude reanudar el workflow pendiente porque faltaba su identificador.",
                context.router_decision.route,
                debug=action_debug,
            )

        plan_manager = self.full_workflow_runner.plan_manager
        try:
            workflow_plan = plan_manager.load_plan(
                workflow_id,
                session_id=session.session_id,
            )
        except Exception as exc:
            self._set_pending_workflow(session, None)
            session.pending_clarification = None
            action_debug["pending_workflow_error"] = str(exc)
            return build_response(
                session.session_id,
                "error",
                f"No pude recuperar el workflow pendiente: {exc}",
                context.router_decision.route,
                debug=action_debug,
            )

        workflow = self.full_workflow_runner.registry.get(workflow_plan.workflow_name or "")
        if workflow is None:
            self._set_pending_workflow(session, None)
            session.pending_clarification = None
            return build_response(
                session.session_id,
                "error",
                "No encontré el workflow pendiente para continuarlo.",
                context.router_decision.route,
                debug=action_debug,
            )

        if checkpoint_id:
            checkpoint = next(
                (
                    item
                    for item in workflow_plan.checkpoints
                    if item.get("checkpoint_id") == checkpoint_id
                ),
                None,
            )
            if checkpoint is not None:
                approved = None
                active_checkpoint = checkpoint.get("kind")
                if active_checkpoint in {"approval", "safety_confirmation", "visual_validation"}:
                    approved = self._parse_approval_answer(context.user_message)
                plan_manager.resolve_human_checkpoint(
                    workflow_plan,
                    checkpoint_id,
                    user_response=context.user_message,
                    approved=approved,
                    state_updates={
                        "last_user_response": context.user_message,
                        "last_pending_workflow_response": context.user_message,
                    },
                )

        resumed_plan = self.full_workflow_runner.loop_controller.run(
            FullWorkflowPlan(
                selected=True,
                workflow_name=workflow_plan.workflow_name,
                inputs=dict(workflow_plan.state),
                status="selected",
                simulation_mode=True,
                missing_tools=[],
            ),
            workflow,
            context,
            session,
            existing_plan=workflow_plan,
        )
        action_debug["full_workflow"] = resumed_plan.model_dump(mode="json")
        action_debug["workflow"] = resumed_plan.model_dump(mode="json")
        return self._build_full_workflow_response(
            context,
            session,
            resumed_plan,
            action_debug,
        )

    def _parse_approval_answer(self, user_text: str) -> bool | None:
        normalized = " ".join(user_text.strip().lower().split())
        if not normalized:
            return None
        if any(token in normalized for token in ("si", "sí", "aprueba", "approve", "hazlo", "ok", "adelante")):
            return True
        if any(token in normalized for token in ("no", "rechaza", "reject", "cancel", "cancela", "parar")):
            return False
        return None

    def _build_full_workflow_response(
        self,
        context: ContextPackage,
        session: SessionState,
        full_workflow_result,
        action_debug: dict,
    ) -> AgentResponse:
        full_workflow_result_debug = full_workflow_result.model_dump(mode="json")
        action_debug["full_workflow"] = full_workflow_result_debug
        action_debug["workflow"] = full_workflow_result_debug

        checkpoint = full_workflow_result.state.get_value("active_checkpoint") or {}
        if full_workflow_result.status in {"waiting_user_input", "waiting_approval"}:
            current_phase = (
                full_workflow_result.phases[-1] if full_workflow_result.phases else None
            )
            checkpoint_kind = checkpoint.get("kind")
            is_approval_pause = (
                full_workflow_result.needs_approval
                or full_workflow_result.status == "waiting_approval"
                or checkpoint_kind in {"approval", "safety_confirmation", "visual_validation"}
            )
            is_user_input_pause = (
                full_workflow_result.needs_user_input
                or full_workflow_result.status == "waiting_user_input"
                or checkpoint_kind in {"missing_info", "preference", "correction_request"}
            )
            question = (
                full_workflow_result.question
                or checkpoint.get("question")
                or (current_phase.question if current_phase else None)
            )
            approval_request = (
                full_workflow_result.approval_request
                or checkpoint.get("approval_request")
                or (current_phase.approval_request if current_phase else None)
            )
            text = (
                question
                or approval_request
                or (current_phase.summary if current_phase else None)
                or "Necesito una respuesta para continuar."
            )
            pending_workflow = {
                "workflow_id": full_workflow_result.workflow_id
                or checkpoint.get("workflow_id")
                or full_workflow_result.state.get_value("workflow_id"),
                "checkpoint_id": full_workflow_result.checkpoint_id
                or checkpoint.get("checkpoint_id"),
                "current_step_id": full_workflow_result.current_step_id
                or checkpoint.get("step_id")
                or full_workflow_result.current_step_id,
            }
            self._set_pending_workflow(
                session,
                {key: value for key, value in pending_workflow.items() if value is not None},
            )
            pending_workflow_state = self._get_pending_workflow(session) or {}
            if is_approval_pause:
                session.pending_confirmation = {
                    "workflow_id": pending_workflow_state.get("workflow_id"),
                    "checkpoint_id": pending_workflow_state.get("checkpoint_id"),
                    "current_step_id": pending_workflow_state.get("current_step_id"),
                    "question": text,
                }
            else:
                session.pending_confirmation = None
            session.pending_clarification = None
            response_status = (
                "needs_confirmation"
                if is_approval_pause
                else "needs_clarification"
                if is_user_input_pause
                else "waiting_user_input"
            )
            return build_response(
                session.session_id,
                response_status,
                text,
                context.router_decision.route,
                needs_user_input=True,
                debug=action_debug,
            )

        finalizer_result = self.full_workflow_finalizer.finalize(
            user_message=context.user_message,
            workflow_result=full_workflow_result,
        )
        finalizer_debug = finalizer_result.model_dump(mode="json")
        action_debug["full_workflow_finalizer"] = finalizer_debug
        action_debug["workflow_finalizer"] = finalizer_debug
        self._set_pending_workflow(session, None)
        session.pending_confirmation = None
        return build_response(
            session.session_id,
            "ok" if full_workflow_result.status != "failed" else "error",
            finalizer_result.text,
            context.router_decision.route,
            debug=action_debug,
        )

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
            try:
                full_workflow_result = self.full_workflow_runner.run(
                    full_workflow_plan,
                    context,
                    session,
                )
            except TypeError:
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
        return self._build_full_workflow_response(
            context,
            session,
            full_workflow_result,
            action_debug,
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

        action_run = self.action_runner.run_tool_call(tool_call)
        tool_result = action_run.final_tool_result
        action_debug["action_run"] = action_run.model_dump(mode="json")
        action_debug["reflection_trace"] = action_run.reflection_trace
        action_debug["reflection"] = action_run.reflection_trace
        action_debug["retry_count"] = action_run.retry_count
        if action_run.stop_reason is not None:
            action_debug["stop_reason"] = action_run.stop_reason
        if action_run.reflection_trace:
            action_debug["retry_reason"] = action_run.reflection_trace[-1]["decision"][
                "reason"
            ]
        action_debug["tool_result"] = tool_result.model_dump(mode="json")

        if action_run.stopped:
            stop_decision = ReflectionDecision(
                **action_run.attempts[-1].reflection_decision
            )
            action_debug["final_stop_reason"] = action_run.stop_reason
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

    def _get_pending_workflow(self, session: SessionState) -> dict[str, object] | None:
        pending_workflow = getattr(session, "pending_workflow", None)
        if pending_workflow is None:
            return None
        return dict(pending_workflow)

    def _set_pending_workflow(
        self,
        session: SessionState,
        pending_workflow: dict[str, object] | None,
    ) -> None:
        setattr(session, "pending_workflow", pending_workflow)

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
