from agent.context_builder.builder import ContextBuilder
from agent.gateway.session_manager import SessionState
from agent.router.router_schema import RouterDecision


class Pipeline:
    def __init__(self, context_builder: ContextBuilder | None = None) -> None:
        self.context_builder = context_builder or ContextBuilder()

    def build_context(
        self, user_text: str, decision: RouterDecision, session: SessionState
    ):
        return self.context_builder.build(user_text, decision, session)

