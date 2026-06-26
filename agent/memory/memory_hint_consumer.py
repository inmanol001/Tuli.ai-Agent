from __future__ import annotations

from typing import Any


ACTIVE_STATUSES = {"candidate", "verified"}


def _dedupe_by_name(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    result: list[dict[str, Any]] = []

    for item in items:
        name = item.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        result.append(item)

    return result


def apply_learning_hints_to_capabilities(
    capabilities: dict[str, list[dict[str, Any]]],
    learning_hints: list[dict[str, Any]],
    *,
    capability_context: Any,
) -> dict[str, list[dict[str, Any]]]:
    """
    Usa learning_hints como señal contextual.

    V1 segura:
    - solo candidate/verified
    - solo agrega tools/skills existentes en registries
    - no cambia router_decision
    - no crea tool_call
    - no ejecuta nada
    """
    if not learning_hints:
        return capabilities

    plugins = list(capabilities.get("plugins") or [])
    skills = list(capabilities.get("skills") or [])
    tools = list(capabilities.get("tools") or [])

    hinted_tool_names: list[str] = []
    hinted_skill_names: list[str] = []

    for hint in learning_hints:
        if hint.get("status") not in ACTIVE_STATUSES:
            continue

        correct_tool = hint.get("correct_tool")
        correct_skill = hint.get("correct_skill")

        if correct_tool:
            hinted_tool_names.append(str(correct_tool))

        if correct_skill:
            hinted_skill_names.append(str(correct_skill))

    if hinted_tool_names:
        tools.extend(
            tool.model_dump()
            for tool in capability_context.tool_registry.find_active(hinted_tool_names)
        )

    if hinted_skill_names:
        skills.extend(
            skill.model_dump()
            for skill in capability_context.skill_selector.select(hinted_skill_names)
        )

    return {
        "plugins": _dedupe_by_name(plugins),
        "skills": _dedupe_by_name(skills),
        "tools": _dedupe_by_name(tools),
    }
