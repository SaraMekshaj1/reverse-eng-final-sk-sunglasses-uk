from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Iterator


class FailedItemStore:
    """Append-only JSONL log of records that failed at some stage (fetch,
    parse, export), so they can be replayed later via scripts/retry_failed_items.py
    instead of being lost when a run ends.

    Each line: {"stage": "parse", "reason": "...", "raw": {...}, "run_id": "..."}
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def record(self, stage: str, reason: str, raw: Any, run_id: str = "") -> None:
        entry = {"stage": stage, "reason": reason, "raw": raw, "run_id": run_id}
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(entry, default=str) + "\n")

    def iter_entries(self) -> Iterator[dict[str, Any]]:
        if not self.path.exists():
            return
        with self.path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    yield json.loads(line)

    def clear(self) -> None:
        with self._lock:
            if self.path.exists():
                self.path.unlink()
