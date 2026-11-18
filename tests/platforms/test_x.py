import json

import httpx
import pytest
import respx

from app.platforms.base import PlatformError
from app.platforms.x import XConnector
from tests.factories import make_settings

TWEETS_URL = "https://api.x.com/2/tweets"
LINK = "https://example.com"
MESSAGE = f"Launch day {LINK}"


def _connector(client: httpx.AsyncClient) -> XConnector:
    return XConnector(client, make_settings(x_access_token="x-token"))


async def test_publish_creates_post(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.post(TWEETS_URL).respond(201, json={"data": {"id": "1890", "text": MESSAGE}})

    outcome = await _connector(http_client).publish(MESSAGE, LINK)

    assert outcome.posted_url == "https://x.com/i/web/status/1890"
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer x-token"
    assert json.loads(request.content) == {"text": MESSAGE}


async def test_forbidden_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(TWEETS_URL).respond(
        403,
        json={
            "title": "Unsupported Authentication",
            "detail": "Authenticating with OAuth 2.0 Application-Only is forbidden.",
            "status": 403,
        },
    )

    with pytest.raises(PlatformError, match=r"^HTTP 403: Authenticating with OAuth 2.0"):
        await _connector(http_client).publish(MESSAGE, LINK)


async def test_malformed_response_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(TWEETS_URL).respond(201, json={"data": {}})

    with pytest.raises(PlatformError, match=r"^Unexpected response from X$"):
        await _connector(http_client).publish(MESSAGE, LINK)
