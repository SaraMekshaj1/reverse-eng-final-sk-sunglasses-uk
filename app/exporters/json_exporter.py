"""
New exporter, not in the original skeleton -- added to fan out alongside
CsvExporter (ExportService already supports multiple sinks, so no other
code needed to change).

Written as append-only JSONL rather than a single JSON array dump (which is
what the old JSONExporter did). A single big JSON array can't be resumed
safely -- re-running after an interruption would either clobber the file or
require loading + re-serializing the whole thing. JSONL matches CsvExporter's
resume-safe append behavior: each line is one Item, dedup already prevents
re-writing rows you've seen before.

If you specifically need a single valid `.json` array file for some
downstream consumer, convert at the end with a short script, or ask and
I'll add a "compact on close" mode.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from app.abstraction.base_exporter import BaseExporter


class JsonExporter(BaseExporter):
    def __init__(self, output_path: Path) -> None:
        self.output_path = Path(output_path)
        self._file = None

    def open(self) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.output_path.open("a", encoding="utf-8")

    def write_row(self, item: Any) -> None:
        row = item.to_row() if hasattr(item, "to_row") else dict(item)
        self._file.write(json.dumps(row, default=str, ensure_ascii=False) + "\n")

    def write_batch(self, items: Iterable[Any]) -> None:
        for item in items:
            self.write_row(item)
        if self._file:
            self._file.flush()

    def close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None
