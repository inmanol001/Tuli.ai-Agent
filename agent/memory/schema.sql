CREATE TABLE IF NOT EXISTS session_state (
    session_id TEXT PRIMARY KEY,
    previous_route TEXT,
    current_route TEXT,
    pending_clarification TEXT,
    pending_confirmation_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_turns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    turn_index INTEGER NOT NULL,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    confidence REAL NOT NULL,
    source TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tool_memory (
    tool_name TEXT PRIMARY KEY,
    notes TEXT,
    success_count INTEGER NOT NULL DEFAULT 0,
    fail_count INTEGER NOT NULL DEFAULT 0,
    last_input_json TEXT,
    last_result_summary TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS error_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    error TEXT NOT NULL,
    solution TEXT,
    source TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS conversation_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    summary TEXT NOT NULL,
    created_at TEXT NOT NULL
);
