from agent.memory.sqlite_store import SQLiteStore
from agent.memory.learning_memory import load_learning_memory
from agent.memory.memory_writer import record_learning_from_completed_turn


def test_memory_writer_records_successful_tool_result(tmp_path):
    store = SQLiteStore(str(tmp_path / "memory.sqlite3"))

    response = {
        "tool_calls": [
            {
                "tool_name": "browser_search",
                "arguments": {
                    "query": "https://docs.ollama.com",
                    "target": "url",
                },
            }
        ],
        "debug": {
            "context": {
                "router_decision": {
                    "intent": "action",
                },
                "selected_skills": [
                    {
                        "name": "browser_search",
                    }
                ],
            },
            "tool_result": {
                "tool_name": "browser_search",
                "success": True,
                "data": {
                    "url": "https://docs.ollama.com",
                },
            },
        },
    }

    recorded = record_learning_from_completed_turn(
        store,
        user_message="abre el primero",
        response=response,
    )

    assert recorded is True

    rows = load_learning_memory(store, phrase="abre el primero")
    assert len(rows) == 1
    assert rows[0]["correct_intent"] == "action"
    assert rows[0]["correct_tool"] == "browser_search"
    assert rows[0]["correct_skill"] == "browser_search"
    assert rows[0]["status"] == "temporary"
    assert rows[0]["success_count"] == 1


def test_memory_writer_does_not_record_failed_tool_result(tmp_path):
    store = SQLiteStore(str(tmp_path / "memory.sqlite3"))

    response = {
        "tool_calls": [
            {
                "tool_name": "open_app",
                "arguments": {
                    "app_name": "Figma",
                },
            }
        ],
        "debug": {
            "tool_result": {
                "tool_name": "open_app",
                "success": False,
                "error": "app not found",
            },
        },
    }

    recorded = record_learning_from_completed_turn(
        store,
        user_message="abre Figma",
        response=response,
    )

    assert recorded is False
    assert load_learning_memory(store, phrase="abre Figma") == []


def test_memory_writer_promotes_repeated_success_to_candidate(tmp_path):
    store = SQLiteStore(str(tmp_path / "memory.sqlite3"))

    response = {
        "tool_calls": [
            {
                "tool_name": "browser_search",
                "arguments": {
                    "query": "https://docs.ollama.com",
                    "target": "url",
                },
            }
        ],
        "debug": {
            "tool_result": {
                "tool_name": "browser_search",
                "success": True,
                "data": {
                    "url": "https://docs.ollama.com",
                },
            },
        },
    }

    record_learning_from_completed_turn(
        store,
        user_message="abre el primero",
        response=response,
    )
    record_learning_from_completed_turn(
        store,
        user_message="abre el primero",
        response=response,
    )

    rows = load_learning_memory(store, phrase="abre el primero")
    assert len(rows) == 1
    assert rows[0]["status"] == "candidate"
    assert rows[0]["usage_count"] == 2
    assert rows[0]["success_count"] == 2
