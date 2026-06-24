import typer
from rich import print

from agent.gateway.gateway import Gateway
from agent.models.model_settings import (
    get_main_model,
    list_ollama_models,
    set_main_model,
)
from agent.rag.ingest import run_ingest
from agent.ui.dev_console import (
    DEFAULT_DEV_LOG_PATH,
    follow_dev_events,
    read_dev_events,
    render_dev_event,
)

app = typer.Typer(help="Local agent MVP CLI")
gateway = Gateway()


def _print_stream_token(output_func, text: str) -> None:
    try:
        output_func(text, end="", flush=True)
    except TypeError:
        output_func(text)


def _format_debug_lines(response, session) -> list[str]:
    lines = [
        f"route: {response.route}",
        f"status: {response.status}",
        f"session: {response.session_id}",
        f"pending_clarification: {session.pending_clarification}",
        f"pending_confirmation: {session.pending_confirmation}",
        f"previous_route: {session.previous_route}",
        f"current_route: {session.current_route}",
    ]
    if response.tool_calls:
        lines.append(f"tool_calls: {response.tool_calls}")
    if response.debug.get("tool_result"):
        lines.append(f"tool_result: {response.debug['tool_result']}")
    if response.debug.get("reflection"):
        lines.append(f"reflection: {response.debug['reflection']}")
    if response.debug.get("context", {}).get("rag_snippets"):
        lines.append(
            f"rag_snippets: {len(response.debug['context']['rag_snippets'])}"
        )
    return lines


def _log_model_changed(gateway_instance: Gateway, model_name: str) -> None:
    logger = getattr(gateway_instance, "logger", None)
    if logger is None:
        return
    logger.write(
        "dev_events",
        {
            "type": "model_changed",
            "role": "main",
            "model": model_name,
        },
    )


def _print_models(output_func, models: list[str]) -> None:
    output_func("Modelos disponibles en Ollama:")
    if not models:
        output_func("(ninguno)")
    else:
        for index, model_name in enumerate(models, 1):
            output_func(f"{index}. {model_name}")
    output_func("")
    output_func(f"Modelo principal actual: {get_main_model()}")


def _handle_models_command(
    command: str,
    gateway_instance: Gateway,
    *,
    input_func=input,
    output_func=print,
) -> bool:
    parts = command.split()
    if not parts or parts[0] != "/models":
        return False

    subcommand = parts[1] if len(parts) > 1 else ""

    try:
        if subcommand in {"", "list"}:
            models = list_ollama_models()
            _print_models(output_func, models)
            if subcommand == "list":
                return True
            if not models:
                return True
            selection = input_func("Selecciona un modelo por número: ").strip()
            if not selection:
                output_func("Selección cancelada.")
                return True
            if not selection.isdigit():
                output_func("Selección inválida.")
                return True
            index = int(selection)
            if index < 1 or index > len(models):
                output_func("Selección fuera de rango.")
                return True
            selected = set_main_model(models[index - 1])
            _log_model_changed(gateway_instance, selected)
            output_func(f"Modelo principal cambiado a {selected}")
            return True

        if subcommand == "current":
            output_func(f"Modelo principal actual: {get_main_model()}")
            return True

        if subcommand == "set":
            model_name = " ".join(parts[2:]).strip()
            selected = set_main_model(model_name)
            _log_model_changed(gateway_instance, selected)
            output_func(f"Modelo principal cambiado a {selected}")
            return True
    except Exception as exc:
        output_func(str(exc))
        return True

    output_func("Uso: /models, /models list, /models current, /models set <model_name>")
    return True


def _consume_stream_events(
    gateway_instance: Gateway,
    message: str,
    *,
    session_id: str | None = None,
    debug: bool = False,
    output_func=print,
) -> str:
    final_session_id = session_id
    saw_token = False
    for event in gateway_instance.stream_message(
        message, session_id=session_id, debug=debug
    ):
        event_type = event.get("type")
        if event_type == "token":
            if not event.get("text"):
                continue
            saw_token = True
            _print_stream_token(output_func, event["text"])
        elif event_type == "early_ack":
            output_func(event["text"])
        elif event_type in {"final", "error"}:
            response = event["response"]
            final_session_id = response.session_id
            if saw_token:
                output_func("")
            if event_type == "error" or not saw_token:
                output_func(response.text)
        elif event_type == "debug" and debug:
            debug_payload = event.get("debug", {})
            output_func(f"debug: {debug_payload}")
    return final_session_id or ""


def run_repl(
    gateway_instance: Gateway,
    *,
    debug: bool = False,
    stream: bool = False,
    input_func=input,
    output_func=print,
) -> None:
    session_id: str | None = None
    output_func("REPL listo. Usa /exit o /quit para salir.")
    while True:
        message = input_func(">>> ").strip()
        if not message:
            continue
        if message in {"/exit", "/quit"}:
            output_func("Saliendo del REPL.")
            return
        if _handle_models_command(
            message,
            gateway_instance,
            input_func=input_func,
            output_func=output_func,
        ):
            continue

        if stream:
            session_id = _consume_stream_events(
                gateway_instance,
                message,
                session_id=session_id,
                debug=debug,
                output_func=output_func,
            )
        else:
            response = gateway_instance.handle_message(
                message, session_id=session_id, debug=debug
            )
            session_id = response.session_id
            output_func(response.text)
            if debug:
                session = gateway_instance.sessions.get_or_create(session_id)
                for line in _format_debug_lines(response, session):
                    output_func(line)


def run_dev_console(
    *,
    follow: bool = False,
    tail: int = 10,
    session_id: str | None = None,
    json_output: bool = False,
    output_func=print,
    path=DEFAULT_DEV_LOG_PATH,
    stop_after: int | None = None,
) -> None:
    shown = 0
    if follow:
        for item in follow_dev_events(path, session_id=session_id, tail=tail):
            if isinstance(item, str):
                output_func(item)
            elif json_output:
                output_func(item)
            else:
                output_func(render_dev_event(item))
            shown += 1
            if stop_after is not None and shown >= stop_after:
                return
        return

    events, warnings = read_dev_events(path, session_id=session_id, tail=tail)
    for warning in warnings:
        output_func(warning)
    if not events:
        output_func("No dev events available.")
        return
    for event in events:
        output_func(event if json_output else render_dev_event(event))


@app.command()
def chat(
    message: str,
    session_id: str | None = typer.Option(None, "--session-id", "-s"),
    debug: bool = typer.Option(False, "--debug"),
    stream: bool = typer.Option(False, "--stream"),
) -> None:
    if stream:
        _consume_stream_events(
            gateway,
            message,
            session_id=session_id,
            debug=debug,
            output_func=print,
        )
        return
    response = gateway.handle_message(message, session_id=session_id, debug=debug)
    print(response.text)
    if debug:
        session = gateway.sessions.get_or_create(response.session_id)
        for line in _format_debug_lines(response, session):
            print(line)


@app.command()
def repl(
    debug: bool = typer.Option(False, "--debug"),
    stream: bool = typer.Option(False, "--stream"),
) -> None:
    run_repl(gateway, debug=debug, stream=stream)


@app.command("dev-console")
def dev_console(
    follow: bool = typer.Option(False, "--follow"),
    session_id: str | None = typer.Option(None, "--session-id", "-s"),
    tail: int = typer.Option(10, "--tail"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    run_dev_console(
        follow=follow,
        tail=tail,
        session_id=session_id,
        json_output=json_output,
    )


@app.command("rag-ingest")
def rag_ingest() -> None:
    try:
        print(run_ingest())
    except Exception as exc:
        print(f"RAG ingest failed: {exc}")
        raise typer.Exit(code=1) from exc
