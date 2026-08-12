"""Contract for any output sink (CSV, JSONL, database, message queue...).

export_service.py fans a batch of Items out to every configured exporter,
so adding a second sink (e.g. write to Postgres AND CSV) means adding a new
BaseExporter implementation, not touching business logic.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable


class BaseExporter(ABC):
    @abstractmethod
    def open(self) -> None:
        """Prepare the sink (open file handle, connect to DB, etc)."""
        raise NotImplementedError

    @abstractmethod
    def write_row(self, item: Any) -> None:
        """Write a single Item."""
        raise NotImplementedError

    @abstractmethod
    def write_batch(self, items: Iterable[Any]) -> None:
        """Write many Items; default implementations may just loop write_row."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Flush and release the sink."""
        raise NotImplementedError
