from collections.abc import Iterable
from collections.abc import Iterator
from typing import Any

try:
    import ollama
except ModuleNotFoundError:  # pragma: no cover
    ollama = None


def _ollama_module():
    if ollama is None:
        raise ModuleNotFoundError(
            "ollama is required for live model calls but is not installed in this environment"
        )
    return ollama


class OllamaClient:
    def chat(
        self,
        model: str,
        messages: Iterable[dict[str, str]],
        *,
        format_schema: dict[str, Any] | None = None,
        stream: bool = False,
        think: bool | str | None = None,
        options: dict[str, Any] | None = None,
    ) -> str:
        ollama = _ollama_module()
        response = ollama.chat(
            model=model,
            messages=list(messages),
            format=format_schema,
            stream=stream,
            think=think,
            options=options or {},
        )
        if stream:
            return "".join(chunk["message"]["content"] for chunk in response)
        return response.message.content

    def chat_with_tools(
        self,
        model: str,
        messages: Iterable[dict[str, str]],
        tools: list[dict[str, Any]],
        *,
        options: dict[str, Any] | None = None,
    ) -> Any:
        ollama = _ollama_module()
        return ollama.chat(
            model=model,
            messages=list(messages),
            tools=tools,
            stream=False,
            options=options or {},
        )

    def chat_stream(
        self,
        model: str,
        messages: Iterable[dict[str, str]],
        *,
        format_schema: dict[str, Any] | None = None,
        think: bool | str | None = None,
        options: dict[str, Any] | None = None,
    ) -> Iterator[str]:
        if format_schema is not None:
            raise ValueError("Streaming with format_schema is not supported.")
        ollama = _ollama_module()
        response = ollama.chat(
            model=model,
            messages=list(messages),
            stream=True,
            think=think,
            options=options or {},
        )
        prefix_buffer = ""
        filtering_think = True
        passthrough = False
        for chunk in response:
            token = chunk["message"]["content"]
            if not token:
                continue

            if passthrough:
                yield token
                continue

            prefix_buffer += token
            lowered = prefix_buffer.lstrip().lower()
            looks_like_thinking = lowered.startswith("<think") or lowered.startswith(
                "thinking"
            )

            if filtering_think and looks_like_thinking:
                if "</think>" not in prefix_buffer:
                    continue
                _, visible = prefix_buffer.split("</think>", 1)
                prefix_buffer = ""
                filtering_think = False
                passthrough = True
                if visible:
                    yield visible
                continue

            if filtering_think and "</think>" in prefix_buffer:
                _, visible = prefix_buffer.split("</think>", 1)
                prefix_buffer = ""
                filtering_think = False
                passthrough = True
                if visible:
                    yield visible
                continue

            if filtering_think:
                filtering_think = False
                passthrough = True
                yield token
