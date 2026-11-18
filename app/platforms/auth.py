"""Auth strategies shared by the connectors.

A strategy names the settings a platform needs and knows how to turn them into
request credentials, so connectors never read settings or build auth headers.
Header strategies send their first field; any other fields are plain configuration.
"""

from dataclasses import dataclass
from typing import ClassVar

from pydantic import SecretStr

from app.config import Settings


@dataclass(frozen=True)
class Auth:
    fields: tuple[str, ...]
    kind: ClassVar[str] = "none"

    def missing(self, settings: Settings) -> list[str]:
        """Environment variable names that still need a value."""
        return [name.upper() for name in self.fields if not getattr(settings, name)]

    def value(self, settings: Settings, name: str) -> str:
        raw = getattr(settings, name)
        return raw.get_secret_value() if isinstance(raw, SecretStr) else str(raw)

    def secrets(self, settings: Settings) -> list[str]:
        """Secret values, used to scrub them from error messages."""
        values = (getattr(settings, name) for name in self.fields)
        return [value.get_secret_value() for value in values if isinstance(value, SecretStr)]

    def headers(self, settings: Settings) -> dict[str, str]:
        return {}


@dataclass(frozen=True)
class BearerToken(Auth):
    """Sends the first field as an OAuth-style bearer token."""

    kind: ClassVar[str] = "bearer_token"

    def headers(self, settings: Settings) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.value(settings, self.fields[0])}"}


@dataclass(frozen=True)
class ApiKeyHeader(Auth):
    """Sends the first field in a custom header."""

    header: str = "api-key"
    kind: ClassVar[str] = "api_key_header"

    def headers(self, settings: Settings) -> dict[str, str]:
        return {self.header: self.value(settings, self.fields[0])}


@dataclass(frozen=True)
class AppPasswordSession(Auth):
    """Identifier plus app password, exchanged by the connector for a session token."""

    kind: ClassVar[str] = "app_password_session"


@dataclass(frozen=True)
class TokenInRequest(Auth):
    """The platform expects the token in the URL path or the request body."""

    kind: ClassVar[str] = "token_in_request"


@dataclass(frozen=True)
class WebhookUrl(Auth):
    """The webhook URL is itself the credential."""

    kind: ClassVar[str] = "webhook_url"
