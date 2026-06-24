import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class GatewayLogger:
    def __init__(self, log_dir: str | Path = "agent/logs") -> None:
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def write(self, stream: str, event: dict[str, Any] | BaseModel) -> None:
        path = self.log_dir / f"{stream}.jsonl"
        payload = event.model_dump(mode="json") if isinstance(event, BaseModel) else event
        payload = {"timestamp": datetime.now(UTC).isoformat(), **payload}
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True) + "\n")

