import json

import httpx
import pytest
import respx

from app.platforms.base import PlatformError
from app.platforms.devto import DevtoConnector
from tests.factories import make_settings

ARTICLES_URL = "https://dev.to/api/articles"
LINK = "https://example.com"
MESSAGE = f"Launch day {LINK}"


def _connector(client: httpx.AsyncClient) -> DevtoConnector:
    return DevtoConnector(client, make_settings(devto_api_key="dev-key"))


async def test_publish_creates_published_article(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.post(ARTICLES_URL).respond(
        201, json={"id": 99, "url": "https://dev.to/demo/launch-day-1a2b"}
    )

    outcome = await _connector(http_client).publish(MESSAGE, LINK)

    assert outcome.posted_url == "https://dev.to/demo/launch-day-1a2b"
    request = route.calls.last.request
    assert request.headers["api-key"] == "dev-key"
    assert request.headers["Accept"] == "application/vnd.forem.api-v1+json"
    assert json.loads(request.content) == {
        "article": {"title": "Launch day", "body_markdown": MESSAGE, "published": True}
    }


async def test_bad_api_key_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(ARTICLES_URL).respond(401, json={"error": "unauthorized", "status": 401})

    with pytest.raises(PlatformError, match=r"^HTTP 401: unauthorized$"):
        await _connector(http_client).publish(MESSAGE, LINK)


async def test_malformed_response_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(ARTICLES_URL).respond(201, json={"id": 99})

    with pytest.raises(PlatformError, match=r"^Unexpected response from DEV Community$"):
        await _connector(http_client).publish(MESSAGE, LINK)
