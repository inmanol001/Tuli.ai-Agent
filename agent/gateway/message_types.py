from typing import Any, Literal

from pydantic import BaseModel, Field

from agent.router.router_schema import RouterDecision


AgentStatus = Literal[
    "ok",
    "needs_clarification",
    "needs_confirmation",
    "refused",
    "error",
]


class AgentResponse(BaseModel):
    session_id: str
    status: AgentStatus
    text: str
    route: str
    needs_user_input: bool = False
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    debug: dict[str, Any] = Field(default_factory=dict)


class ConversationTurn(BaseModel):
    role: Literal["user", "assistant", "tool"]
    content: str


class ContextPackage(BaseModel):
    system_prompt: str
    user_message: str
    router_decision: RouterDecision
    recent_history: list[ConversationTurn] = Field(default_factory=list)
    session_state: dict[str, Any] = Field(default_factory=dict)
    selected_plugins: list[dict[str, Any]] = Field(default_factory=list)
    selected_skills: list[dict[str, Any]] = Field(default_factory=list)
    selected_tools: list[dict[str, Any]] = Field(default_factory=list)
    rag_snippets: list[dict[str, Any]] = Field(default_factory=list)
    safety_rules: list[str] = Field(default_factory=list)
    task_instruction: str = ""
