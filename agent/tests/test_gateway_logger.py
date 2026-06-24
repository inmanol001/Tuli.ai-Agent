import json

from agent.gateway.gateway_logger import GatewayLogger


def test_gateway_logger_writes_jsonl(tmp_path):
    logger = GatewayLogger(tmp_path)
    logger.write("events", {"event": "test", "value": 1})
    content = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip()
    payload = json.loads(content)
    assert payload["event"] == "test"
    assert payload["value"] == 1
    assert "timestamp" in payload
