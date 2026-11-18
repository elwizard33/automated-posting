"""Mastodon: post a public status on the configured instance."""

from typing import ClassVar

from app.platforms.auth import BearerToken
from app.platforms.base import Connector, ConnectorSpec, PublishOutcome


class MastodonConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        key="mastodon",
        name="Mastodon",
        auth=BearerToken(fields=("mastodon_access_token", "mastodon_base_url")),
        docs_url="https://docs.joinmastodon.org/methods/statuses/#create",
        max_length=500,
    )

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        base_url = self._value("mastodon_base_url").rstrip("/")
        response = await self._request(
            "POST",
            f"{base_url}/api/v1/statuses",
            headers=self._auth_headers(),
            json={"status": message, "visibility": "public"},
        )
        return PublishOutcome(posted_url=response.json()["url"])
