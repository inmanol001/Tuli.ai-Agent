from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterable


DEFAULT_DEV_LOG_PATH = Path("agent/logs/dev_events.jsonl")


def read_dev_events(
    path: str | Path = DEFAULT_DEV_LOG_PATH,
    *,
    session_id: str | None = None,
    tail: int = 10,
) -> tuple[list[dict[str, Any]], list[str]]:
    path = Path(path)
    if not path.exists():
        return [], [f"No dev events log found at {path}."]

    warnings = []
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            warnings.append(f"Skipped corrupt JSONL line {line_number}.")
            continue
        if session_id and event.get("session_id") != session_id:
            continue
        events.append(event)
    return events[-tail:], warnings


def follow_dev_events(
    path: str | Path = DEFAULT_DEV_LOG_PATH,
    *,
    session_id: str | None = None,
    tail: int = 10,
    poll_interval: float = 0.5,
) -> Iterable[dict[str, Any] | str]:
    path = Path(path)
    events, warnings = read_dev_events(path, session_id=session_id, tail=tail)
    yield from warnings
    yield from events
    seen_lines = 0
    if path.exists():
        seen_lines = len(path.read_text(encoding="utf-8").splitlines())

    while True:
        if not path.exists():
            time.sleep(poll_interval)
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        for line_number, line in enumerate(lines[seen_lines:], seen_lines + 1):
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                yield f"Skipped corrupt JSONL line {line_number}."
                continue
            if session_id and event.get("session_id") != session_id:
                continue
            yield event
        seen_lines = len(lines)
        time.sleep(poll_interval)


def render_dev_console(events: list[dict[str, Any]]) -> str:
    return "\n".join(render_dev_event(event) for event in events)


def render_dev_event(event: dict[str, Any]) -> str:
    if event.get("type") == "early_ack":
        return "\n".join(
            [
                "──────────────── Agent Dev Event ────────────────",
                f"session: {event.get('session_id')}",
                "status: early_ack",
                f"route: {event.get('route')}",
                f"text: {event.get('text')}",
                f"suggested_tools: {_join_or_none(event.get('suggested_tools'))}",
                "────────────────────────────────────────────────",
            ]
        )
    if event.get("type") == "model_changed":
        return "\n".join(
            [
                "──────────────── Agent Dev Event ────────────────",
                f"role: {event.get('role')}",
                "status: model_changed",
                f"model: {event.get('model')}",
                "────────────────────────────────────────────────",
            ]
        )
    router = event.get("router") or {}
    state = event.get("session_state") or {}
    capabilities = event.get("capabilities") or {}
    rag = event.get("rag") or {}
    reflection = event.get("reflection")
    memory = event.get("memory") or {}
    lines = [
        "──────────────── Agent Dev Event ────────────────",
        f"time: {event.get('ts') or event.get('timestamp')}",
        f"session: {event.get('session_id')}",
        f"status: {event.get('status')}",
        f"route: {event.get('route')}",
        f"needs_user_input: {event.get('needs_user_input')}",
        "",
        "router:",
        f"  intent: {router.get('intent')}",
        f"  domain: {router.get('domain')}",
        f"  action: {router.get('action')}",
        f"  needs_tool: {router.get('needs_tool')}",
        f"  risk: {router.get('risk_level')}",
        f"  corrected: {router.get('corrected')}",
        f"  model: {router.get('model_used')}",
        "",
        "session_state:",
        f"  pending_clarification: {state.get('pending_clarification')}",
        f"  pending_confirmation: {state.get('pending_confirmation')}",
        f"  previous_route: {state.get('previous_route')}",
        f"  current_route: {state.get('current_route')}",
        "",
        "capabilities:",
        f"  plugins: {_join_or_none(capabilities.get('plugins'))}",
        f"  skills: {_join_or_none(capabilities.get('skills'))}",
        "  tools:",
    ]
    tools = capabilities.get("tools") or []
    if tools:
        for tool in tools:
            lines.append(
                "    - "
                f"{tool.get('name')} active={tool.get('active')} "
                f"declared={tool.get('declared')} risk={tool.get('risk_level')}"
            )
    else:
        lines.append("    none")

    lines.extend(["", "rag:"])
    if rag.get("count"):
        lines.append(f"  count: {rag.get('count')}")
        for snippet in rag.get("snippets") or []:
            lines.append(f"  - {snippet.get('source')}: {snippet.get('preview')}")
    else:
        lines.append("  none")

    lines.extend(["", "tool_calls:"])
    tool_calls = event.get("tool_calls") or []
    if tool_calls:
        for call in tool_calls:
            lines.append(
                f"  - {call.get('tool_name')} {call.get('arguments')} "
                f"risk={call.get('risk_level')} confirm={call.get('requires_confirmation')}"
            )
    else:
        lines.append("  none")

    lines.extend(["", "tool_result:"])
    result = event.get("tool_result")
    if result:
        lines.append(
            f"  {result.get('tool_name')} success={result.get('success')} "
            f"error={result.get('error')} metadata={result.get('metadata')}"
        )
        if result.get("data_preview"):
            lines.append(f"  data: {result.get('data_preview')}")
    else:
        lines.append("  none")

    lines.extend(["", "reflection:"])
    if reflection:
        lines.append(f"  retry_count: {reflection.get('retry_count')}")
        lines.append(f"  reason: {reflection.get('retry_reason')}")
        for attempt in reflection.get("attempts") or []:
            lines.append(
                "  - "
                f"attempt={attempt.get('attempt_number')} "
                f"execution={attempt.get('execution_number')} "
                f"success={attempt.get('success')} "
                f"decision={attempt.get('decision_reason')} "
                f"retry={attempt.get('should_retry')} "
                f"stop={attempt.get('should_stop')}"
            )
    else:
        lines.append("  none")

    lines.extend(
        [
            "",
            "memory:",
            f"  session_persisted: {memory.get('session_persisted')}",
            f"  turns_count: {memory.get('turns_count')}",
            "────────────────────────────────────────────────",
        ]
    )
    return "\n".join(lines)


def _join_or_none(values) -> str:
    values = [value for value in (values or []) if value]
    return ", ".join(values) if values else "none"
