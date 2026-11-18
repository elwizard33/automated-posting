import json

import httpx
import pytest
import respx

from app.platforms.base import PlatformError
from app.platforms.telegram import TelegramConnector, channel_username
from tests.factories import make_settings

SEND_URL = "https://api.telegram.org/bot123456:ABC-token/sendMessage"
LINK = "https://example.com"
MESSAGE = f"Launch day {LINK}"


def _connector(client: httpx.AsyncClient) -> TelegramConnector:
    settings = make_settings(
        telegram_bot_token="123456:ABC-token", telegram_channel="@demo_channel"
    )
    return TelegramConnector(client, settings)


async def test_publish_sends_message_to_channel(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.post(SEND_URL).respond(
        200, json={"ok": True, "result": {"message_id": 42, "chat": {"username": "demo_channel"}}}
    )

    outcome = await _connector(http_client).publish(MESSAGE, LINK)

    assert outcome.posted_url == "https://t.me/demo_channel/42"
    assert json.loads(route.calls.last.request.content) == {
        "chat_id": "@demo_channel",
        "text": MESSAGE,
    }


@pytest.mark.parametrize(
    "raw",
    [
        "@demo_channel",
        "demo_channel",
        "https://t.me/demo_channel",
        "t.me/demo_channel",
        " @demo_channel ",
    ],
)
def test_channel_username_accepts_common_forms(raw: str) -> None:
    assert channel_username(raw) == "demo_channel"


async def test_bad_token_is_reported_without_leaking_it(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(SEND_URL).respond(
        401, json={"ok": False, "error_code": 401, "description": "Unauthorized"}
    )

    with pytest.raises(PlatformError) as excinfo:
        await _connector(http_client).publish(MESSAGE, LINK)
    assert str(excinfo.value) == "HTTP 401: Unauthorized"
    assert "ABC-token" not in str(excinfo.value)


async def test_malformed_response_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(SEND_URL).respond(200, json={"ok": True})

    with pytest.raises(PlatformError, match=r"^Unexpected response from Telegram$"):
        await _connector(http_client).publish(MESSAGE, LINK)
