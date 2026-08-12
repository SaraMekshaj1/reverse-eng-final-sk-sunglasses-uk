"""
Replays entries from the failed_item_store through the same parse ->
validate -> dedup -> export pipeline the main run uses, so a batch of
transient failures (a flaky page fetch, a handful of malformed records)
can be recovered without re-running the whole scrape.

Usage:
    python -m scripts.retry_failed_items

Only "parse" and "validate" stage failures are replayed here, since those
have a `raw` record that can be re-parsed directly. "fetch" stage failures
(a whole page request that failed) need to be re-fetched, not re-parsed --
handle those by re-running main.py, which resumes from the last checkpoint
(brand + page, for this project).
"""
from __future__ import annotations

from app.config.settings import Settings
from app.container import Container


def main() -> None:
    settings = Settings()
    container = Container(settings)

    replayable_stages = {"parse", "validate"}
    to_retry = [
        entry for entry in container.failed_item_store.iter_entries()
        if entry.get("stage") in replayable_stages
    ]

    if not to_retry:
        container.logger.info("No replayable failed items found.")
        container.close()
        return

    container.logger.info("Replaying %s failed items", len(to_retry))

    container.dedup_service.begin_run()
    container.export_service.start()

    recovered, still_failed = 0, 0
    try:
        for entry in to_retry:
            raw_record = entry["raw"]
            try:
                item = container.hit_parser.parse(raw_record)
            except Exception as exc:
                container.logger.warning("Retry parse failed again: %s", exc)
                still_failed += 1
                continue

            if not item.is_valid() or not container.dedup_service.is_new(item):
                still_failed += 1
                continue

            container.export_service.export_batch([item])
            recovered += 1
    finally:
        container.export_service.finish()
        container.dedup_service.end_run()
        container.close()

    container.logger.info("Retry complete: recovered=%s, still_failed=%s", recovered, still_failed)


if __name__ == "__main__":
    main()
