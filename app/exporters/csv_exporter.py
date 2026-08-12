from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Iterable

from app.abstraction.base_exporter import BaseExporter


class CsvExporter(BaseExporter):
    """Appends rows to a CSV file. Resume-safe: if the file already exists
    (from a previous interrupted run) it does NOT rewrite the header, it
    just keeps appending -- combined with DeduplicationService this means
    re-running after an interruption won't duplicate rows.
    """

    def __init__(self, output_path: Path, fieldnames: list[str] | None = None) -> None:
        self.output_path = Path(output_path)
        self.fieldnames = fieldnames
        self._file = None
        self._writer: csv.DictWriter | None = None

    def open(self) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        file_exists = self.output_path.exists() and self.output_path.stat().st_size > 0
        self._file = self.output_path.open("a", newline="", encoding="utf-8")
        if self.fieldnames:
            self._writer = csv.DictWriter(self._file, fieldnames=self.fieldnames)
            if not file_exists:
                self._writer.writeheader()

    def write_row(self, item: Any) -> None:
        row = item.to_row() if hasattr(item, "to_row") else dict(item)
        if self._writer is None:
            # first row defines the header if none was given up front
            self.fieldnames = list(row.keys())
            self._writer = csv.DictWriter(self._file, fieldnames=self.fieldnames)
            if self._file.tell() == 0:
                self._writer.writeheader()
        self._writer.writerow(row)

    def write_batch(self, items: Iterable[Any]) -> None:
        for item in items:
            self.write_row(item)
        if self._file:
            self._file.flush()

    def close(self) -> None:
        if self._file:
            self._file.close()
            self._file = None
            self._writer = None
