from __future__ import annotations

from app.config.settings import Settings
from app.container import Container


def main() -> None:
    settings = Settings()  # edit app/config/settings.py to change target/output
    container = Container(settings)
    try:
        container.engine.run()
    finally:
        container.close()


if __name__ == "__main__":
    main()
