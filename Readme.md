# Sunglass Hut Product Scraper
**Python • Requests • Algolia API • Reverse Engineering**

A production-grade scraper that collects the full Sunglass Hut product catalogue by reverse-engineering the Algolia search API the website uses internally — delivering cleaner data, faster, and without the fragility of HTML parsing.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Requests](https://img.shields.io/badge/Requests-Latest-green)
![Algolia](https://img.shields.io/badge/Algolia-Reverse--Engineered-orange)
![License](https://img.shields.io/badge/License-MIT-red)

---

## Project highlights

- Collected **4,641 unique products** across **48 brands**
- **100% catalogue coverage** — every product matched the expected count
- **72 API requests** to fetch the entire catalogue
- Completed in **15.7 seconds**
- Zero duplicates, zero missed products
- Exports to both **CSV** and **JSON**
- Automatic retries with exponential backoff, plus a circuit breaker for sustained failures
- Checkpointed and resumable — an interrupted run picks up mid-brand instead of starting over
- Failed items are recorded and can be replayed without a full re-scrape

---

## Overview

Most scrapers parse HTML — they find elements on the page by their CSS class or position. This works but breaks easily: one website redesign and the scraper stops working.

This scraper takes a different approach. When you browse Sunglass Hut, your browser quietly makes requests to a search service called **Algolia** in the background. Algolia sends back clean, structured JSON. This scraper sends the same requests your browser does, gets the same data back, and saves it — no HTML parsing, no browser automation, no fragile CSS selectors.

### Target website

| Property       | Value                          |
|----------------|--------------------------------|
| Website        | Sunglass Hut (sunglasshut.com) |
| Category       | Eyewear / Luxury Retail        |
| Content type   | Dynamic (API-driven)           |
| Search backend | Algolia                        |
| Pagination     | Page-based (100 products/page) |
| Total brands   | 48                             |
| Total products | 4,983                          |

---

## Performance

Results from a full production run.

| Metric            | Value |
|-------------------|-------|
| Brands discovered | 48    |
| Brands completed  | 48    |
| Expected products | 4,983 |
| Products scraped  | 4,983 |
| Coverage          | 100.0%|
| Requests sent     | 75    |
| Pages crawled     | 73    |
| Duplicates skipped| 0     |
| Total runtime     | 15.35s|


---

## Architecture

```
main.py
   │
   ▼
Container (dependency wiring — the only file that imports concrete classes)
   │
   ▼
ScraperEngine (thin orchestrator: fetch -> dedup -> export, batched)
   │
   ├── FetchService        — discovers brands, then paginates each brand's
   │                          slice of the Algolia index; also exposes
   │                          get_total_expected() for coverage reporting
   │     ├── GenericApiClient  — requests.Session + urllib3 Retry +
   │     │                       CircuitBreaker + optional throttling
   │     ├── ItemParser        — maps raw Algolia hits to Product objects
   │     ├── JsonCheckpointStore — tracks completed brands + in-progress
   │     │                         brand/page for resumable runs
   │     └── FailedItemStore     — records fetch/parse/validate failures
   ├── DeduplicationService — in-memory/on-disk dedup by objectID
   ├── ExportService        — fans out each batch to every exporter
   │     ├── CsvExporter
   │     └── JsonExporter
   └── RunMonitor           — tracks time, prints the final coverage report
```

Each layer only knows about its direct neighbours through an abstraction (`BaseApiClient`, `BaseCheckpointStore`, `BaseHitParser`, ...). Any piece can be swapped out — for example, replacing `GenericApiClient` with a browser-backed or GraphQL client, or adding a Postgres exporter alongside CSV/JSON — without touching anything else. `Container` is the single place that wires concrete implementations together.

Note on discovery + pagination: Algolia caps hits returned per single query, so a flat single-pass paginator can't reach every product. `FetchService` first discovers all brand facet values, then pages through each brand's slice individually — that's why brand discovery and per-brand crawling live together in one project-specific service rather than as separate, swappable pieces.

---

## Project structure

```
app/
├── abstraction/         # Interfaces (BaseApiClient, BaseCheckpointStore,
│                         #   BaseHitParser, etc.)
├── client/               # generic_api_client.py — HTTP layer: retries,
│                         #   circuit breaker, throttling, session
├── config/               # Settings (URLs, page size, rate limit, etc.)
├── container/            # Container — wires all pieces together
├── exceptions/           # scraper_exceptions.py (e.g. ParseError)
├── exporters/            # CSV and JSON exporters
├── models/                # Product data model, RunOutcome
├── monitoring/            # ScrapeStatistics, RunMonitor
├── orchestration/         # ScraperEngine
├── parsers/                # ItemParser — raw hit -> Product
├── services/                # FetchService, DeduplicationService,
│                            #   ExportService
├── storage/                  # JsonCheckpointStore, FailedItemStore
├── utils/                     # RateLimiter/throttling, CircuitBreaker
│                              #   (retry_policy.py), logger
└── validators/                 # Checks scraped data looks right

scripts/
└── retry_failed_urls.py        # Replays recorded parse/validate failures
                                 #   through the pipeline without a full
                                 #   re-scrape
```

---

## Resilience & resumability

Three separate mechanisms handle failure at different scopes:

| Mechanism | Scope | What it does |
|---|---|---|
| `urllib3.Retry` (in `GenericApiClient`) | Single request | Retries a request a few times with exponential backoff on transient errors (429, 5xx) |
| `CircuitBreaker` (`utils/retry_policy.py`) | Sustained failure | After `circuit_breaker_failure_threshold` consecutive failures, stops sending requests for `circuit_breaker_reset_seconds` instead of paying full retry+backoff cost against an API that's clearly down or blocking the scraper |
| `JsonCheckpointStore` (via `FetchService`) | Whole run | Tracks which brands are fully completed plus the in-progress brand/page. A restarted run skips finished brands and resumes mid-brand instead of re-crawling from scratch |

When a page fetch fails outright, `FetchService` records it in `FailedItemStore` under stage `"fetch"` and checkpoints the current brand/page so a re-run of `main.py` resumes exactly there. Parse and validation failures (a malformed record, an item that fails `is_valid()`) are also recorded, under stages `"parse"` and `"validate"`, but don't need a re-fetch — they can be replayed directly:

```bash
python -m scripts.retry_failed_urls
```

This re-runs each recorded raw record through parse → validate → dedup → export, so a batch of malformed records or a one-off parse bug can be recovered without re-running the whole scrape.

---

## What data is collected

Each product record captures everything a business would need:

```json
{
  "object_id": "8056597529679",
  "product_id": "3074457345618581851",
  "sku": "0RB2198 56 129251",
  "brand": "Ray-Ban",
  "model": "Bill",
  "gender": "UNISEX",
  "frame_shape": "Square",
  "frame_material": "Acetate",
  "lens_color": "Brown",
  "front_color": "Havana On Transparent Brown",
  "product_type": "SUN",
  "price": 164.0,
  "list_price": 164.0,
  "currency": "GBP",
  "discount_percentage": 0.0,
  "discount_amount": 0.0,
  "on_sale": false,
  "inventory": 1593,
  "is_best_seller": true,
  "is_polarized": false,
  "is_customizable": true,
  "image_url": "https://assets2.sunglasshut.com/.../0RB2198__129251__STD__noshad__qt.png",
  "url": "https://www.sunglasshut.com/ray-ban/rb2198-8056597529679"
}
```

### Business use cases this data supports

- **Price monitoring** — track `price` vs `list_price` and `discount_percentage` over time to get alerted when products go on sale
- **Catalogue/feed building** — structured attributes plus image URLs make a ready-made product feed for affiliate or comparison sites
- **Market research** — `is_best_seller`, frame shapes, materials, and brand distribution reveal what Sunglass Hut is pushing each season
- **Inventory signals** — `inventory` counts let dropshippers know which products are safe to list without risking overselling

---

## Getting started

**1. Clone the repo**
```bash
git clone 
cd algolia-api-reverse-engineering-scraper
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Set your request headers**

`GenericApiClient` accepts a plain `headers: dict[str, str]` in `Settings`, so it works against any reverse-engineered REST/JSON API, not just Algolia. For this project, open `settings.py` and set the Algolia API key header:

> The key can be found in your browser's network tab while browsing Sunglass Hut — open DevTools → Network tab → filter by `algolia` → look at any request's headers under `x-algolia-api-key`. It is a public read-only key embedded in the site's JavaScript.

**4. Run the scraper**
```bash
python main.py
```

Output is saved to `output/products.csv` and `output/products.json`. If the run is interrupted, just re-run `main.py` — it resumes from the last checkpoint instead of starting over.

**5. (Optional) Recover failed items**

If any records failed to parse or validate during the run, replay them without a full re-scrape:
```bash
python -m scripts.retry_failed_urls
```

---

## Configuration

All settings live in `app/config/settings.py`.

| Setting | Default | What it does |
|---|---|---|
| `hits_per_page` | `100` | Products fetched per request (Algolia max) |
| `requests_per_second` | `5.0` | How fast to send requests |
| `max_retries` | `5` | How many times `urllib3.Retry` retries a single failed request |
| `backoff_factor` | `0.5` | Backoff multiplier between per-request retries (doubles each attempt) |
| `circuit_breaker_failure_threshold` | `5` | Consecutive failures before the circuit breaker opens and fails fast |
| `circuit_breaker_reset_seconds` | `60.0` | How long the circuit stays open before allowing a trial (half-open) request |
| `output_filename` | `products.csv` | Base name for output files |

---

## Why reverse-engineering the API

| | HTML scraping | API reverse engineering |
|---|---|---|
| Speed | One request per page | 100 products per request |
| Stability | Breaks on redesigns | Stable JSON contract |
| Data quality | Depends on what's rendered | Full structured data |
| Hidden fields | Not accessible | Available in API response |
| Requests needed | ~4,641 | 72 |

---

## Requirements

- Python 3.10+
- See `requirements.txt` for packages

---

## Engineering highlights

This project demonstrates practical implementation of:

- Dependency injection via a single composition-root `Container`
- Layered architecture with abstract interfaces (`BaseApiClient`, `BaseCheckpointStore`, `BaseHitParser`, ...)
- Two-tier failure handling: per-request retry with exponential backoff (`urllib3.Retry`) plus a circuit breaker for sustained outages
- Checkpointed, resumable crawling — restarted runs skip completed brands and resume mid-brand
- Failed-item capture and replay — parse/validate failures are recorded and recoverable via `scripts/retry_failed_urls.py` without a full re-scrape
- Token-bucket-style client-side throttling (`requests_per_second`)
- In-memory/on-disk deduplication by stable objectID
- Pluggable exporters (CSV and JSON from the same data)
- Separation of scraping, parsing, storage, and export concerns

---

## Screenshots

### Output 
![alt text](image.png)

### Final report from log file
![alt text](image-1.png)

## Disclaimer

This project is built for educational and portfolio purposes. Users are responsible for ensuring compliance with the target website's terms of service and applicable laws before running the scraper in production.

---

## Author

**
Sara Mekshaj

Python Developer | Web Scraping Engineer

Specialising in:
- API reverse engineering
- Requests-based scraping systems
- Playwright automation
- Fault-tolerant data pipelines
- Data extraction and ETL