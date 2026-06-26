from typing import Any

from agent.context_builder.builder import ContextBuilder
from agent.gateway.session_manager import SessionState
from agent.router.router_schema import RouterDecision


class Pipeline:
    def __init__(
        self,
        context_builder: ContextBuilder | None = None,
        learning_memory_store: Any | None = None,
    ) -> None:
        self.context_builder = context_builder or ContextBuilder(
            learning_memory_store=learning_memory_store
        )

    def build_context(
        self, user_text: str, decision: RouterDecision, session: SessionState
    ):
        return self.context_builder.build(user_text, decision, session)

