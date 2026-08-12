"""Circuit breaker used by GenericApiClient to stop hammering a dead/blocking API.

This is separate from urllib3's per-request Retry: Retry handles a single
request's transient failures (a 503 gets retried a few times with backoff).
CircuitBreaker handles *sustained* failure across many requests -- once
`failure_threshold` consecutive failures happen, it "opens" and fails fast
for `reset_seconds` instead of letting every subsequent request pay the
full retry+backoff cost against an API that's clearly down or blocking us.
"""
from __future__ import annotations

import threading
import time


class CircuitOpenError(Exception):
    """Raised by before_call() while the circuit is open."""


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, reset_seconds: float = 60.0) -> None:
        self.failure_threshold = failure_threshold
        self.reset_seconds = reset_seconds
        self._lock = threading.Lock()
        self._consecutive_failures = 0
        self._opened_at: float | None = None

    def before_call(self) -> None:
        with self._lock:
            if self._opened_at is None:
                return
            elapsed = time.monotonic() - self._opened_at
            if elapsed < self.reset_seconds:
                raise CircuitOpenError(
                    f"Circuit open; retry in {self.reset_seconds - elapsed:.1f}s"
                )
            # reset window elapsed -- allow a single trial call through
            # (half-open state); on_success/on_failure will decide what's next.
            self._opened_at = None
            self._consecutive_failures = 0

    def on_success(self) -> None:
        with self._lock:
            self._consecutive_failures = 0
            self._opened_at = None

    def on_failure(self) -> None:
        with self._lock:
            self._consecutive_failures += 1
            if self._consecutive_failures >= self.failure_threshold:
                self._opened_at = time.monotonic()
