CREATE TABLE IF NOT EXISTS session_state (
    session_id TEXT PRIMARY KEY,
    previous_route TEXT,
    current_route TEXT,
    pending_clarification TEXT,
    pending_confirmation_json TEXT,
    pending_workflow_json TEXT,
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

CREATE TABLE IF NOT EXISTS learning_memory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    user_phrase TEXT NOT NULL,
    normalized_phrase TEXT NOT NULL,

    correct_intent TEXT NOT NULL,
    correct_tool TEXT,
    correct_skill TEXT,

    confidence REAL NOT NULL DEFAULT 0.0,
    status TEXT NOT NULL DEFAULT 'temporary',

    source TEXT NOT NULL DEFAULT 'runtime',
    evidence_json TEXT,
    notes TEXT,

    usage_count INTEGER NOT NULL DEFAULT 0,
    success_count INTEGER NOT NULL DEFAULT 0,
    failure_count INTEGER NOT NULL DEFAULT 0,

    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    verified_at TEXT,

    UNIQUE(normalized_phrase, correct_intent, correct_tool, correct_skill)
);

CREATE INDEX IF NOT EXISTS idx_learning_memory_phrase
ON learning_memory(normalized_phrase);

CREATE INDEX IF NOT EXISTS idx_learning_memory_status
ON learning_memory(status);

CREATE INDEX IF NOT EXISTS idx_learning_memory_tool
ON learning_memory(correct_tool);
