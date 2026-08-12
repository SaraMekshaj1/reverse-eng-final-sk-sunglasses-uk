"""Contract for turning one raw API record into one typed Item.

This is the other file (besides Settings + Item) that changes on nearly
every project, because every API's JSON shape is different.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseHitParser(ABC):
    @abstractmethod
    def parse(self, raw_record: dict[str, Any]) -> Any:
        """Convert one raw record (a dict from the API response) into an Item.

        Should raise on unrecoverable shape mismatches so the caller can
        route the raw record to the failed-item store instead of silently
        producing a broken Item.
        """
        raise NotImplementedError
