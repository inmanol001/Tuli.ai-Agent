import json
from collections.abc import Iterator
from typing import Any

from agent.gateway.gateway_logger import GatewayLogger
from agent.gateway.message_types import AgentResponse, ContextPackage
from agent.gateway.pipeline import Pipeline
from agent.gateway.session_manager import SessionManager
from agent.behavior.loader import load_soul
from agent.logging.dev_event_builder import build_dev_event
from agent.memory.error_memory import record_error_memory
from agent.conversation_state.state import update_conversation_state_from_response, normalize_conversation_state
from agent.memory.preferences import capture_explicit_preferences
from agent.memory.tool_memory import record_tool_memory
from agent.response_action.controller import ResponseController
from agent.response_action.early_ack import build_early_ack
from agent.response_action.state_helpers import (
    clear_stale_pending_confirmation_for_action,
    resolve_pending_clarification,
    clear_pending_workflow_for_topic_change,
)
from agent.router.xlam_router import XlamRouter
from agent.memory.memory_writer import record_learning_from_completed_turn
from agent.memory.user_memory import (
    handle_explicit_memory_request,
    detect_user_confirmation,
    load_user_memories,
    load_relevant_user_memories,
    confirm_user_memory,
)


class Gateway:
    def __init__(
        self,
        session_manager: SessionManager | None = None,
        router: XlamRouter | None = None,
        pipeline: Pipeline | None = None,
        response_controller: ResponseController | None = None,
        logger: GatewayLogger | None = None,
    ) -> None:
        self.sessions = session_manager or SessionManager()
        self.router = router or XlamRouter()
        self.pipeline = pipeline or Pipeline(
            learning_memory_store=self.sessions.store
        )
        self.response_controller = response_controller or ResponseController()
        self.logger = logger or GatewayLogger()

    def handle_message(
        self, user_text: str, session_id: str | None = None, debug: bool = False
    ) -> AgentResponse:
        session = self.sessions.get_or_create(session_id)

        explicit_memory = handle_explicit_memory_request(
            self.sessions.store,
            user_text,
        )
        if explicit_memory is not None:
            response = AgentResponse(
                session_id=session.session_id,
                status="ok",
                text="Listo, lo recordaré.",
                route="memory_lookup",
                debug={
                    "explicit_memory": explicit_memory,
                    "memory_write": True,
                },
            )
            self._record_completed_turn(user_text, session, response, None)
            return self._public_response(response, debug)

        session, effective_decision, context, debug_payload, dev_debug_payload = self._prepare_turn(
            user_text, session.session_id, debug
        )

        try:
            response = self.response_controller.handle(
                context, session, debug=dev_debug_payload
            )
            self._record_completed_turn(user_text, session, response, dev_debug_payload)
            return self._public_response(response, debug)
        except Exception as exc:
            self._record_error(session.session_id, str(exc), effective_decision.route, dev_debug_payload)
            return AgentResponse(
                session_id=session.session_id,
                status="error",
                text=f"Error en la fase actual: {exc}",
                route=effective_decision.route,
            )

    def stream_message(
        self, user_text: str, session_id: str | None = None, debug: bool = False
    ) -> Iterator[dict[str, Any]]:
        session = self.sessions.get_or_create(session_id)

        explicit_memory = handle_explicit_memory_request(
            self.sessions.store,
            user_text,
        )
        if explicit_memory is not None:
            response = AgentResponse(
                session_id=session.session_id,
                status="ok",
                text="Listo, lo recordaré.",
                route="memory_lookup",
                debug={
                    "explicit_memory": explicit_memory,
                    "memory_write": True,
                },
            )
            self._record_completed_turn(user_text, session, response, None)
            public_response = self._public_response(response, debug)
            yield {"type": "token", "text": public_response.text}
            yield {"type": "response", "response": public_response}
            if debug:
                yield {"type": "debug", "debug": public_response.debug}
            return

        session, effective_decision, context, debug_payload, dev_debug_payload = self._prepare_turn(
            user_text, session.session_id, debug
        )
        if effective_decision.route != "chat":
            try:
                if context.router_decision.route == "action_ready":
                    ack_text = build_early_ack(
                        context.router_decision.suggested_tools or []
                    )
                    self.logger.write(
                        "dev_events",
                        {
                            "type": "early_ack",
                            "session_id": session.session_id,
                            "text": ack_text,
                            "route": context.router_decision.route,
                            "suggested_tools": context.router_decision.suggested_tools,
                        },
                    )
                    yield {
                        "type": "early_ack",
                        "text": ack_text,
                        "route": context.router_decision.route,
                        "suggested_tools": context.router_decision.suggested_tools,
                    }
                response = self.response_controller.handle(
                    context, session, debug=dev_debug_payload
                )
                self._record_completed_turn(user_text, session, response, dev_debug_payload)
                response = self._public_response(response, debug)
                yield {"type": "final", "response": response}
                if debug:
                    yield {"type": "debug", "debug": response.debug}
            except Exception as exc:
                self._record_error(session.session_id, str(exc), effective_decision.route, dev_debug_payload)
                response = AgentResponse(
                    session_id=session.session_id,
                    status="error",
                    text=f"Error en la fase actual: {exc}",
                    route=effective_decision.route,
                    debug=debug_payload if debug else {},
                )
                yield {"type": "error", "response": response}
                if debug:
                    yield {"type": "debug", "debug": response.debug}
            return

        try:
            preflight_response = self.response_controller.handle_chat_preflight(
                context,
                session,
                debug=dev_debug_payload,
            )

            if preflight_response is not None:
                self._record_completed_turn(user_text, session, preflight_response, dev_debug_payload)
                public_response = self._public_response(preflight_response, debug)
                yield {"type": "final", "response": public_response}
                if debug:
                    yield {"type": "debug", "debug": public_response.debug}
                return

            full_text = ""
            for token in self.response_controller.main_model.respond_stream(context):
                if not token:
                    continue
                full_text += token
                yield {"type": "token", "text": token}

            response = AgentResponse(
                session_id=session.session_id,
                status="ok",
                text=full_text,
                route="chat",
                debug={
                    **debug_payload,
                    **self.response_controller._chat_preflight_debug(context, session),
                },
            )
            self._record_completed_turn(user_text, session, response, dev_debug_payload)
            response = self._public_response(response, debug)
            yield {"type": "final", "response": response}
            if debug:
                yield {"type": "debug", "debug": response.debug}
        except Exception as exc:
            self._record_error(session.session_id, str(exc), "chat", dev_debug_payload)
            response = AgentResponse(
                session_id=session.session_id,
                status="error",
                text=f"Error durante streaming: {exc}",
                route="chat",
                debug=debug_payload if debug else {},
            )
            yield {"type": "error", "response": response}
            if debug:
                yield {"type": "debug", "debug": response.debug}

    def _is_user_memory_question(self, text: str) -> bool:
        compact = " ".join((text or "").lower().strip().split())
        if not compact:
            return False

        memory_patterns = (
            "cual es mi ",
            "cuál es mi ",
            "que es mi ",
            "qué es mi ",
            "que dia ",
            "qué dia ",
            "qué día ",
            "cuando cumplo",
            "cuándo cumplo",
            "mi cumpleaños",
            "mi color favorito",
            "como prefiero",
            "cómo prefiero",
            "que sabes de mi",
            "qué sabes de mí",
        )
        return any(pattern in compact for pattern in memory_patterns)

    def _force_chat_for_user_memory_question(self, user_text: str, decision):
        if not self._is_user_memory_question(user_text):
            return decision

        memories = load_relevant_user_memories(
            self.sessions.store,
            user_message=user_text,
            limit=8,
        )
        if not memories:
            return decision

        forced = decision.model_copy(deep=True)
        forced.intent = "chat"
        forced.domain = "memory"
        forced.action = "answer_user_memory_question"
        forced.route = "chat"
        forced.needs_tool = False
        forced.needs_clarification = False
        forced.missing_info = []
        forced.suggested_plugins = []
        forced.suggested_skills = []
        forced.suggested_tools = []
        return forced

    def _prepare_turn(
        self, user_text: str, session_id: str | None, debug: bool
    ) -> tuple[Any, Any, ContextPackage, dict, dict]:
        session = self.sessions.get_or_create(session_id)

        session.previous_route = session.current_route

        router_result = self.router.route(user_text)
        effective_decision = resolve_pending_clarification(
            session, user_text, router_result.decision
        )
        clear_stale_pending_confirmation_for_action(session, user_text, effective_decision)
        effective_decision = self._force_chat_for_user_memory_question(user_text, effective_decision)
        if session.pending_workflow:
            clear_pending_workflow_for_topic_change(session, user_text)
            if session.pending_workflow is not None:
                effective_decision = effective_decision.model_copy(deep=True)
                effective_decision.intent = "action"
                effective_decision.domain = "workflow"
                effective_decision.action = "resume_pending_workflow"
                effective_decision.route = "action_ready"
                effective_decision.needs_tool = False
                effective_decision.needs_clarification = False
                effective_decision.missing_info = []
            else:
                session.pending_confirmation = None
        session.current_route = effective_decision.route
        self.logger.write(
            "router",
            {
                "session_id": session.session_id,
                "model_used": router_result.model_used,
                "corrected": router_result.corrected,
                "decision": effective_decision.model_dump(mode="json"),
                "error": router_result.error,
            },
        )

        context = self.pipeline.build_context(user_text, effective_decision, session)
        self.logger.write(
            "context_builder",
            {"session_id": session.session_id, "context": context.model_dump(mode="json")},
        )
        soul = load_soul()
        dev_debug_payload = {
            "router": router_result.model_dump(mode="json"),
            "context": context.model_dump(mode="json"),
            "soul": {
                "loaded": soul.loaded,
                "source": soul.source_path,
                "fallback_used": soul.fallback_used,
                "error": soul.error,
                "chars": len(soul.content),
            },
        }
        debug_payload = {}
        if debug:
            debug_payload = dev_debug_payload
        return session, effective_decision, context, debug_payload, dev_debug_payload

    def _confirm_recent_user_memory_if_applicable(
        self, user_text: str, session, response: AgentResponse
    ) -> dict | None:
        try:
            if not detect_user_confirmation(user_text):
                return None

            previous_assistant = None
            for turn in reversed(session.history):
                if turn.role == "assistant" and turn.content:
                    previous_assistant = turn.content
                    break

            if not previous_assistant:
                return None

            assistant_text = previous_assistant.lower()
            memories = load_user_memories(self.sessions.store, status=None, limit=50)

            for memory in memories:
                value = str(memory.get("value") or "").strip()
                key = str(memory.get("key") or "").strip()
                candidates = [value, key]

                lower_value = value.lower()
                if " es " in lower_value:
                    candidates.append(lower_value.split(" es ", 1)[1].strip())

                if " es el " in lower_value:
                    candidates.append(lower_value.split(" es el ", 1)[1].strip())

                if " es la " in lower_value:
                    candidates.append(lower_value.split(" es la ", 1)[1].strip())

                for candidate in candidates:
                    candidate = str(candidate or "").strip().lower()
                    if len(candidate) >= 3 and candidate in assistant_text:
                        confirmed = confirm_user_memory(
                            self.sessions.store,
                            memory_id=int(memory["id"]),
                            source_phrase=user_text,
                        )
                        response.debug["memory_confirmation"] = {
                            "confirmed": True,
                            "memory_id": confirmed.get("id"),
                            "key": confirmed.get("key"),
                            "value": confirmed.get("value"),
                            "status": confirmed.get("status"),
                            "trust_level": confirmed.get("trust_level"),
                            "verification_count": confirmed.get("verification_count"),
                        }
                        return confirmed

            return None
        except Exception as exc:
            response.debug["memory_confirmation"] = {
                "confirmed": False,
                "error": str(exc),
            }
            return None

    def _record_completed_turn(
        self, user_text: str, session, response: AgentResponse, dev_debug_payload: dict | None = None
    ) -> None:
        self._confirm_recent_user_memory_if_applicable(user_text, session, response)
        self.sessions.add_turn(session.session_id, "user", user_text)
        capture_explicit_preferences(user_text, self.sessions.store)

        tool_result = response.debug.get("tool_result")
        if tool_result:
            tool_call = response.tool_calls[0] if response.tool_calls else None
            self.sessions.add_turn_with_metadata(
                session.session_id,
                "tool",
                json.dumps(tool_result, ensure_ascii=True),
                metadata={
                    "tool_name": tool_result.get("tool_name"),
                    "success": tool_result.get("success"),
                },
            )
            record_tool_memory(
                self.sessions.store,
                tool_call=tool_call,
                tool_result=tool_result,
            )
            if tool_result.get("success") is False:
                record_error_memory(
                    self.sessions.store,
                    error=tool_result.get("error"),
                    source=f"tool:{tool_result.get('tool_name', 'unknown')}",
                )
            self.logger.write(
                "tool_calls",
                {
                    "session_id": session.session_id,
                    "route": response.route,
                    "tool_call": tool_call,
                    "tool_result": tool_result,
                    "success": tool_result.get("success"),
                    "blocked": tool_result.get("metadata", {}).get("blocked", False),
                },
            )
        session.conversation_state = update_conversation_state_from_response(
            session.conversation_state,
            user_text=user_text,
            response=response,
        )
        self.sessions.add_turn(session.session_id, "assistant", response.text)
        self.sessions.save_session_state(session.session_id)
        self.logger.write(
            "events",
            {
                "session_id": session.session_id,
                "event": "user_message",
                "text": user_text,
                "effective_route": response.route,
            },
        )
        self.logger.write(
            "model_outputs",
            {
                "session_id": session.session_id,
                "route": response.route,
                "status": response.status,
                "text": response.text,
            },
        )
        self._write_dev_event(response, dev_debug_payload, session=session)


        try:
            record_learning_from_completed_turn(
                self.sessions.store,
                user_message=user_text,
                response=response,
            )
        except Exception as exc:
            if dev_debug_payload is not None:
                print(f"[memory_writer] skipped: {exc}")

    def _record_error(
        self,
        session_id: str,
        error: str,
        route: str = "error",
        dev_debug_payload: dict | None = None,
    ) -> None:
        record_error_memory(
            self.sessions.store,
            error=error,
            source="gateway",
        )
        self.sessions.save_session_state(session_id)
        self.logger.write(
            "errors",
            {"session_id": session_id, "error": error},
        )
        response = AgentResponse(
            session_id=session_id,
            status="error",
            text=error,
            route=route,
            debug=dev_debug_payload or {},
        )
        self._write_dev_event(response, dev_debug_payload)

    def _write_dev_event(
        self,
        response: AgentResponse,
        dev_debug_payload: dict | None = None,
        session=None,
    ) -> None:
        event_response = response
        if dev_debug_payload:
            merged_debug = {**dev_debug_payload, **(response.debug or {})}
            if session is not None:
                merged_debug.setdefault("context", {}).setdefault("session_state", {})
                merged_debug["context"]["session_state"] = {
                    "pending_clarification": session.pending_clarification,
                    "pending_confirmation": session.pending_confirmation,
                    "pending_workflow": session.pending_workflow,
                    "previous_route": session.previous_route,
                    "current_route": session.current_route,
                    "conversation_state": normalize_conversation_state(session.conversation_state),
                }
            event_response = response.model_copy(update={"debug": merged_debug})
        self.logger.write("dev_events", build_dev_event(event_response))

    def _public_response(self, response: AgentResponse, debug: bool) -> AgentResponse:
        if debug:
            return response
        return response.model_copy(update={"debug": {}})
