from __future__ import annotations
import logging
import time
from typing import Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from app.abstraction.base_api_client import BaseApiClient
from app.utils.retry_policy import CircuitBreaker, CircuitOpenError

class GenericApiClient(BaseApiClient):
    """Plain requests.Session client for reverse-engineered REST/JSON APIs.

    Handles:
      - per-request retries with backoff (urllib3.Retry) for transient errors
      - a circuit breaker for sustained failure (stop hammering a dead/blocking API)
      - optional simple client-side throttling (requests_per_second)

    Swap this out for browser_backed_api_client.py or graphql_api_client.py
    (Tier 2) when the project needs it; both implement BaseApiClient the same way.
    """

    def __init__(
        self,
        headers: dict[str, str] | None = None,
        timeout_seconds: float = 15.0,
        max_retries: int = 5,
        backoff_factor: float = 0.5,
        status_forcelist: tuple = (429, 500, 502, 503, 504),
        circuit_breaker_failure_threshold: int = 5,
        circuit_breaker_reset_seconds: float = 60.0,
        requests_per_second: float | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.timeout_seconds = timeout_seconds
        self.logger = logger or logging.getLogger("scraper")
        self._min_interval = (1.0 / requests_per_second) if requests_per_second else 0.0
        self._last_request_at = 0.0

        self.session = requests.Session()
        if headers:
            self.session.headers.update(headers)

        retry = Retry(
            total=max_retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
            allowed_methods=("GET", "POST"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.circuit_breaker = CircuitBreaker(
            failure_threshold=circuit_breaker_failure_threshold,
            reset_seconds=circuit_breaker_reset_seconds,
        )

    def _throttle(self) -> None:
        if self._min_interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        remaining = self._min_interval - elapsed
        if remaining > 0:
            time.sleep(remaining)
        self._last_request_at = time.monotonic()

    def get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("GET", url, params=params)

    def post(self, url: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._request("POST", url, json_body=json_body)

    def _request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.circuit_breaker.before_call()
        self._throttle()
        try:
            response = self.session.request(
                method,
                url,
                params=params,
                json=json_body,
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            self.circuit_breaker.on_success()
            return response.json()
        except CircuitOpenError:
            raise
        except Exception as exc:
            self.circuit_breaker.on_failure()
            self.logger.warning("Request failed: %s %s -> %s", method, url, exc)
            raise

    def close(self) -> None:
        self.session.close()
