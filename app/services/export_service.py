from __future__ import annotations

import logging
from typing import Any, Iterable

from app.abstraction.base_exporter import BaseExporter


class ExportService:
    """Owns the exporter lifecycle and fans batches out to every configured
    sink. Adding a second output (e.g. CSV + JSON) means passing a second
    BaseExporter into `exporters`, not touching this class.
    """

    def __init__(self, exporters: list[BaseExporter], logger: logging.Logger | None = None) -> None:
        self.exporters = exporters
        self.logger = logger or logging.getLogger("scraper")

    def start(self) -> None:
        for exporter in self.exporters:
            exporter.open()

    def export_batch(self, items: Iterable[Any]) -> int:
        items = list(items)
        if not items:
            return 0
        for exporter in self.exporters:
            exporter.write_batch(items)
        self.logger.info("Exported batch of %s items", len(items))
        return len(items)

    def finish(self) -> None:
        for exporter in self.exporters:
            exporter.close()
