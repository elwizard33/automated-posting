from urllib.parse import parse_qs

import httpx
import pytest
import respx

from app.platforms.base import PlatformError
from app.platforms.facebook_page import FacebookPageConnector
from tests.factories import make_settings

FEED_URL = "https://graph.facebook.com/v23.0/1234567890/feed"
LINK = "https://example.com"
MESSAGE = f"Launch day {LINK}"


def _connector(client: httpx.AsyncClient) -> FacebookPageConnector:
    settings = make_settings(facebook_page_access_token="fb-token", facebook_page_id="1234567890")
    return FacebookPageConnector(client, settings)


async def test_publish_posts_to_page_feed(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.post(FEED_URL).respond(200, json={"id": "1234567890_987"})

    outcome = await _connector(http_client).publish(MESSAGE, LINK)

    assert outcome.posted_url == "https://www.facebook.com/1234567890_987"
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer fb-token"
    assert parse_qs(request.content.decode()) == {"message": [MESSAGE], "link": [LINK]}


async def test_invalid_token_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(FEED_URL).respond(
        401,
        json={
            "error": {
                "message": "Invalid OAuth access token",
                "type": "OAuthException",
                "code": 190,
            }
        },
    )

    with pytest.raises(PlatformError, match=r"^HTTP 401: Invalid OAuth access token$"):
        await _connector(http_client).publish(MESSAGE, LINK)


async def test_malformed_response_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(FEED_URL).respond(200, json={"success": True})

    with pytest.raises(PlatformError, match=r"^Unexpected response from Facebook Page$"):
        await _connector(http_client).publish(MESSAGE, LINK)
