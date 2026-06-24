from typing import Any

from agent.memory.sqlite_store import SQLiteStore


def summarize_tool_result(tool_result: dict[str, Any]) -> str | None:
    if tool_result.get("success") is False:
        return tool_result.get("error") or "Tool failed."

    data = tool_result.get("data") or {}
    results = data.get("results") or []
    if results:
        return results[0].get("url") or results[0].get("title")
    if data.get("query"):
        return f"query={data['query']}"
    return "Tool completed successfully."


def record_tool_memory(
    store: SQLiteStore,
    *,
    tool_call: dict[str, Any] | None,
    tool_result: dict[str, Any],
) -> None:
    tool_name = tool_result.get("tool_name") or (tool_call or {}).get("tool_name")
    if not tool_name:
        return
    store.record_tool_result(
        tool_name=tool_name,
        success=bool(tool_result.get("success")),
        input_data=(tool_call or {}).get("arguments"),
        result_summary=summarize_tool_result(tool_result),
        notes=None,
    )
