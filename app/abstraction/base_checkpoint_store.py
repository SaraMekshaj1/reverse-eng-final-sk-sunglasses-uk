"""Contract for anything that persists "where the run got to" so it can resume.

Default implementation is JSON-file-backed (storage/checkpoint_store.py).
Swap for a Sqlite- or Redis-backed store (Tier 2) without touching fetch_service.py.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Iterable


class BaseCheckpointStore(ABC):
    @abstractmethod
    def save(self, key: str, value: Any) -> None:
        """Persist `value` under `key` (overwrites any existing value)."""
        raise NotImplementedError

    @abstractmethod
    def load(self, key: str, default: Any = None) -> Any:
        """Return the value stored under `key`, or `default` if absent."""
        raise NotImplementedError

    @abstractmethod
    def exists(self, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError

    @abstractmethod
    def keys(self) -> Iterable[str]:
        raise NotImplementedError
