import json

import httpx
import pytest
import respx

from app.platforms.base import PlatformError
from app.platforms.discord import DiscordConnector
from tests.factories import make_settings

WEBHOOK_URL = "https://discord.com/api/webhooks/111/hook-token"
LINK = "https://example.com"
MESSAGE = f"Launch day {LINK}"


def _connector(client: httpx.AsyncClient) -> DiscordConnector:
    return DiscordConnector(client, make_settings(discord_webhook_url=WEBHOOK_URL))


def test_spec_declares_posts_as_not_public() -> None:
    assert DiscordConnector.spec.public is False


async def test_publish_posts_through_webhook(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    lookup = respx_mock.get(WEBHOOK_URL).respond(
        200, json={"id": "111", "guild_id": "222", "channel_id": "333"}
    )
    post = respx_mock.post(WEBHOOK_URL).respond(200, json={"id": "444", "channel_id": "333"})

    outcome = await _connector(http_client).publish(MESSAGE, LINK)

    assert outcome.posted_url == "https://discord.com/channels/222/333/444"
    assert lookup.called
    request = post.calls.last.request
    assert request.url.params["wait"] == "true"
    assert json.loads(request.content) == {"content": MESSAGE, "allowed_mentions": {"parse": []}}


async def test_unknown_webhook_fails_before_posting(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(WEBHOOK_URL).respond(404, json={"message": "Unknown Webhook", "code": 10015})
    post = respx_mock.post(WEBHOOK_URL).respond(200, json={"id": "444", "channel_id": "333"})

    with pytest.raises(PlatformError, match=r"^HTTP 404: Unknown Webhook$"):
        await _connector(http_client).publish(MESSAGE, LINK)
    assert not post.called


async def test_malformed_response_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(WEBHOOK_URL).respond(200, json={"guild_id": "222"})
    respx_mock.post(WEBHOOK_URL).respond(200, json={"content": MESSAGE})

    with pytest.raises(PlatformError, match=r"^Unexpected response from Discord$"):
        await _connector(http_client).publish(MESSAGE, LINK)
