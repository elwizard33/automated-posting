import json

import httpx
import pytest
import respx

from app.platforms.base import PlatformError
from app.platforms.mastodon import MastodonConnector
from tests.factories import make_settings

STATUS_URL = "https://mastodon.social/api/v1/statuses"
LINK = "https://example.com"
MESSAGE = f"Launch day {LINK}"


def _connector(client: httpx.AsyncClient) -> MastodonConnector:
    settings = make_settings(
        mastodon_access_token="masto-token", mastodon_base_url="https://mastodon.social/"
    )
    return MastodonConnector(client, settings)


async def test_publish_posts_public_status(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.post(STATUS_URL).respond(
        200, json={"id": "113", "url": "https://mastodon.social/@demo/113"}
    )

    outcome = await _connector(http_client).publish(MESSAGE, LINK)

    assert outcome.posted_url == "https://mastodon.social/@demo/113"
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer masto-token"
    assert json.loads(request.content) == {"status": MESSAGE, "visibility": "public"}


async def test_invalid_token_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(STATUS_URL).respond(401, json={"error": "The access token is invalid"})

    with pytest.raises(PlatformError, match=r"^HTTP 401: The access token is invalid$"):
        await _connector(http_client).publish(MESSAGE, LINK)


async def test_malformed_response_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(STATUS_URL).respond(200, json={"id": "113"})

    with pytest.raises(PlatformError, match=r"^Unexpected response from Mastodon$"):
        await _connector(http_client).publish(MESSAGE, LINK)


@pytest.mark.parametrize("url", [None, 12345, "", "not a url"])
async def test_missing_or_invalid_post_url_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter, url: object
) -> None:
    # Mastodon documents Status.url as "String or null".
    respx_mock.post(STATUS_URL).respond(200, json={"id": "113", "url": url})

    with pytest.raises(PlatformError, match=r"^Unexpected response from Mastodon$"):
        await _connector(http_client).publish(MESSAGE, LINK)
