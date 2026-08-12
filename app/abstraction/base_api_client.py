"""Contract for any HTTP/GraphQL client used to talk to the target API.
Swappable implementations (Tier 2): browser_backed_api_client.py, async_api_client.py,
graphql_api_client.py -- all must satisfy this same interface so services never
need to know which concrete client is wired in.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any


class BaseApiClient(ABC):
    @abstractmethod
    def get(self, url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Perform a GET request and return the parsed JSON body."""
        raise NotImplementedError

    @abstractmethod
    def post(self, url: str, json_body: dict[str, Any] | None = None) -> dict[str, Any]:
        """Perform a POST request (e.g. GraphQL) and return the parsed JSON body."""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """Release any underlying connections/sessions."""
        raise NotImplementedError
