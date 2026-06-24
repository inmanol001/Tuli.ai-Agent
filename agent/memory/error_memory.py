from agent.memory.sqlite_store import SQLiteStore


def record_error_memory(
    store: SQLiteStore,
    *,
    error: str | None,
    source: str,
    solution: str | None = None,
) -> None:
    if not error:
        return
    store.record_error(error=error, source=source, solution=solution)
