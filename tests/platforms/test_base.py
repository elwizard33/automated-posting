from typing import ClassVar

import httpx
import pytest
import respx

from app.platforms.auth import (
    ApiKeyHeader,
    AppPasswordSession,
    BearerToken,
    TokenInRequest,
    WebhookUrl,
)
from app.platforms.base import Connector, ConnectorSpec, PlatformError, PublishOutcome
from tests.factories import make_settings

URL = "https://api.example.test/posts"


class EchoConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        key="echo",
        name="Echo",
        auth=BearerToken(fields=("devto_api_key",)),
        docs_url="https://example.test/docs",
    )

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        response = await self._request(
            "POST", URL, headers=self._auth_headers(), json={"m": message}
        )
        return PublishOutcome(posted_url=response.json()["url"])


def test_missing_lists_environment_variable_names() -> None:
    auth = AppPasswordSession(fields=("bluesky_handle", "bluesky_app_password"))
    assert auth.missing(make_settings()) == ["BLUESKY_HANDLE", "BLUESKY_APP_PASSWORD"]
    assert auth.missing(make_settings(bluesky_handle="me.bsky.social")) == ["BLUESKY_APP_PASSWORD"]
    assert (
        auth.missing(make_settings(bluesky_handle="me.bsky.social", bluesky_app_password="pw"))
        == []
    )


def test_bearer_token_header() -> None:
    auth = BearerToken(fields=("github_gist_token",))
    settings = make_settings(github_gist_token="ghp_123")
    assert auth.headers(settings) == {"Authorization": "Bearer ghp_123"}
    assert auth.kind == "bearer_token"


def test_api_key_header() -> None:
    auth = ApiKeyHeader(fields=("devto_api_key",), header="api-key")
    assert auth.headers(make_settings(devto_api_key="k1")) == {"api-key": "k1"}
    assert auth.kind == "api_key_header"


def test_strategies_without_headers() -> None:
    settings = make_settings(telegram_bot_token="1:a", discord_webhook_url="https://d.test/w")
    assert TokenInRequest(fields=("telegram_bot_token",)).headers(settings) == {}
    assert WebhookUrl(fields=("discord_webhook_url",)).headers(settings) == {}
    assert TokenInRequest(fields=("telegram_bot_token",)).kind == "token_in_request"
    assert WebhookUrl(fields=("discord_webhook_url",)).kind == "webhook_url"


def test_value_and_secrets() -> None:
    auth = BearerToken(fields=("mastodon_access_token", "mastodon_base_url"))
    settings = make_settings(mastodon_access_token="tok", mastodon_base_url="https://m.test")
    assert auth.value(settings, "mastodon_access_token") == "tok"
    assert auth.value(settings, "mastodon_base_url") == "https://m.test"
    assert auth.secrets(settings) == ["tok"]


async def test_publish_success(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.post(URL).respond(201, json={"url": "https://example.test/p/1"})
    connector = EchoConnector(http_client, make_settings(devto_api_key="k1"))

    outcome = await connector.publish("hello", "https://example.com")

    assert outcome == PublishOutcome(posted_url="https://example.test/p/1")
    assert route.calls.last.request.headers["Authorization"] == "Bearer k1"
    assert connector.missing_settings() == []


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (401, {"message": "Bad credentials"}, "HTTP 401: Bad credentials"),
        (401, {"error": "The access token is invalid"}, "HTTP 401: The access token is invalid"),
        (401, {"ok": False, "description": "Unauthorized"}, "HTTP 401: Unauthorized"),
        (403, {"title": "Forbidden", "detail": "Not allowed here"}, "HTTP 403: Not allowed here"),
        (
            400,
            {"error": {"message": "Invalid OAuth access token", "code": 190}},
            "HTTP 400: Invalid OAuth access token",
        ),
        (429, {"errors": ["slow down"]}, "HTTP 429: Too Many Requests"),
    ],
)
async def test_error_responses_become_platform_errors(
    http_client: httpx.AsyncClient,
    respx_mock: respx.MockRouter,
    status: int,
    body: dict[str, object],
    expected: str,
) -> None:
    respx_mock.post(URL).respond(status, json=body)
    connector = EchoConnector(http_client, make_settings(devto_api_key="k1"))

    with pytest.raises(PlatformError, match=f"^{expected}$"):
        await connector.publish("hello", "https://example.com")


async def test_non_json_error_uses_reason_phrase(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(URL).respond(502, text="<html>bad gateway</html>")
    connector = EchoConnector(http_client, make_settings(devto_api_key="k1"))

    with pytest.raises(PlatformError, match=r"^HTTP 502: Bad Gateway$"):
        await connector.publish("hello", "https://example.com")


async def test_secrets_are_scrubbed_from_error_details(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(URL).respond(401, json={"message": "token k1-secret is not valid"})
    connector = EchoConnector(http_client, make_settings(devto_api_key="k1-secret"))

    with pytest.raises(PlatformError, match=r"^HTTP 401: token \*\*\* is not valid$"):
        await connector.publish("hello", "https://example.com")


async def test_long_error_details_are_truncated(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(URL).respond(400, json={"message": "x" * 500})
    connector = EchoConnector(http_client, make_settings(devto_api_key="k1"))

    with pytest.raises(PlatformError) as excinfo:
        await connector.publish("hello", "https://example.com")
    assert str(excinfo.value) == "HTTP 400: " + "x" * 200


async def test_malformed_success_body_becomes_platform_error(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(URL).respond(201, json={"unexpected": True})
    connector = EchoConnector(http_client, make_settings(devto_api_key="k1"))

    with pytest.raises(PlatformError, match=r"^Unexpected response from Echo$"):
        await connector.publish("hello", "https://example.com")


async def test_network_errors_propagate_for_the_service_to_handle(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(URL).mock(side_effect=httpx.ConnectTimeout("boom"))
    connector = EchoConnector(http_client, make_settings(devto_api_key="k1"))

    with pytest.raises(httpx.ConnectTimeout):
        await connector.publish("hello", "https://example.com")
