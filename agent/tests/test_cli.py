from agent.gateway.message_types import AgentResponse
from typer.testing import CliRunner

from agent.models import model_settings
from agent.ui import cli
from agent.ui.cli import run_repl


class FakeSession:
    def __init__(self):
        self.pending_clarification = None
        self.pending_confirmation = None
        self.previous_route = None
        self.current_route = None


class FakeSessions:
    def __init__(self):
        self.state = FakeSession()

    def get_or_create(self, session_id=None):
        return self.state


class FakeGateway:
    def __init__(self):
        self.sessions = FakeSessions()
        self.calls = []

    def handle_message(self, message, session_id=None, debug=False):
        self.calls.append((message, session_id, debug))
        self.sessions.state.previous_route = self.sessions.state.current_route
        self.sessions.state.current_route = "clarification"
        self.sessions.state.pending_clarification = "artist_or_genre"
        return AgentResponse(
            session_id="session-1",
            status="needs_clarification",
            text="Claro. ¿Qué tema o destino web quieres que abra o busque?",
            route="clarification",
            needs_user_input=True,
        )


class FakeToolGateway(FakeGateway):
    def stream_message(self, message, session_id=None, debug=False):
        self.calls.append((message, session_id, debug, "stream"))
        yield {
            "type": "early_ack",
            "text": "Claro, voy a buscarlo ahora.",
            "route": "action_ready",
            "suggested_tools": ["browser_search"],
        }
        yield {
            "type": "final",
            "response": AgentResponse(
                session_id="session-1",
                status="ok",
                text="Resultado final mock",
                route="action_ready",
                tool_calls=[
                    {
                        "tool_name": "browser_search",
                        "arguments": {"query": message, "target": "youtube"},
                    }
                ],
                debug={
                    "tool_result": {
                        "tool_name": "browser_search",
                        "success": True,
                        "data": {"query": message, "target": "youtube"},
                        "metadata": {},
                    }
                }
                if debug
                else {},
            ),
        }
        if debug:
            yield {
                "type": "debug",
                "debug": {
                    "tool_result": {
                        "tool_name": "browser_search",
                        "success": True,
                        "data": {"query": message, "target": "youtube"},
                        "metadata": {},
                    }
                },
            }

    def handle_message(self, message, session_id=None, debug=False):
        self.calls.append((message, session_id, debug))
        self.sessions.state.previous_route = self.sessions.state.current_route
        self.sessions.state.current_route = "action_ready"
        return AgentResponse(
            session_id="session-1",
            status="ok",
            text="Resultado final mock",
            route="action_ready",
            tool_calls=[{"tool_name": "browser_search", "arguments": {"query": message, "target": "youtube"}}],
            debug={
                "tool_result": {
                    "tool_name": "browser_search",
                    "success": True,
                    "data": {"query": message, "target": "youtube"},
                    "metadata": {},
                }
            },
        )


class FakeStreamGateway(FakeGateway):
    def stream_message(self, message, session_id=None, debug=False):
        self.calls.append((message, session_id, debug, "stream"))
        yield {"type": "token", "text": "Ho"}
        yield {"type": "token", "text": "la"}
        yield {
            "type": "final",
            "response": AgentResponse(
                session_id="session-1",
                status="ok",
                text="Hola",
                route="chat",
                debug={"route": "chat"} if debug else {},
            ),
        }
        if debug:
            yield {"type": "debug", "debug": {"route": "chat"}}


class FakeNonStreamRouteGateway(FakeGateway):
    def stream_message(self, message, session_id=None, debug=False):
        self.calls.append((message, session_id, debug, "stream"))
        yield {
            "type": "final",
            "response": AgentResponse(
                session_id="session-1",
                status="needs_clarification",
                text="Claro. ¿Qué detalle te falta para continuar?",
                route="clarification",
                needs_user_input=True,
            ),
        }


class FakeEmptyTokenStreamGateway(FakeGateway):
    def stream_message(self, message, session_id=None, debug=False):
        self.calls.append((message, session_id, debug, "stream"))
        yield {"type": "token", "text": ""}
        yield {"type": "token", "text": "¡"}
        yield {"type": "token", "text": ""}
        yield {"type": "token", "text": "Hola"}
        yield {"type": "token", "text": "!"}
        yield {
            "type": "final",
            "response": AgentResponse(
                session_id="session-1",
                status="ok",
                text="¡Hola!",
                route="chat",
            ),
        }


def test_run_repl_keeps_session_and_exits():
    gateway = FakeGateway()
    prompts = iter(["hola", "/quit"])
    output = []

    def fake_input(_prompt):
        return next(prompts)

    def fake_output(message):
        output.append(str(message))

    run_repl(gateway, input_func=fake_input, output_func=fake_output)

    assert gateway.calls == [("hola", None, False)]
    assert output[0] == "REPL listo. Usa /exit o /quit para salir."
    assert output[1] == "Claro. ¿Qué tema o destino web quieres que abra o busque?"
    assert output[-1] == "Saliendo del REPL."


def test_run_repl_shows_debug_state():
    gateway = FakeGateway()
    prompts = iter(["hola", "/exit"])
    output = []

    def fake_input(_prompt):
        return next(prompts)

    def fake_output(message):
        output.append(str(message))

    run_repl(gateway, debug=True, input_func=fake_input, output_func=fake_output)

    assert ("route: clarification") in output
    assert ("status: needs_clarification") in output
    assert ("session: session-1") in output
    assert ("pending_clarification: artist_or_genre") in output


def test_run_repl_shows_tool_debug_state():
    gateway = FakeToolGateway()
    prompts = iter(["omega", "/exit"])
    output = []

    def fake_input(_prompt):
        return next(prompts)

    def fake_output(message):
        output.append(str(message))

    run_repl(gateway, debug=True, input_func=fake_input, output_func=fake_output)

    assert "tool_calls: [{'tool_name': 'browser_search', 'arguments': {'query': 'omega', 'target': 'youtube'}}]" in output
    assert "tool_result: {'tool_name': 'browser_search', 'success': True, 'data': {'query': 'omega', 'target': 'youtube'}, 'metadata': {}}" in output


def test_run_repl_stream_keeps_session_and_outputs_tokens():
    gateway = FakeStreamGateway()
    prompts = iter(["hola", "otra", "/exit"])
    output = []

    def fake_input(_prompt):
        return next(prompts)

    def fake_output(message):
        output.append(str(message))

    run_repl(
        gateway,
        stream=True,
        input_func=fake_input,
        output_func=fake_output,
    )

    assert gateway.calls == [
        ("hola", None, False, "stream"),
        ("otra", "session-1", False, "stream"),
    ]
    assert "Ho" in output
    assert "la" in output


def test_run_repl_stream_non_stream_route_outputs_final_response():
    gateway = FakeNonStreamRouteGateway()
    prompts = iter(["busca música en YouTube", "/exit"])
    output = []

    def fake_input(_prompt):
        return next(prompts)

    def fake_output(message):
        output.append(str(message))

    run_repl(gateway, stream=True, input_func=fake_input, output_func=fake_output)

    assert "Claro. ¿Qué detalle te falta para continuar?" in output


def test_run_repl_stream_prints_early_ack_before_final_response():
    gateway = FakeToolGateway()
    prompts = iter(["omega", "/exit"])
    output = []

    def fake_input(_prompt):
        return next(prompts)

    def fake_output(message, **_kwargs):
        output.append(str(message))

    run_repl(gateway, stream=True, input_func=fake_input, output_func=fake_output)

    assert "Claro, voy a buscarlo ahora." in output
    assert output.index("Claro, voy a buscarlo ahora.") < output.index("Resultado final mock")


def test_run_repl_stream_ignores_empty_tokens_before_response():
    gateway = FakeEmptyTokenStreamGateway()
    prompts = iter(["hola", "/exit"])
    output = []

    def fake_input(_prompt):
        return next(prompts)

    def fake_output(message, **_kwargs):
        output.append(str(message))

    run_repl(gateway, stream=True, input_func=fake_input, output_func=fake_output)

    response_index = output.index("¡")
    assert "" not in output[:response_index]
    assert output[response_index : response_index + 3] == ["¡", "Hola", "!"]


def test_chat_command_prints_clean_text_by_default(monkeypatch):
    monkeypatch.setattr(cli, "gateway", FakeGateway())
    result = CliRunner().invoke(cli.app, ["chat", "hola"])

    assert result.exit_code == 0
    assert "Claro. ¿Qué tema o destino web quieres que abra o busque?" in result.output
    assert "router" not in result.output
    assert "debug" not in result.output


def test_models_list_does_not_hit_gateway(monkeypatch):
    gateway = FakeGateway()
    prompts = iter(["/models list", "/exit"])
    output = []

    monkeypatch.setattr(cli, "list_ollama_models", lambda: ["qwen3:4b", "llama3.1:8b"])
    monkeypatch.setattr(cli, "get_main_model", lambda: "qwen3:4b")

    run_repl(
        gateway,
        input_func=lambda _prompt: next(prompts),
        output_func=lambda message, **_kwargs: output.append(str(message)),
    )

    assert gateway.calls == []
    assert "Modelos disponibles en Ollama:" in output
    assert "1. qwen3:4b" in output
    assert "Modelo principal actual: qwen3:4b" in output


def test_models_current_does_not_hit_gateway(monkeypatch):
    gateway = FakeGateway()
    prompts = iter(["/models current", "/exit"])
    output = []

    monkeypatch.setattr(cli, "get_main_model", lambda: "llama3.1:8b")

    run_repl(
        gateway,
        input_func=lambda _prompt: next(prompts),
        output_func=lambda message, **_kwargs: output.append(str(message)),
    )

    assert gateway.calls == []
    assert "Modelo principal actual: llama3.1:8b" in output


def test_models_set_changes_model_without_hitting_gateway(monkeypatch):
    gateway = FakeGateway()
    prompts = iter(["/models set llama3.1:8b", "/exit"])
    output = []
    changed = []

    monkeypatch.setattr(cli, "set_main_model", lambda model: changed.append(model) or model)

    run_repl(
        gateway,
        input_func=lambda _prompt: next(prompts),
        output_func=lambda message, **_kwargs: output.append(str(message)),
    )

    assert gateway.calls == []
    assert changed == ["llama3.1:8b"]
    assert "Modelo principal cambiado a llama3.1:8b" in output


def test_models_selector_interactive_changes_model(monkeypatch):
    gateway = FakeGateway()
    prompts = iter(["/models", "2", "/exit"])
    output = []
    changed = []

    monkeypatch.setattr(cli, "list_ollama_models", lambda: ["qwen3:4b", "llama3.1:8b"])
    monkeypatch.setattr(cli, "get_main_model", lambda: "qwen3:4b")
    monkeypatch.setattr(cli, "set_main_model", lambda model: changed.append(model) or model)

    run_repl(
        gateway,
        input_func=lambda _prompt: next(prompts),
        output_func=lambda message, **_kwargs: output.append(str(message)),
    )

    assert gateway.calls == []
    assert changed == ["llama3.1:8b"]
    assert "1. qwen3:4b" in output
    assert "2. llama3.1:8b" in output


def test_models_command_logs_model_change(monkeypatch, tmp_path):
    class FakeLogger:
        def __init__(self):
            self.events = []

        def write(self, stream, event):
            self.events.append((stream, event))

    gateway = FakeGateway()
    gateway.logger = FakeLogger()
    prompts = iter(["/models set llama3.1:8b", "/exit"])

    monkeypatch.setattr(cli, "set_main_model", lambda model: model)

    run_repl(
        gateway,
        input_func=lambda _prompt: next(prompts),
        output_func=lambda *_args, **_kwargs: None,
    )

    assert gateway.logger.events == [
        (
            "dev_events",
            {"type": "model_changed", "role": "main", "model": "llama3.1:8b"},
        )
    ]
