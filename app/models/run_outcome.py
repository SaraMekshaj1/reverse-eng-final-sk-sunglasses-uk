from __future__ import annotations

from enum import Enum, auto


class RunOutcome(Enum):
    COMPLETED = auto()     # reached natural end of pagination
    INTERRUPTED = auto()   # stopped early (error, circuit breaker, Ctrl-C, max_pages hit)
