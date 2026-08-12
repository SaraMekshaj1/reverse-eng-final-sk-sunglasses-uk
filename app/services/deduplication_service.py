from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any


class DeduplicationService:
    """Generic key-based dedup, persisted to disk so it survives across
    interrupted/resumed runs (not just within one process).

    Lifecycle:
        begin_run()  -> load previously seen keys from disk
        is_new(item) -> True the first time a key is seen, False after
        end_run()    -> flush seen keys back to disk
    """

    def __init__(self, state_path: Path, logger: logging.Logger | None = None) -> None:
        self.state_path = Path(state_path)
        self.logger = logger or logging.getLogger("scraper")
        self._seen: set[str] = set()
        self._lock = threading.Lock()
        self._dirty = False

    def begin_run(self) -> None:
        if self.state_path.exists():
            with self.state_path.open("r", encoding="utf-8") as f:
                self._seen = set(json.load(f))
            self.logger.info("Dedup state loaded: %s known keys", len(self._seen))
        else:
            self._seen = set()

    def is_new(self, item: Any) -> bool:
        key = item.dedup_key() if hasattr(item, "dedup_key") else str(item)
        with self._lock:
            if key in self._seen:
                return False
            self._seen.add(key)
            self._dirty = True
            return True

    def end_run(self) -> None:
        if not self._dirty:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        # Unique tmp filename + retry: same Windows PermissionError race as
        # JsonCheckpointStore -- Defender's real-time scanner can grab a
        # transient handle on the destination right as we try to replace it.
        tmp_path = self.state_path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(sorted(self._seen), f)

        attempts = 5
        delay = 0.05
        for attempt in range(1, attempts + 1):
            try:
                tmp_path.replace(self.state_path)
                break
            except PermissionError as exc:
                if attempt == attempts:
                    self.logger.warning(
                        "Dedup state write failed after %d attempts (locked by "
                        "another process, likely antivirus): %s", attempts, exc,
                    )
                    tmp_path.unlink(missing_ok=True)
                    return
                time.sleep(delay)
                delay *= 2
        self.logger.info("Dedup state saved: %s known keys", len(self._seen))
