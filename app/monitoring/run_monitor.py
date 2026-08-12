"""
Not present in the base skeleton -- added because the base ScraperEngine
only logs a one-line "Run finished" summary. This gives the richer
end-of-run report the old project had (coverage vs expected catalogue
size, brands/pages/requests counts, duplicates, elapsed time).
"""
from __future__ import annotations

import logging
import time

from app.models.run_outcome import RunOutcome
from app.monitoring.scrape_statistics import ScrapeStatistics


class RunMonitor:
    """Tracks wall-clock time for a scrape run and logs a final summary."""

    def __init__(self, logger: logging.Logger, statistics: ScrapeStatistics) -> None:
        self._logger = logger
        self._statistics = statistics
        self._start_time: float | None = None

    def start(self) -> None:
        self._start_time = time.time()
        self._logger.info("Scrape started.")

    def finish(
        self,
        outcome: RunOutcome,
        scraped: int,
        expected: int | None = None,
    ) -> None:
        elapsed = time.time() - (self._start_time or time.time())
        coverage = f"{scraped / expected * 100:.1f}%" if expected else "N/A"

        self._logger.info("=== FINAL REPORT ===")
        self._logger.info("Outcome            : %s", outcome.name)
        self._logger.info("Expected items      : %s", expected if expected is not None else "N/A")
        self._logger.info("Items scraped       : %d", scraped)
        self._logger.info("Coverage            : %s", coverage)
        self._logger.info("Brands discovered   : %d", self._statistics.brands_discovered)
        self._logger.info("Brands completed    : %d", self._statistics.brands_completed)
        self._logger.info("Requests sent       : %d", self._statistics.requests_sent)
        self._logger.info("Pages crawled       : %d", self._statistics.pages_crawled)
        self._logger.info("Duplicates skipped  : %d", self._statistics.duplicates_skipped)
        self._logger.info("Items failed        : %d", self._statistics.items_failed)
        self._logger.info("Elapsed             : %.2fs", elapsed)
