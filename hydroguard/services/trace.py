"""JSONL trace with an allowlist: raw input and exception messages are never logged."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from hydroguard.data.sample import source_registry


class RunTrace:
    def __init__(self, log_dir: Path | None = None):
        self.run_id = str(uuid4())
        directory = Path(log_dir or os.environ.get("HYDROGUARD_LOG_DIR", "logs"))
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"{self.run_id}.jsonl"
        self.sequence = 0
        self.mode = "offline_rule_based" if os.environ.get("SAMPLE_MODE", "true").lower() == "true" else "live_unavailable"
        self.safe_sources = frozenset(source_registry())

    def emit(self, agent: str, event: str, status: str = "completed", *,
             source_ids=(), retry: int = 0, handoff: str | None = None,
             decision: str | None = None, passed: bool | None = None):
        self.sequence += 1
        record = {"run_id": self.run_id, "sequence": self.sequence,
                  "timestamp": datetime.now(timezone.utc).isoformat(),
                  "mode": self.mode, "agent": agent, "event": event,
                  "status": status, "retry": retry,
                  "source_ids": [s if s in self.safe_sources else "[redacted]" for s in source_ids]}
        if handoff is not None:
            record["handoff"] = handoff
        if decision is not None:
            record["decision"] = decision
        if passed is not None:
            record["passed"] = passed
        line = json.dumps(record, separators=(",", ":"))
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")
        print(line, flush=True)
