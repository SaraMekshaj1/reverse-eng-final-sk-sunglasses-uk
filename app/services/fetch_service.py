"""
ADAPT THIS FILE per project -- this is the project-specific fetch driver.

Algolia caps hits per single query, so a flat SimplePaginator can't reach
every product: the old project worked around this with BrandService
(discover facet values) + CrawlService (page through each brand's slice).
That two-level pattern is what `SimplePaginator`'s docstring calls out as
needing "the harder case" (see discovery_batch_paginator.py mentioned
there) -- so instead of forcing SimplePaginator to do two passes, this
project gets its own FetchService that drives discovery + per-brand
pagination directly.

Resumability: checkpoints track which brands are fully completed, plus
the in-progress brand/page, so a restarted run skips finished brands and
resumes mid-brand instead of re-crawling from scratch.
"""
from __future__ import annotations

import logging
from typing import Any, Iterator

from app.abstraction.base_api_client import BaseApiClient
from app.abstraction.base_checkpoint_store import BaseCheckpointStore
from app.abstraction.base_hit_parser import BaseHitParser
from app.config.settings import Settings
from app.exceptions.scraper_exceptions import ParseError
from app.monitoring.scrape_statistics import ScrapeStatistics
from app.storage.failed_item_store import FailedItemStore


class FetchService:
    CHECKPOINT_COMPLETED_BRANDS_KEY = "completed_brands"
    CHECKPOINT_CURRENT_BRAND_KEY = "current_brand"
    CHECKPOINT_CURRENT_PAGE_KEY = "current_page"

    def __init__(
        self,
        api_client: BaseApiClient,
        hit_parser: BaseHitParser,
        checkpoint_store: BaseCheckpointStore,
        failed_item_store: FailedItemStore,
        statistics: ScrapeStatistics,
        settings: Settings,
        logger: logging.Logger | None = None,
    ) -> None:
        self.api_client = api_client
        self.hit_parser = hit_parser
        self.checkpoint_store = checkpoint_store
        self.failed_item_store = failed_item_store
        self.statistics = statistics
        self.settings = settings
        self.run_id = settings.run_id
        self.logger = logger or logging.getLogger("scraper")

    # --- public: driven by ScraperEngine --------------------------------

    def fetch_all(self) -> Iterator[Any]:
        brands = self._discover_brands()
        self.statistics.brands_discovered = len(brands)
        self.logger.info("Discovered %d brands.", len(brands))

        completed = set(self.checkpoint_store.load(self.CHECKPOINT_COMPLETED_BRANDS_KEY, []))
        self.statistics.brands_completed += len(completed)  # ADD: credit already-done brands

        resume_brand = self.checkpoint_store.load(self.CHECKPOINT_CURRENT_BRAND_KEY)
        resume_page = self.checkpoint_store.load(self.CHECKPOINT_CURRENT_PAGE_KEY, 0)

        for brand in brands:
            if brand in completed:
                continue
            start_page = resume_page if brand == resume_brand else 0
            yield from self._crawl_brand(brand, start_page, completed)

    #catalogue service
    def get_total_expected(self) -> int:
        """Total nbHits reported by the index across all brands/variants.
        Used by RunMonitor to report coverage at the end of a run.
        """
        payload = {
            "requests": [
                {
                    "indexName": self.settings.index_name,
                    "query": "",
                    "hitsPerPage": 0,
                }
            ]
        }
        response = self.api_client.post(self.settings.base_url, json_body=payload)
        self.statistics.requests_sent += 1
        return response["results"][0].get("nbHits", 0)

    # --- internal: discovery ---------------------------------------------

    def _discover_brands(self) -> list[str]:
        payload = {
            "requests": [
                {
                    "indexName": self.settings.index_name,
                    "query": "",
                    "facets": [self.settings.facet_field],
                    "hitsPerPage": 0,
                }
            ]
        }
        response = self.api_client.post(self.settings.base_url, json_body=payload)
        self.statistics.requests_sent += 1
        facets = response["results"][0]["facets"].get(self.settings.facet_field, {})
        return sorted(facets.keys())

    #crawl+service
    # --- internal: per-brand pagination -----------------------------------
    def _crawl_brand(self, brand: str, start_page: int, completed: set[str]) -> Iterator[Any]:
        page = start_page
        while True:
            payload = {"requests": [self._build_request(brand, page)]}
            self.logger.info("Fetching brand=%s page=%s", brand, page)

            try:
                response = self.api_client.post(self.settings.base_url, json_body=payload)
                self.statistics.requests_sent += 1
            except Exception as exc:
                self.logger.error("Fetch failed brand=%s page=%s: %s", brand, page, exc)
                self.failed_item_store.record(
                    stage="fetch",
                    reason=str(exc),
                    raw={"brand": brand, "page": page},
                    run_id=self.run_id,
                )
                # Save progress so a retry resumes here instead of the
                # whole brand from scratch; don't mark this brand completed.
                self.checkpoint_store.save(self.CHECKPOINT_CURRENT_BRAND_KEY, brand)
                self.checkpoint_store.save(self.CHECKPOINT_CURRENT_PAGE_KEY, page)
                return

            results = response["results"][0]
            hits = results.get("hits", [])
            nb_pages = results.get("nbPages", 0)
            nb_hits = results.get("nbHits", 0)

            if page == start_page:
                self.logger.info("%s : %d products (%d pages)", brand, nb_hits, nb_pages)

            if not hits:
                break

            self.statistics.pages_crawled += 1

            for raw_record in hits:
                try:
                    item = self.hit_parser.parse(raw_record)
                except ParseError as exc:
                    self.logger.warning("Parse failed brand=%s page=%s: %s", brand, page, exc)
                    self.failed_item_store.record(
                        stage="parse", reason=str(exc), raw=raw_record, run_id=self.run_id,
                    )
                    self.statistics.items_failed += 1
                    continue

                if not item.is_valid():
                    self.failed_item_store.record(
                        stage="validate", reason="is_valid() returned False",
                        raw=raw_record, run_id=self.run_id,
                    )
                    self.statistics.items_failed += 1
                    continue

                yield item

            # checkpoint progress within this brand before deciding next step
            self.checkpoint_store.save(self.CHECKPOINT_CURRENT_BRAND_KEY, brand)
            self.checkpoint_store.save(self.CHECKPOINT_CURRENT_PAGE_KEY, page)

            page += 1
            if page >= nb_pages:
                break

        # brand fully crawled -- mark completed, clear in-progress markers
        completed.add(brand)
        self.checkpoint_store.save(self.CHECKPOINT_COMPLETED_BRANDS_KEY, sorted(completed))
        self.checkpoint_store.delete(self.CHECKPOINT_CURRENT_BRAND_KEY)
        self.checkpoint_store.delete(self.CHECKPOINT_CURRENT_PAGE_KEY)
        self.statistics.brands_completed += 1

    def _build_request(self, brand: str, page: int) -> dict[str, Any]:
        filters = f'{self.settings.brand_filter_field}:"{brand}"'
        if self.settings.category_filter:
            filters = f"{filters} AND {self.settings.category_filter}"
        return {
            "indexName": self.settings.index_name,
            "query": "",
            "hitsPerPage": self.settings.hits_per_page,
            "page": page,
            "filters": filters,
        }
