from __future__ import annotations

import logging
from pathlib import Path


def setup_logger(
    name: str = "scraper",
    level: str = "INFO",
    log_file: Path | str | None = None,
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if logger.handlers:
        # Avoid duplicate handlers if Container is built more than once
        # (e.g. in tests or a REPL session).
        return logger

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(fmt)
    logger.addHandler(console_handler)

    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)

    return logger
