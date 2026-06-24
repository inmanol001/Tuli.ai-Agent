import re

from agent.memory.sqlite_store import SQLiteStore


SHORT_REPLY_RE = re.compile(r"\b(respondeme|respóndeme)\s+corto\b", re.I)
SPANISH_RE = re.compile(r"\bprefiero\s+respuestas\s+en\s+español\b", re.I)
CALL_ME_RE = re.compile(r"\b(llamame|llámame)\s+([A-Za-zÁÉÍÓÚÑáéíóúñ'-]{2,40})\b", re.I)


def capture_explicit_preferences(text: str, store: SQLiteStore) -> None:
    if SHORT_REPLY_RE.search(text):
        store.upsert_preference(
            key="response_length",
            value="short",
            confidence=1.0,
            source="explicit_user_message",
        )
    if SPANISH_RE.search(text):
        store.upsert_preference(
            key="language",
            value="es",
            confidence=1.0,
            source="explicit_user_message",
        )
    match = CALL_ME_RE.search(text)
    if match:
        store.upsert_preference(
            key="preferred_name",
            value=match.group(2),
            confidence=1.0,
            source="explicit_user_message",
        )
