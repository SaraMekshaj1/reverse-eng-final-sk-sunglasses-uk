from __future__ import annotations

import json
import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Iterable

from app.abstraction.base_checkpoint_store import BaseCheckpointStore


class JsonCheckpointStore(BaseCheckpointStore):
    """Default checkpoint store: one JSON file per run, holding a flat key/value
    map (e.g. {"last_page": 12, "run_status": "in_progress"}).

    Simple, human-inspectable, good enough until a project needs multi-worker
    shared state -- at which point swap in a Sqlite- or Redis-backed store
    that satisfies the same BaseCheckpointStore contract.
    """

    def __init__(
        self,
        checkpoint_dir: Path,
        run_id: str,
        logger: logging.Logger | None = None,
    ) -> None:
        self.path = Path(checkpoint_dir) / f"{run_id}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.logger = logger or logging.getLogger("scraper")
        self._lock = threading.Lock()
        self._data: dict[str, Any] = self._read()

    def _read(self) -> dict[str, Any]:
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _flush(self) -> None:
        # Unique tmp filename per write (not a shared "<name>.tmp") so two
        # rapid-fire flushes can never collide with each other's temp file.
        tmp_path = self.path.with_suffix(f".{uuid.uuid4().hex}.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, default=str)

        # os.replace is atomic on POSIX but on Windows it can raise
        # PermissionError if something else (almost always Defender's
        # real-time scanner) has a transient handle on the destination file
        # at that instant. Checkpoints save on every page, so with dozens of
        # writes per second that race gets hit sooner or later. Retry with
        # backoff; if it never clears, drop this one write rather than
        # crashing the whole run -- the in-memory state is still correct
        # and the next successful flush will catch up.
        attempts = 5
        delay = 0.05
        for attempt in range(1, attempts + 1):
            try:
                tmp_path.replace(self.path)
                return
            except PermissionError as exc:
                if attempt == attempts:
                    self.logger.warning(
                        "Checkpoint write skipped after %d attempts (locked by "
                        "another process, likely antivirus): %s", attempts, exc,
                    )
                    tmp_path.unlink(missing_ok=True)
                    return
                time.sleep(delay)
                delay *= 2

    def save(self, key: str, value: Any) -> None:
        with self._lock:
            self._data[key] = value
            self._flush()

    def load(self, key: str, default: Any = None) -> Any:
        with self._lock:
            return self._data.get(key, default)

    def exists(self, key: str) -> bool:
        with self._lock:
            return key in self._data

    def delete(self, key: str) -> None:
        with self._lock:
            self._data.pop(key, None)
            self._flush()

    def keys(self) -> Iterable[str]:
        with self._lock:
            return list(self._data.keys())
