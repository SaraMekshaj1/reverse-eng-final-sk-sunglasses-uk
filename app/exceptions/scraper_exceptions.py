class ScraperError(Exception):
    """Base exception for all scraper errors."""


class APIClientError(ScraperError):
    """Raised when an API request fails after retries."""


class ParseError(ScraperError):
    """Raised when a hit cannot be parsed into an Item."""


class ExportError(ScraperError):
    """Raised when exporting data fails."""


class PaginationError(ScraperError):
    """Raised when the paginator/fetch loop produces an invalid payload."""
