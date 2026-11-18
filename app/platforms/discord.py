"""Discord: post through a channel webhook."""

from typing import ClassVar

from app.platforms.auth import WebhookUrl
from app.platforms.base import Connector, ConnectorSpec, PublishOutcome


class DiscordConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        key="discord",
        name="Discord",
        auth=WebhookUrl(fields=("discord_webhook_url",)),
        docs_url="https://discord.com/developers/docs/resources/webhook#execute-webhook",
        public=False,
        max_length=2000,
        notes="Messages are visible only to members of the server.",
    )

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        webhook_url = self._value("discord_webhook_url")
        # The message URL needs the server id, which only the webhook lookup returns.
        # Look it up before posting so a failure here cannot follow a successful post.
        guild_id = (await self._request("GET", webhook_url)).json()["guild_id"]
        response = await self._request(
            "POST",
            webhook_url,
            params={"wait": "true"},
            json={"content": message, "allowed_mentions": {"parse": []}},
        )
        posted = response.json()
        return PublishOutcome(
            posted_url=(
                f"https://discord.com/channels/{guild_id}/{posted['channel_id']}/{posted['id']}"
            )
        )
