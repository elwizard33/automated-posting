import json

import httpx
import pytest
import respx

from app.platforms.base import PlatformError
from app.platforms.bluesky import BlueskyConnector, link_facet
from tests.factories import make_settings

SESSION_URL = "https://bsky.social/xrpc/com.atproto.server.createSession"
RECORD_URL = "https://bsky.social/xrpc/com.atproto.repo.createRecord"
LINK = "https://example.com"
MESSAGE = f"Launch day {LINK}"
SESSION = {"accessJwt": "jwt-1", "did": "did:plc:abc123", "handle": "demo.bsky.social"}


def _connector(client: httpx.AsyncClient) -> BlueskyConnector:
    settings = make_settings(bluesky_handle="@demo.bsky.social", bluesky_app_password="app-pw")
    return BlueskyConnector(client, settings)


async def test_publish_creates_post_with_link_facet(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    login = respx_mock.post(SESSION_URL).respond(200, json=SESSION)
    create = respx_mock.post(RECORD_URL).respond(
        200, json={"uri": "at://did:plc:abc123/app.bsky.feed.post/3kabc", "cid": "bafy"}
    )

    outcome = await _connector(http_client).publish(MESSAGE, LINK)

    assert outcome.posted_url == "https://bsky.app/profile/demo.bsky.social/post/3kabc"
    assert json.loads(login.calls.last.request.content) == {
        "identifier": "demo.bsky.social",
        "password": "app-pw",
    }
    request = create.calls.last.request
    assert request.headers["Authorization"] == "Bearer jwt-1"
    body = json.loads(request.content)
    assert body["repo"] == "did:plc:abc123"
    assert body["collection"] == "app.bsky.feed.post"
    assert body["record"]["text"] == MESSAGE
    assert body["record"]["createdAt"].endswith("Z")
    assert body["record"]["facets"] == [
        {
            "index": {"byteStart": 11, "byteEnd": 30},
            "features": [{"$type": "app.bsky.richtext.facet#link", "uri": LINK}],
        }
    ]


def test_link_facet_counts_bytes_not_characters() -> None:
    facet = link_facet(f"Café ☕ {LINK}", LINK)
    # "Café ☕ " is 7 characters but 10 bytes in UTF-8.
    assert facet["index"] == {"byteStart": 10, "byteEnd": 29}


async def test_bad_app_password_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(SESSION_URL).respond(
        401, json={"error": "AuthenticationRequired", "message": "Invalid identifier or password"}
    )

    with pytest.raises(PlatformError, match=r"^HTTP 401: Invalid identifier or password$"):
        await _connector(http_client).publish(MESSAGE, LINK)


async def test_malformed_response_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(SESSION_URL).respond(200, json=SESSION)
    respx_mock.post(RECORD_URL).respond(200, json={"cid": "bafy"})

    with pytest.raises(PlatformError, match=r"^Unexpected response from Bluesky$"):
        await _connector(http_client).publish(MESSAGE, LINK)


async def test_non_string_record_uri_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(SESSION_URL).respond(200, json=SESSION)
    respx_mock.post(RECORD_URL).respond(200, json={"uri": 42, "cid": "bafy"})

    with pytest.raises(PlatformError, match=r"^Unexpected response from Bluesky$"):
        await _connector(http_client).publish(MESSAGE, LINK)
