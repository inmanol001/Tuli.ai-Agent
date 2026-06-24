import json

from agent.capabilities.tools.schemas import ToolCall
from agent.executor.results import ToolResult
from agent.models.tool_finalizer import ToolFinalizerModel


class FakeClient:
    def __init__(self, response=None, error: Exception | None = None):
        self.response = response
        self.error = error
        self.calls = []

    def chat(self, model, messages, **kwargs):
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "kwargs": kwargs,
            }
        )
        if self.error is not None:
            raise self.error
        return self.response


def browser_call():
    return ToolCall(
        tool_name="browser_search",
        arguments={"query": "ollama tool calling", "target": "web"},
        risk_level="low",
    )


def test_tool_finalizer_returns_model_text():
    client = FakeClient(response="Respuesta natural final.")
    result = ToolFinalizerModel(client=client).finalize(
        user_message="busca información sobre tool calling en Ollama",
        tool_call=browser_call(),
        tool_result=ToolResult(
            tool_name="browser_search",
            success=True,
            data={"target": "web", "url": "https://google.test?q=ollama"},
        ),
    )

    assert result.text == "Respuesta natural final."
    assert result.fallback is False


def test_tool_finalizer_sends_minimal_payload_without_tools():
    client = FakeClient(response="ok")
    tool_call = browser_call()
    tool_result = ToolResult(
        tool_name="browser_search",
        success=True,
        data={"target": "web", "url": "https://google.test?q=ollama"},
    )

    ToolFinalizerModel(client=client).finalize(
        user_message="busca información sobre tool calling en Ollama",
        tool_call=tool_call,
        tool_result=tool_result,
    )

    call = client.calls[0]
    payload = json.loads(call["messages"][1]["content"])
    assert payload["user_message"] == "busca información sobre tool calling en Ollama"
    assert payload["tool_call"] == tool_call.model_dump(mode="json")
    assert payload["tool_result"] == tool_result.model_dump(mode="json")
    assert "tools" not in call["kwargs"]


def test_tool_finalizer_uses_fallback_when_model_fails():
    result = ToolFinalizerModel(client=FakeClient(error=RuntimeError("boom"))).finalize(
        user_message="busca información sobre tool calling en Ollama",
        tool_call=browser_call(),
        tool_result=ToolResult(
            tool_name="browser_search",
            success=True,
            data={"target": "web", "url": "https://google.test?q=ollama"},
        ),
    )

    assert result.fallback is True
    assert result.error == "boom"
    assert "https://google.test?q=ollama" in result.text


def test_tool_finalizer_browser_search_fallback_uses_url():
    model = ToolFinalizerModel(client=FakeClient(error=RuntimeError("boom")))
    result = model.finalize(
        user_message="busca información",
        tool_call=browser_call(),
        tool_result=ToolResult(
            tool_name="browser_search",
            success=True,
            data={"target": "web", "url": "https://google.test?q=ollama"},
        ),
    )

    assert "Abrí la búsqueda en el navegador" in result.text
    assert "https://google.test?q=ollama" in result.text


def test_tool_finalizer_open_app_failure_fallback_returns_error():
    result = ToolFinalizerModel(client=FakeClient(error=RuntimeError("boom"))).finalize(
        user_message="abre Chrome",
        tool_call=ToolCall(tool_name="open_app", arguments={"app_name": "Google Chrome"}),
        tool_result=ToolResult(
            tool_name="open_app",
            success=False,
            error="not authorized",
            data={"app_name": "Google Chrome"},
        ),
    )

    assert result.text == "No pude abrir la aplicación: not authorized"


def test_tool_finalizer_open_app_verified_false_is_honest():
    result = ToolFinalizerModel(client=FakeClient(error=RuntimeError("boom"))).finalize(
        user_message="abre Chrome",
        tool_call=ToolCall(tool_name="open_app", arguments={"app_name": "Google Chrome"}),
        tool_result=ToolResult(
            tool_name="open_app",
            success=True,
            data={"app_name": "Google Chrome"},
            metadata={"verified": False},
        ),
    )

    assert "Envié la orden para abrir Google Chrome" in result.text
    assert "quedó activa" in result.text
    assert "Abrí" not in result.text


def test_tool_finalizer_space_next_fallback_is_honest():
    result = ToolFinalizerModel(client=FakeClient(error=RuntimeError("boom"))).finalize(
        user_message="cambia al siguiente escritorio",
        tool_call=ToolCall(tool_name="macos_space_next", arguments={}),
        tool_result=ToolResult(
            tool_name="macos_space_next",
            success=True,
            data={"action": "macos_space_next"},
        ),
    )

    assert result.text == "Envié el atajo para cambiar al siguiente escritorio."


def test_tool_finalizer_window_native_tiling_verified_false_is_honest():
    result = ToolFinalizerModel(client=FakeClient(error=RuntimeError("boom"))).finalize(
        user_message="pon la ventana a la derecha",
        tool_call=ToolCall(
            tool_name="window_native_tiling",
            arguments={"action": "right"},
        ),
        tool_result=ToolResult(
            tool_name="window_native_tiling",
            success=True,
            data={
                "action": "right",
                "target": "frontmost window",
                "method": "system_events_window_menu",
                "verified": False,
            },
        ),
    )

    assert "Envié la acción nativa de macOS" in result.text
    assert "derecha" in result.text
    assert "verifiqué" not in result.text.lower()
