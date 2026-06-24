from typing import Literal

from pydantic import BaseModel

from agent.capabilities.tools.schemas import ToolCall


ActionKind = Literal[
    "chat_response",
    "clarification_question",
    "tool_call",
    "safety_confirmation",
    "final_answer",
    "error",
]


class ModelAction(BaseModel):
    kind: ActionKind
    text: str = ""
    tool_call: ToolCall | None = None
