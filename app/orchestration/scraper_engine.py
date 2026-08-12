from __future__ import annotations

import logging

from app.models.run_outcome import RunOutcome
from app.monitoring.run_monitor import RunMonitor
from app.monitoring.scrape_statistics import ScrapeStatistics
from app.services.deduplication_service import DeduplicationService
from app.services.export_service import ExportService
from app.services.fetch_service import FetchService

BATCH_SIZE = 100


class ScraperEngine:
    """Thin coordinator: begin_run -> fetch -> dedup -> export -> end_run.

    This is the ONE orchestrator file for the project -- brand discovery,
    per-page crawling, and total-count lookups all live inside
    FetchService (the "adapt per project" file); this class stays generic
    and just wires monitoring around the same fetch -> dedup -> export
    loop the base skeleton uses.
    """

    def __init__(
        self,
        fetch_service: FetchService,
        dedup_service: DeduplicationService,
        export_service: ExportService,
        statistics: ScrapeStatistics,
        monitor: RunMonitor,
        logger: logging.Logger | None = None,
    ) -> None:
        self.fetch_service = fetch_service
        self.dedup_service = dedup_service
        self.export_service = export_service
        self.statistics = statistics
        self.monitor = monitor
        self.logger = logger or logging.getLogger("scraper")

    def run(self) -> RunOutcome:
        self.monitor.start()
        self.dedup_service.begin_run()
        self.export_service.start()

        total_exported = 0
        outcome = RunOutcome.COMPLETED
        batch: list = []

        try:
            for item in self.fetch_service.fetch_all():
                if not self.dedup_service.is_new(item):
                    self.statistics.duplicates_skipped += 1
                    continue
                batch.append(item)
                self.statistics.items_scraped += 1
                if len(batch) >= BATCH_SIZE:
                    total_exported += self.export_service.export_batch(batch)
                    batch = []

            if batch:
                total_exported += self.export_service.export_batch(batch)

        except KeyboardInterrupt:
            self.logger.warning("Run interrupted by user (Ctrl-C)")
            if batch:
                total_exported += self.export_service.export_batch(batch)
            outcome = RunOutcome.INTERRUPTED

        except Exception:
            self.logger.exception("Run interrupted by unhandled error")
            if batch:
                total_exported += self.export_service.export_batch(batch)
            outcome = RunOutcome.INTERRUPTED

        finally:
            self.export_service.finish()
            self.dedup_service.end_run()

        expected = None
        try:
            expected = self.fetch_service.get_total_expected()
        except Exception:
            self.logger.warning("Could not fetch expected total for coverage report.")

        self.monitor.finish(
            outcome=outcome,
            scraped=len(self.dedup_service._seen),  # cumulative across runs, matches `expected`
            expected=expected,
        )
        
        self.logger.info("Run finished: outcome=%s, exported=%s", outcome.name, total_exported)
        return outcome
