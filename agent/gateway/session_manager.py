from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from agent.gateway.message_types import ConversationTurn
from agent.memory.sqlite_store import SQLiteStore
from agent.conversation_state.persistence import load_conversation_state, save_conversation_state
from agent.conversation_state.state import default_conversation_state, normalize_conversation_state


@dataclass
class SessionState:
    session_id: str
    history: list[ConversationTurn] = field(default_factory=list)
    pending_clarification: str | None = None
    pending_confirmation: dict | None = None
    pending_workflow: dict | None = None
    previous_route: str | None = None
    current_route: str | None = None
    conversation_state: dict[str, Any] = field(default_factory=default_conversation_state)


class SessionManager:
    def __init__(
        self,
        max_history: int = 12,
        store: SQLiteStore | None = None,
    ) -> None:
        self.max_history = max_history
        self.store = store or SQLiteStore()
        self._sessions: dict[str, SessionState] = {}

    def get_or_create(self, session_id: str | None = None) -> SessionState:
        if session_id and session_id in self._sessions:
            return self._sessions[session_id]
        new_session_id = session_id or uuid4().hex
        state = self.hydrate_session(new_session_id)
        if state is None:
            state = SessionState(session_id=new_session_id)
            self.save_session_state(new_session_id)
        self._sessions[new_session_id] = state
        return state

    def add_turn(self, session_id: str, role: str, content: str) -> None:
        state = self.get_or_create(session_id)
        self.store.append_turn(session_id, role, content)
        state.history.append(ConversationTurn(role=role, content=content))
        state.history = state.history[-self.max_history :]

    def add_turn_with_metadata(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> None:
        state = self.get_or_create(session_id)
        self.store.append_turn(session_id, role, content, metadata=metadata)
        state.history.append(ConversationTurn(role=role, content=content))
        state.history = state.history[-self.max_history :]

    def save_session_state(self, session_id: str) -> None:
        state = self._sessions.get(session_id)
        if state is None:
            state = SessionState(session_id=session_id)
            self._sessions[session_id] = state
        state.conversation_state = normalize_conversation_state(state.conversation_state)
        self.store.upsert_session_state(
            session_id=state.session_id,
            previous_route=state.previous_route,
            current_route=state.current_route,
            pending_clarification=state.pending_clarification,
            pending_confirmation=state.pending_confirmation,
            pending_workflow=state.pending_workflow,
        )
        save_conversation_state(self.store, state.session_id, state.conversation_state)

    def load_recent_history(
        self, session_id: str, limit: int | None = None
    ) -> list[ConversationTurn]:
        rows = self.store.load_recent_turns(session_id, limit or self.max_history)
        return [
            ConversationTurn(role=row["role"], content=row["content"])
            for row in rows
            if row["role"] in {"user", "assistant", "tool"}
        ]

    def hydrate_session(self, session_id: str) -> SessionState | None:
        stored = self.store.get_session_state(session_id)
        if stored is None:
            return None
        return SessionState(
            session_id=session_id,
            history=self.load_recent_history(session_id, self.max_history),
            pending_clarification=stored.get("pending_clarification"),
            pending_confirmation=stored.get("pending_confirmation"),
            pending_workflow=stored.get("pending_workflow"),
            previous_route=stored.get("previous_route"),
            current_route=stored.get("current_route"),
            conversation_state=load_conversation_state(self.store, session_id),
        )
