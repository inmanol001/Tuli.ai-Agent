import json
from collections.abc import Iterator

from agent.context_builder.assembler import (
    assemble_action_messages,
    assemble_final_messages,
    assemble_messages,
)
from agent.capabilities.tools.schemas import ToolCall
from agent.executor.results import ToolResult
from agent.gateway.message_types import ContextPackage
from agent.models.model_settings import get_main_model
from agent.models.action_models import ModelAction
from agent.models.ollama_client import OllamaClient


class MainModel:
    def __init__(
        self, client: OllamaClient | None = None, model: str | None = None
    ) -> None:
        self.client = client or OllamaClient()
        self.model = model

    def _current_model(self) -> str:
        return self.model or get_main_model()

    def respond(self, context: ContextPackage) -> str:
        return self.client.chat(
            self._current_model(),
            assemble_messages(context),
            stream=False,
            options={"temperature": 0.3, "top_p": 0.9, "num_ctx": 8192},
        ).strip()

    def respond_stream(self, context: ContextPackage) -> Iterator[str]:
        yield from self.client.chat_stream(
            self._current_model(),
            assemble_messages(context),
            options={"temperature": 0.3, "top_p": 0.9, "num_ctx": 8192},
        )

    def respond_with_rag(self, context: ContextPackage) -> str:
        return self.client.chat(
            self._current_model(),
            assemble_messages(context),
            stream=False,
            options={"temperature": 0.1, "top_p": 0.9, "num_ctx": 8192},
        ).strip()

    def plan_or_act(self, context: ContextPackage) -> ModelAction:
        raw = self.client.chat(
            self._current_model(),
            assemble_action_messages(context),
            format_schema=ModelAction.model_json_schema(),
            stream=False,
            think=False,
            options={"temperature": 0, "top_p": 0.9, "num_ctx": 8192},
        ).strip()
        return ModelAction.model_validate(json.loads(raw))

    def finalize_from_tool_result(
        self, context: ContextPackage, tool_call: ToolCall, tool_result: ToolResult
    ) -> str:
        return self.client.chat(
            self._current_model(),
            assemble_final_messages(context, tool_call, tool_result),
            stream=False,
            options={"temperature": 0.2, "top_p": 0.9, "num_ctx": 8192},
        ).strip()
