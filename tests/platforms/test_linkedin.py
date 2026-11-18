import json

import httpx
import pytest
import respx

from app.platforms.base import PlatformError
from app.platforms.linkedin import LinkedInConnector, escape_commentary
from tests.factories import make_settings

POSTS_URL = "https://api.linkedin.com/rest/posts"
LINK = "https://example.com"
MESSAGE = f"Launch day (v2) {LINK}"


def _connector(client: httpx.AsyncClient) -> LinkedInConnector:
    settings = make_settings(
        linkedin_access_token="li-token", linkedin_author_urn="urn:li:person:abc123"
    )
    return LinkedInConnector(client, settings)


async def test_publish_creates_public_post(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.post(POSTS_URL).respond(201, headers={"x-restli-id": "urn:li:share:7001"})

    outcome = await _connector(http_client).publish(MESSAGE, LINK)

    assert outcome.posted_url == "https://www.linkedin.com/feed/update/urn:li:share:7001/"
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer li-token"
    assert request.headers["LinkedIn-Version"] == "202610"
    assert request.headers["X-Restli-Protocol-Version"] == "2.0.0"
    assert json.loads(request.content) == {
        "author": "urn:li:person:abc123",
        "commentary": f"Launch day \\(v2\\) {LINK}",
        "visibility": "PUBLIC",
        "distribution": {
            "feedDistribution": "MAIN_FEED",
            "targetEntities": [],
            "thirdPartyDistributionChannels": [],
        },
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }


def test_escape_commentary_escapes_reserved_characters() -> None:
    assert escape_commentary("50% off #1 [today] @home_x") == "50% off \\#1 \\[today\\] \\@home\\_x"


async def test_invalid_token_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(POSTS_URL).respond(
        401, json={"status": 401, "code": "INVALID_ACCESS_TOKEN", "message": "Invalid access token"}
    )

    with pytest.raises(PlatformError, match=r"^HTTP 401: Invalid access token$"):
        await _connector(http_client).publish(MESSAGE, LINK)


async def test_missing_post_id_header_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(POSTS_URL).respond(201)

    with pytest.raises(PlatformError, match=r"^Unexpected response from LinkedIn$"):
        await _connector(http_client).publish(MESSAGE, LINK)
