"""The contract every platform connector implements."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, ClassVar

import httpx

from app.config import Settings
from app.platforms.auth import Auth

_MAX_DETAIL_LENGTH = 200
_DETAIL_KEYS = ("message", "description", "detail", "error_description", "error", "title")


class PlatformError(Exception):
    """A publish failure whose message is safe to show to the API client."""


@dataclass(frozen=True)
class ConnectorSpec:
    key: str
    name: str
    auth: Auth
    docs_url: str
    public: bool = True
    max_length: int | None = None
    notes: str | None = None


@dataclass(frozen=True)
class PublishOutcome:
    posted_url: str


class Connector(ABC):
    spec: ClassVar[ConnectorSpec]

    def __init__(self, client: httpx.AsyncClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings

    def missing_settings(self) -> list[str]:
        return self.spec.auth.missing(self._settings)

    async def publish(self, message: str, link: str) -> PublishOutcome:
        """Publish the message and return where it can be read."""
        try:
            outcome = await self._publish(message, link)
        except (AttributeError, KeyError, IndexError, TypeError, ValueError) as exc:
            # The platform answered 2xx but not with the documented shape.
            raise PlatformError(f"Unexpected response from {self.spec.name}") from exc
        if not isinstance(outcome.posted_url, str) or not outcome.posted_url.startswith(
            ("https://", "http://")
        ):
            raise PlatformError(f"Unexpected response from {self.spec.name}")
        return outcome

    @abstractmethod
    async def _publish(self, message: str, link: str) -> PublishOutcome: ...

    def _value(self, name: str) -> str:
        return self.spec.auth.value(self._settings, name)

    def _auth_headers(self) -> dict[str, str]:
        return self.spec.auth.headers(self._settings)

    async def _request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        """Send a request and turn any non-2xx answer into a PlatformError."""
        response = await self._client.request(method, url, **kwargs)
        if not response.is_success:
            raise PlatformError(f"HTTP {response.status_code}: {self._error_detail(response)}")
        return response

    def _error_detail(self, response: httpx.Response) -> str:
        detail = _extract_detail(response)
        for secret in self.spec.auth.secrets(self._settings):
            detail = detail.replace(secret, "***")
        return detail[:_MAX_DETAIL_LENGTH]


def _extract_detail(response: httpx.Response) -> str:
    """Pick the human-readable part of an error body instead of echoing it whole."""
    try:
        body = response.json()
    except ValueError:
        return response.reason_phrase
    if isinstance(body, dict):
        for key in _DETAIL_KEYS:
            value = body.get(key)
            if isinstance(value, dict):
                value = value.get("message")
            if isinstance(value, str) and value:
                return value
    return response.reason_phrase
