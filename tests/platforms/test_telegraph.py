import json

import httpx
import pytest
import respx

from app.platforms.base import PlatformError
from app.platforms.telegraph import TelegraphConnector, page_content
from tests.factories import make_settings

CREATE_URL = "https://api.telegra.ph/createPage"
LINK = "https://example.com"
MESSAGE = f"Launch day {LINK} for everyone"


def _connector(client: httpx.AsyncClient) -> TelegraphConnector:
    return TelegraphConnector(client, make_settings(telegraph_access_token="tg-token"))


async def test_publish_creates_page(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.post(CREATE_URL).respond(
        200,
        json={
            "ok": True,
            "result": {"path": "Launch-11-18", "url": "https://telegra.ph/Launch-11-18"},
        },
    )

    outcome = await _connector(http_client).publish(MESSAGE, LINK)

    assert outcome.posted_url == "https://telegra.ph/Launch-11-18"
    assert json.loads(route.calls.last.request.content) == {
        "access_token": "tg-token",
        "title": "Launch day for everyone",
        "content": [
            {
                "tag": "p",
                "children": [
                    "Launch day ",
                    {"tag": "a", "attrs": {"href": LINK}, "children": [LINK]},
                    " for everyone",
                ],
            }
        ],
    }


def test_page_content_skips_empty_text_around_the_link() -> None:
    assert page_content(LINK, LINK) == [
        {"tag": "p", "children": [{"tag": "a", "attrs": {"href": LINK}, "children": [LINK]}]}
    ]


async def test_error_reported_with_http_200(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(CREATE_URL).respond(200, json={"ok": False, "error": "ACCESS_TOKEN_INVALID"})

    with pytest.raises(PlatformError, match=r"^Telegraph rejected the page: ACCESS_TOKEN_INVALID$"):
        await _connector(http_client).publish(MESSAGE, LINK)


async def test_malformed_response_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(CREATE_URL).respond(200, json={"ok": True, "result": {}})

    with pytest.raises(PlatformError, match=r"^Unexpected response from Telegraph$"):
        await _connector(http_client).publish(MESSAGE, LINK)
