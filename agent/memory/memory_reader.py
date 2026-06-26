from __future__ import annotations

from typing import Any

from agent.memory.learning_memory import load_learning_memory, normalize_phrase


ACTIVE_STATUSES = {"candidate", "verified"}


def _compact_hint(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row.get("id"),
        "user_phrase": row.get("user_phrase"),
        "normalized_phrase": row.get("normalized_phrase"),
        "correct_intent": row.get("correct_intent"),
        "correct_tool": row.get("correct_tool"),
        "correct_skill": row.get("correct_skill"),
        "confidence": row.get("confidence"),
        "status": row.get("status"),
        "success_count": row.get("success_count"),
        "updated_at": row.get("updated_at"),
    }


def load_relevant_learning_hints(
    store: Any,
    *,
    user_message: str,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """
    Lee aprendizajes estructurados útiles para el contexto.

    V1 es conservador:
    - ignora temporary
    - ignora deprecated
    - solo devuelve candidate/verified
    - primero intenta match exacto por frase normalizada
    - no decide ni ejecuta nada
    """
    if store is None:
        return []

    normalized = normalize_phrase(user_message)
    if not normalized:
        return []

    hints: list[dict[str, Any]] = []

    for status in ("verified", "candidate"):
        rows = load_learning_memory(
            store,
            phrase=user_message,
            status=status,
            limit=limit,
        )
        for row in rows:
            if row.get("status") in ACTIVE_STATUSES:
                hints.append(_compact_hint(row))

    # Deduplicar por id preservando orden.
    seen = set()
    deduped = []
    for hint in hints:
        key = hint.get("id")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(hint)

    return deduped[:limit]
