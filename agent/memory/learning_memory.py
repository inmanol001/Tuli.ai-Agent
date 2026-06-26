from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any


VALID_STATUSES = {"temporary", "candidate", "verified", "deprecated"}


def normalize_phrase(text: str) -> str:
    text = (text or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_learning_memory(
    store: Any,
    *,
    user_phrase: str,
    correct_intent: str,
    correct_tool: str | None = None,
    correct_skill: str | None = None,
    confidence: float = 0.5,
    status: str = "temporary",
    source: str = "runtime",
    evidence: dict[str, Any] | None = None,
    notes: str | None = None,
) -> None:
    if not user_phrase or not correct_intent:
        return

    if status not in VALID_STATUSES:
        status = "temporary"

    normalized = normalize_phrase(user_phrase)
    if not normalized:
        return

    confidence = max(0.0, min(float(confidence), 1.0))
    timestamp = now_iso()
    evidence_json = json.dumps(evidence or {}, ensure_ascii=False)

    with store.connect() as conn:
        conn.execute(
            """
            INSERT INTO learning_memory (
                user_phrase,
                normalized_phrase,
                correct_intent,
                correct_tool,
                correct_skill,
                confidence,
                status,
                source,
                evidence_json,
                notes,
                usage_count,
                success_count,
                failure_count,
                created_at,
                updated_at,
                verified_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, 0, ?, ?, ?)
            ON CONFLICT(normalized_phrase, correct_intent, correct_tool, correct_skill)
            DO UPDATE SET
                user_phrase = excluded.user_phrase,
                confidence = MAX(learning_memory.confidence, excluded.confidence),
                status = CASE
                    WHEN learning_memory.status = 'verified' THEN 'verified'
                    WHEN learning_memory.status = 'deprecated' THEN 'deprecated'
                    WHEN learning_memory.success_count + excluded.success_count >= 2 THEN 'candidate'
                    ELSE learning_memory.status
                END,
                evidence_json = excluded.evidence_json,
                notes = COALESCE(excluded.notes, learning_memory.notes),
                usage_count = learning_memory.usage_count + 1,
                success_count = learning_memory.success_count + excluded.success_count,
                updated_at = excluded.updated_at
            """,
            (
                user_phrase,
                normalized,
                correct_intent,
                correct_tool,
                correct_skill,
                confidence,
                status,
                source,
                evidence_json,
                notes,
                1 if status in {"temporary", "candidate", "verified"} else 0,
                timestamp,
                timestamp,
                timestamp if status == "verified" else None,
            ),
        )


def load_learning_memory(
    store: Any,
    *,
    phrase: str | None = None,
    status: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    limit = max(1, min(int(limit), 100))

    clauses = []
    params: list[Any] = []

    if phrase:
        clauses.append("normalized_phrase = ?")
        params.append(normalize_phrase(phrase))

    if status:
        clauses.append("status = ?")
        params.append(status)

    where = ""
    if clauses:
        where = "WHERE " + " AND ".join(clauses)

    with store.connect() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM learning_memory
            {where}
            ORDER BY
                CASE status
                    WHEN 'verified' THEN 1
                    WHEN 'candidate' THEN 2
                    WHEN 'temporary' THEN 3
                    WHEN 'deprecated' THEN 4
                    ELSE 5
                END,
                confidence DESC,
                updated_at DESC
            LIMIT ?
            """,
            [*params, limit],
        ).fetchall()

    return [dict(row) for row in rows]


def verify_learning_memory(store: Any, memory_id: int) -> None:
    timestamp = now_iso()
    with store.connect() as conn:
        conn.execute(
            """
            UPDATE learning_memory
            SET status = 'verified',
                confidence = MAX(confidence, 0.95),
                verified_at = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (timestamp, timestamp, memory_id),
        )


def deprecate_learning_memory(store: Any, memory_id: int, notes: str | None = None) -> None:
    timestamp = now_iso()
    with store.connect() as conn:
        conn.execute(
            """
            UPDATE learning_memory
            SET status = 'deprecated',
                notes = COALESCE(?, notes),
                updated_at = ?
            WHERE id = ?
            """,
            (notes, timestamp, memory_id),
        )
