"""
Composition root. This is the ONLY file that should import concrete
implementations and wire them together. Everything else in `app/` depends
only on the abstractions (BaseApiClient, BaseCheckpointStore, etc) or on
plain dataclasses.

To swap an implementation (e.g. GenericApiClient -> BrowserBackedApiClient,
or add a Postgres exporter alongside CSV/JSON), change it here and nowhere
else.
"""
from __future__ import annotations
import logging
from app.client.generic_api_client import GenericApiClient
from app.config.settings import Settings
from app.exporters.csv_exporter import CsvExporter
from app.exporters.json_exporter import JsonExporter
from app.monitoring.run_monitor import RunMonitor
from app.monitoring.scrape_statistics import ScrapeStatistics
from app.orchestration.scraper_engine import ScraperEngine
from app.parsers.item_parser import ItemParser
from app.services.deduplication_service import DeduplicationService
from app.services.export_service import ExportService
from app.services.fetch_service import FetchService
from app.storage.checkpoint_store import JsonCheckpointStore
from app.storage.failed_item_store import FailedItemStore
from app.utils.logger import setup_logger


class Container:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.settings.ensure_dirs()
        self.logger: logging.Logger = setup_logger(
            level=self.settings.log_level, log_file=self.settings.log_file,
        )
        self.statistics = ScrapeStatistics()

        self.api_client = GenericApiClient(
            headers=self.settings.headers,
            timeout_seconds=self.settings.timeout_seconds,
            max_retries=self.settings.max_retries,
            backoff_factor=self.settings.backoff_factor,
            status_forcelist=self.settings.status_forcelist,
            circuit_breaker_failure_threshold=self.settings.circuit_breaker_failure_threshold,
            circuit_breaker_reset_seconds=self.settings.circuit_breaker_reset_seconds,
            requests_per_second=self.settings.requests_per_second,
            logger=self.logger,
        )

        self.hit_parser = ItemParser()

        self.checkpoint_store = JsonCheckpointStore(
            checkpoint_dir=self.settings.checkpoint_dir,
            run_id=self.settings.run_id,
        )

        self.failed_item_store = FailedItemStore(path=self.settings.failed_items_path)


        self.fetch_service = FetchService(
            api_client=self.api_client,
            hit_parser=self.hit_parser,
            checkpoint_store=self.checkpoint_store,
            failed_item_store=self.failed_item_store,
            statistics=self.statistics,
            settings=self.settings,
            logger=self.logger,
        )

        self.dedup_service = DeduplicationService(
            state_path=self.settings.dedup_state_path,
            logger=self.logger,
        )

        self.csv_exporter = CsvExporter(output_path=self.settings.output_csv_path)
        self.json_exporter = JsonExporter(output_path=self.settings.output_json_path)
        self.export_service = ExportService(
            exporters=[self.csv_exporter, self.json_exporter],
            logger=self.logger,
        )

        self.monitor = RunMonitor(logger=self.logger, statistics=self.statistics)

        self.engine = ScraperEngine(
            fetch_service=self.fetch_service,
            dedup_service=self.dedup_service,
            export_service=self.export_service,
            statistics=self.statistics,
            monitor=self.monitor,
            logger=self.logger,
        )

    def close(self) -> None:
        self.api_client.close()
