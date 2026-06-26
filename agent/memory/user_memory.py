from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from agent.memory.learning_memory import normalize_phrase, now_iso
from agent.memory.memory_intent_classifier import classify_memory_intent


ACTIVE_STATUS = "active"


@dataclass(frozen=True)
class ExplicitMemoryRequest:
    source_phrase: str
    value: str
    memory_type: str = "instruction"
    key: str | None = None


_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^\s*recuerda\s+que\s+(.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*recuerdame\s+que\s+(.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*recu[eé]rdame\s+que\s+(.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*recuerda\s+esto\s*:?\s+(.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*anota\s+que\s+(.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*anota\s+esto\s*:?\s+(.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*guarda\s+que\s+(.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*guarda\s+esto\s*:?\s+(.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*ten\s+pendiente\s+que\s+(.+?)\s*$", re.IGNORECASE),
    re.compile(r"^\s*de\s+ahora\s+en\s+adelante\s+(.+?)\s*$", re.IGNORECASE),
]


def ensure_user_memory_table(store: Any) -> None:
    with store.connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS user_memory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type TEXT NOT NULL,
                key TEXT,
                value TEXT NOT NULL,
                source_phrase TEXT NOT NULL,
                normalized_source_phrase TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                confidence REAL NOT NULL DEFAULT 1.0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )

        existing_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(user_memory)").fetchall()
        }

        if "verification_count" not in existing_columns:
            conn.execute(
                "ALTER TABLE user_memory ADD COLUMN verification_count INTEGER NOT NULL DEFAULT 1"
            )

        if "trust_level" not in existing_columns:
            conn.execute(
                "ALTER TABLE user_memory ADD COLUMN trust_level TEXT NOT NULL DEFAULT 'normal'"
            )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_memory_status_updated
            ON user_memory(status, updated_at)
            """
        )
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_user_memory_normalized_source
            ON user_memory(normalized_source_phrase)
            """
        )


def detect_explicit_memory_request(text: str) -> ExplicitMemoryRequest | None:
    raw = (text or "").strip()
    if not raw:
        return None

    for pattern in _PATTERNS:
        match = pattern.match(raw)
        if not match:
            continue

        value = match.group(1).strip()
        if not value:
            return None

        # Evita guardar comandos o basura obvia.
        if value in {".", "?", "!"}:
            return None

        return ExplicitMemoryRequest(
            source_phrase=raw,
            value=value,
            memory_type=_classify_memory_type(value),
            key=_guess_key(value),
        )

    return None


def _classify_memory_type(value: str) -> str:
    normalized = normalize_phrase(value)

    if "cuando diga" in normalized or "cuando yo diga" in normalized:
        return "alias"

    if (
        "prefiero" in normalized
        or "me gusta que" in normalized
        or "no me gusta que" in normalized
        or "no vuelvas a" in normalized
    ):
        return "preference"

    if (
        "proyecto" in normalized
        or "agente" in normalized
        or "tuli" in normalized
        or "cliente" in normalized
    ):
        return "project"

    if (
        "mi cumpleaños" in normalized
        or "mi cumpleanos" in normalized
        or "mi color favorito" in normalized
        or "mi nombre" in normalized
    ):
        return "personal_fact"

    return "instruction"


def _guess_key(value: str) -> str | None:
    normalized = normalize_phrase(value)

    alias_match = re.search(
        r"cuando\s+(?:yo\s+)?diga\s+(.+?)\s+(?:me\s+refiero\s+a|significa|quiere\s+decir)\s+(.+)",
        normalized,
    )
    if alias_match:
        return alias_match.group(1).strip()

    if "mi cumpleaños" in normalized or "mi cumpleanos" in normalized:
        return "birthday"

    if "mi color favorito" in normalized:
        return "favorite_color"

    if "mi nombre" in normalized:
        return "name"

    if "no vuelvas a" in normalized:
        return "negative_preference"

    if "prefiero" in normalized:
        return "preference"

    return None


def record_user_memory(
    store: Any,
    *,
    source_phrase: str,
    value: str,
    memory_type: str = "instruction",
    key: str | None = None,
    confidence: float = 1.0,
    status: str = ACTIVE_STATUS,
) -> dict[str, Any]:
    ensure_user_memory_table(store)

    now = now_iso()
    normalized_source = normalize_phrase(source_phrase)
    normalized_value = normalize_phrase(value)

    with store.connect() as conn:
        existing = conn.execute(
            """
            SELECT *
            FROM user_memory
            WHERE status = ?
              AND memory_type = ?
              AND COALESCE(key, '') = COALESCE(?, '')
              AND lower(value) = lower(?)
            ORDER BY id DESC
            LIMIT 1
            """,
            (status, memory_type, key, value),
        ).fetchone()

        if existing is not None:
            memory_id = existing["id"]
            next_verification_count = int(existing["verification_count"] or 1) + 1
            next_trust_level = (
                "trusted" if next_verification_count >= 2 else existing["trust_level"]
            )
            next_status = (
                "verified" if next_verification_count >= 2 else existing["status"]
            )
            next_confidence = max(float(existing["confidence"] or 0), confidence)
            if next_verification_count >= 2:
                next_confidence = max(next_confidence, 0.95)

            conn.execute(
                """
                UPDATE user_memory
                SET source_phrase = ?,
                    normalized_source_phrase = ?,
                    confidence = ?,
                    verification_count = ?,
                    trust_level = ?,
                    status = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    source_phrase,
                    normalized_source,
                    next_confidence,
                    next_verification_count,
                    next_trust_level,
                    next_status,
                    now,
                    memory_id,
                ),
            )
        else:
            cursor = conn.execute(
                """
                INSERT INTO user_memory (
                    memory_type,
                    key,
                    value,
                    source_phrase,
                    normalized_source_phrase,
                    status,
                    confidence,
                    created_at,
                    updated_at,
                    verification_count,
                    trust_level
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_type,
                    key,
                    value,
                    source_phrase,
                    normalized_source,
                    status,
                    confidence,
                    now,
                    now,
                    1,
                    "normal",
                ),
            )
            memory_id = cursor.lastrowid

        row = conn.execute(
            """
            SELECT *
            FROM user_memory
            WHERE id = ?
            """,
            (memory_id,),
        ).fetchone()

    return dict(row)


def load_user_memories(
    store: Any,
    *,
    status: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    if store is None:
        return []

    ensure_user_memory_table(store)

    with store.connect() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM user_memory
            WHERE ((? IS NULL AND status IN ('active', 'verified')) OR status = ?)
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (status, status, limit),
        ).fetchall()

    return [dict(row) for row in rows]


def handle_explicit_memory_request(store: Any, user_text: str) -> dict[str, Any] | None:
    request = detect_explicit_memory_request(user_text)
    if request is not None:
        memory = record_user_memory(
            store,
            source_phrase=request.source_phrase,
            value=request.value,
            memory_type=request.memory_type,
            key=request.key,
        )
        return memory

    classification = classify_memory_intent(user_text)

    if not classification.should_save:
        return None

    memory = record_user_memory(
        store,
        source_phrase=user_text,
        value=classification.value,
        memory_type=classification.memory_type,
        key=classification.key,
        confidence=classification.confidence,
    )

    return memory


def load_relevant_user_memories(
    store: Any,
    *,
    user_message: str | None = None,
    limit: int = 8,
) -> list[dict[str, Any]]:
    if store is None:
        return []

    """
    Carga memorias activas útiles para el prompt.

    Regla importante:
    - Las memorias estables del usuario deben estar disponibles aunque el query
      no haga match perfecto por tokens.
    - No decide tools.
    - No cambia router_decision.
    """
    memories = load_user_memories(store, status=None, limit=50)

    if not memories:
        return []

    if not user_message:
        return memories[:limit]

    query = normalize_phrase(user_message)
    query_tokens = {token for token in query.split() if len(token) >= 3}

    always_include_types = {
        "preference",
        "instruction",
        "personal_fact",
        "alias",
        "project",
    }

    scored: list[tuple[int, int, dict[str, Any]]] = []

    for index, memory in enumerate(memories):
        haystack = normalize_phrase(
            " ".join(
                str(memory.get(field) or "")
                for field in ("memory_type", "key", "value", "source_phrase")
            )
        )
        hay_tokens = {token for token in haystack.split() if len(token) >= 3}
        overlap = len(query_tokens & hay_tokens)

        score = overlap * 10

        memory_type = memory.get("memory_type")
        key = memory.get("key")

        if memory_type in always_include_types:
            score += 1

        # Boosts para preguntas personales comunes.
        if key == "birthday" and (
            "cumpleaños" in query or "cumpleanos" in query or "fecha de nacimiento" in query
        ):
            score += 50

        if key == "favorite_color" and (
            "color" in query or "favorito" in query or "favorita" in query
        ):
            score += 50

        if key == "name" and "nombre" in query:
            score += 50

        scored.append((score, -index, memory))

    selected = [
        memory
        for score, _negative_index, memory in sorted(
            scored,
            key=lambda item: (item[0], item[1]),
            reverse=True,
        )
        if score > 0
    ]

    if not selected:
        selected = memories

    return selected[:limit]



def confirm_user_memory(
    store: Any,
    *,
    memory_id: int,
    source_phrase: str,
) -> dict[str, Any] | None:
    if store is None:
        return None

    ensure_user_memory_table(store)

    now = now_iso()
    normalized_source = normalize_phrase(source_phrase)

    with store.connect() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM user_memory
            WHERE id = ?
            """,
            (memory_id,),
        ).fetchone()

        if row is None:
            return None

        next_verification_count = int(row["verification_count"] or 1) + 1
        next_confidence = max(float(row["confidence"] or 0), 0.95)
        next_status = "verified" if next_verification_count >= 2 else row["status"]
        next_trust_level = (
            "trusted" if next_verification_count >= 2 else row["trust_level"]
        )

        conn.execute(
            """
            UPDATE user_memory
            SET source_phrase = ?,
                normalized_source_phrase = ?,
                confidence = ?,
                verification_count = ?,
                status = ?,
                trust_level = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                source_phrase,
                normalized_source,
                next_confidence,
                next_verification_count,
                next_status,
                next_trust_level,
                now,
                memory_id,
            ),
        )

        updated = conn.execute(
            """
            SELECT *
            FROM user_memory
            WHERE id = ?
            """,
            (memory_id,),
        ).fetchone()

    return dict(updated)


def detect_user_confirmation(text: str) -> bool:
    normalized = normalize_phrase(text)
    if not normalized:
        return False

    positive_phrases = {
        "si",
        "sí",
        "si es correcto",
        "sí es correcto",
        "correcto",
        "exacto",
        "asi es",
        "así es",
        "eso es",
        "esta correcto",
        "está correcto",
        "confirmo",
        "confirmado",
    }

    if normalized in positive_phrases:
        return True

    return any(
        phrase in normalized
        for phrase in (
            "es correcto",
            "esta correcto",
            "está correcto",
            "si correcto",
            "sí correcto",
            "asi mismo",
            "así mismo",
        )
    )
