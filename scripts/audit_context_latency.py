from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from agent.gateway.gateway import Gateway


DEFAULT_MESSAGES = [
    "hola Tuli",
    "abre github",
    "busca documentación de ollama",
]


class TimingRecorder:
    def __init__(self) -> None:
        self.current: dict[str, float] = {}

    def reset(self) -> None:
        self.current = {}

    def add(self, metric_name: str, elapsed_ms: float) -> None:
        self.current[metric_name] = self.current.get(metric_name, 0.0) + elapsed_ms

    def snapshot(self) -> dict[str, float]:
        return {key: round(value, 2) for key, value in sorted(self.current.items())}


def _json_size(value: Any) -> int:
    try:
        return len(json.dumps(value, ensure_ascii=False, default=str))
    except Exception:
        return len(str(value))


def _list_len(value: Any) -> int:
    return len(value) if isinstance(value, list) else 0


def _text_len(value: Any) -> int:
    return len(value) if isinstance(value, str) else 0


def _context_summary(context: dict[str, Any] | None) -> dict[str, Any]:
    context = context or {}
    behavior = context.get("behavior") if isinstance(context.get("behavior"), dict) else {}
    session_state = (
        context.get("session_state") if isinstance(context.get("session_state"), dict) else {}
    )
    return {
        "total_json_chars": _json_size(context),
        "system_prompt_chars": _text_len(context.get("system_prompt")),
        "task_instruction_chars": _text_len(context.get("task_instruction")),
        "user_message_chars": _text_len(context.get("user_message")),
        "recent_history_count": _list_len(context.get("recent_history")),
        "recent_history_json_chars": _json_size(context.get("recent_history") or []),
        "selected_plugins_count": _list_len(context.get("selected_plugins")),
        "selected_plugins_json_chars": _json_size(context.get("selected_plugins") or []),
        "selected_skills_count": _list_len(context.get("selected_skills")),
        "selected_skills_json_chars": _json_size(context.get("selected_skills") or []),
        "selected_tools_count": _list_len(context.get("selected_tools")),
        "selected_tools_json_chars": _json_size(context.get("selected_tools") or []),
        "rag_snippets_count": _list_len(context.get("rag_snippets")),
        "rag_snippets_json_chars": _json_size(context.get("rag_snippets") or []),
        "safety_rules_count": _list_len(context.get("safety_rules")),
        "behavior_json_chars": _json_size(behavior),
        "session_state_json_chars": _json_size(session_state),
    }


def _wrap_timed_method(
    obj: Any,
    method_name: str,
    metric_name: str,
    recorder: TimingRecorder,
) -> None:
    original = getattr(obj, method_name, None)
    if original is None or not callable(original):
        return

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        start = perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            recorder.add(metric_name, (perf_counter() - start) * 1000)

    setattr(obj, method_name, wrapped)


def _install_timing_wrappers(gateway: Gateway, recorder: TimingRecorder) -> None:
    """Install wrappers once. The recorder is reset before each turn."""
    _wrap_timed_method(gateway.router, "route", "router_ms", recorder)
    _wrap_timed_method(gateway.pipeline, "build_context", "context_builder_ms", recorder)
    _wrap_timed_method(gateway.response_controller, "handle", "response_controller_ms", recorder)

    controller = gateway.response_controller
    _wrap_timed_method(controller.main_model, "respond", "main_model_ms", recorder)
    _wrap_timed_method(controller.main_model, "respond_with_rag", "main_model_rag_ms", recorder)
    _wrap_timed_method(controller.tool_planner, "plan", "tool_planner_ms", recorder)
    _wrap_timed_method(controller.tool_finalizer, "finalize", "tool_finalizer_ms", recorder)
    _wrap_timed_method(controller.action_runner, "run_tool_call", "action_runner_ms", recorder)
    _wrap_timed_method(
        controller.chat_clarification_guard,
        "evaluate",
        "chat_clarification_guard_ms",
        recorder,
    )
    _wrap_timed_method(
        controller.action_intent_guard,
        "evaluate",
        "action_intent_guard_ms",
        recorder,
    )


def run_audit(messages: list[str], *, session_id: str | None = None) -> list[dict[str, Any]]:
    gateway = Gateway()
    recorder = TimingRecorder()
    _install_timing_wrappers(gateway, recorder)

    current_session_id = session_id
    rows: list[dict[str, Any]] = []

    for message in messages:
        recorder.reset()
        started = perf_counter()
        response = gateway.handle_message(message, session_id=current_session_id, debug=True)
        total_ms = (perf_counter() - started) * 1000
        current_session_id = response.session_id

        debug = response.debug or {}
        context = debug.get("context") if isinstance(debug.get("context"), dict) else {}
        router = debug.get("router") if isinstance(debug.get("router"), dict) else {}
        tool_result = debug.get("tool_result") if isinstance(debug.get("tool_result"), dict) else None

        rows.append(
            {
                "message": message,
                "route": response.route,
                "status": response.status,
                "session_id": response.session_id,
                "response_chars": len(response.text or ""),
                "total_ms": round(total_ms, 2),
                "timings_ms": recorder.snapshot(),
                "router": {
                    "model_used": router.get("model_used"),
                    "corrected": router.get("corrected"),
                    "error": router.get("error"),
                },
                "context_summary": _context_summary(context),
                "tool_calls_count": len(response.tool_calls or []),
                "tool_result": {
                    "tool_name": tool_result.get("tool_name"),
                    "success": tool_result.get("success"),
                    "error": tool_result.get("error"),
                }
                if tool_result
                else None,
            }
        )

    return rows


def _print_table(rows: list[dict[str, Any]]) -> None:
    for index, row in enumerate(rows, start=1):
        context = row["context_summary"]
        timings = row["timings_ms"]
        print(f"\n--- Turn {index}: {row['message']} ---")
        print(f"route={row['route']} status={row['status']} total_ms={row['total_ms']}")
        print(f"router={row['router']}")
        print(f"timings_ms={timings}")
        print(
            "context="
            f"total_json_chars={context['total_json_chars']}, "
            f"history={context['recent_history_count']}/"
            f"{context['recent_history_json_chars']} chars, "
            f"skills={context['selected_skills_count']}/"
            f"{context['selected_skills_json_chars']} chars, "
            f"tools={context['selected_tools_count']}/"
            f"{context['selected_tools_json_chars']} chars, "
            f"behavior_chars={context['behavior_json_chars']}, "
            f"session_state_chars={context['session_state_json_chars]}"
        )
        if row["tool_result"]:
            print(f"tool_result={row['tool_result']}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit Tuli context size and per-layer latency without changing runtime behavior."
    )
    parser.add_argument(
        "messages",
        nargs="*",
        help="Messages to run through Gateway. Defaults to a small smoke set.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print full JSON instead of the readable summary.",
    )
    parser.add_argument(
        "--session-id",
        default=None,
        help="Optional existing session id to reuse.",
    )
    args = parser.parse_args()

    messages = args.messages or DEFAULT_MESSAGES
    rows = run_audit(messages, session_id=args.session_id)
    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return
    _print_table(rows)


if __name__ == "__main__":
    main()
