"""
ADAPT THIS FILE FIRST for every new project.

This instance is wired for the Sunglass Hut Algolia storefront index.
Nothing else in the app should hardcode these values -- everything pulls
from an instance of `Settings`, built once in container.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    # --- target API -------------------------------------------------
    base_url: str = "https://21ogkm5th5-dsn.algolia.net/1/indexes/*/queries"
    request_method: str = "POST"  # Algolia's query endpoint is POST-only
    index_name: str = "prod_live_sgh_en-gb__grouped"

    # Set to a non-empty Algolia filter string (e.g. 'categories: gender_male')
    # to scope every brand-crawl query; leave "" to crawl everything.
    category_filter: str = ""

    # Static headers copied from the browser's Network tab.
    headers: dict = field(default_factory=lambda: {
        "User-Agent": "Mozilla/5.0",
        "Content-Type": "application/json",
        "x-algolia-application-id": "21OGKM5TH5",
        "x-algolia-api-key": "dc91173a4a5d669a3eef474e5836e94f",
        "Origin": "https://www.sunglasshut.com",
        "Referer": "https://www.sunglasshut.com/",
    })

    # --- discovery + pagination -----------------------------------------
    # Algolia caps hits per single query, so we can't just page through the
    # whole index -- we discover facet values (brands) first, then page
    # through each brand's slice individually. See fetch_service.py.
    facet_field: str = "attributes.BRAND"
    brand_filter_field: str = "attributes.BRAND"
    hits_per_page: int = 100

    # --- networking / resilience --------------------------------------
    timeout_seconds: float = 30.0
    max_retries: int = 5
    backoff_factor: float = 2.0
    status_forcelist: tuple = (429, 500, 502, 503, 504)

    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_reset_seconds: float = 60.0

    requests_per_second: float | None = 5.0

    # --- run identity / storage ----------------------------------------
    run_id: str = "sunglasshut-run"
    data_dir: Path = Path("data")

    output_csv_path: Path | None = None
    output_json_path: Path | None = None
    checkpoint_dir: Path | None = None
    failed_items_path: Path | None = None
    dedup_state_path: Path | None = None
    log_file: Path | None = None

    log_level: str = "INFO"

    def __post_init__(self) -> None:
        if self.output_csv_path is None:
            object.__setattr__(self, "output_csv_path", self.data_dir / "products.csv")
        if self.output_json_path is None:
            object.__setattr__(self, "output_json_path", self.data_dir / "products.json")
        if self.checkpoint_dir is None:
            object.__setattr__(self, "checkpoint_dir", self.data_dir / "checkpoints")
        if self.failed_items_path is None:
            object.__setattr__(self, "failed_items_path", self.data_dir / "failed_items.jsonl")
        if self.dedup_state_path is None:
            object.__setattr__(self, "dedup_state_path", self.data_dir / "dedup_keys.json")
        if self.log_file is None:
            object.__setattr__(self, "log_file", self.data_dir / "scraper.log")

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
