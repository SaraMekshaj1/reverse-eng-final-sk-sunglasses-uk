"""
Not present in the base skeleton -- added because this project needs
cross-cutting counters (brands discovered, pages crawled, etc) that don't
belong to any single service but are updated by several of them.

This object is shared between FetchService (which increments most counters)
and RunMonitor (which reports them). It's a plain mutable dataclass rather
than going through the checkpoint store, since these are report-only stats
for a single run, not resume state.
"""
from __future__ import annotations
from dataclasses import dataclass

@dataclass
class ScrapeStatistics:
    # Discovery
    brands_discovered: int = 0
    brands_completed: int = 0

    # Networking
    requests_sent: int = 0

    # Crawling
    pages_crawled: int = 0

    # Items
    items_scraped: int = 0
    duplicates_skipped: int = 0
    items_failed: int = 0
