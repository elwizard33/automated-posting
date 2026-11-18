"""Telegram: a bot posts to a public channel it administers."""

from typing import ClassVar

from app.platforms.auth import TokenInRequest
from app.platforms.base import Connector, ConnectorSpec, PublishOutcome

API_URL = "https://api.telegram.org"


class TelegramConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        key="telegram",
        name="Telegram",
        auth=TokenInRequest(fields=("telegram_bot_token", "telegram_channel")),
        docs_url="https://core.telegram.org/bots/api#sendmessage",
        max_length=4096,
    )

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        channel = channel_username(self._value("telegram_channel"))
        response = await self._request(
            "POST",
            f"{API_URL}/bot{self._value('telegram_bot_token')}/sendMessage",
            json={"chat_id": f"@{channel}", "text": message},
        )
        message_id = response.json()["result"]["message_id"]
        return PublishOutcome(posted_url=f"https://t.me/{channel}/{message_id}")


def channel_username(raw: str) -> str:
    """Accept '@name', 'name' or 't.me/name' and return the bare username."""
    return raw.strip().removeprefix("https://").removeprefix("t.me/").removeprefix("@")
