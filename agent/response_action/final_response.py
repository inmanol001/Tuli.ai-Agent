from agent.gateway.message_types import AgentResponse


def build_response(
    session_id: str,
    status: str,
    text: str,
    route: str,
    *,
    needs_user_input: bool = False,
    tool_calls: list[dict] | None = None,
    debug: dict | None = None,
) -> AgentResponse:
    return AgentResponse(
        session_id=session_id,
        status=status,
        text=text,
        route=route,
        needs_user_input=needs_user_input,
        tool_calls=tool_calls or [],
        debug=debug or {},
    )
