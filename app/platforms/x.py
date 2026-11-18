"""X: create a post with an OAuth 2.0 user access token."""

from typing import ClassVar

from app.platforms.auth import BearerToken
from app.platforms.base import Connector, ConnectorSpec, PublishOutcome

API_URL = "https://api.x.com"


class XConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        key="x",
        name="X",
        auth=BearerToken(fields=("x_access_token",)),
        docs_url="https://docs.x.com/x-api/posts/create-post",
        max_length=280,
        notes="Off by default: write access needs a paid API plan. Not live-tested.",
    )

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        response = await self._request(
            "POST",
            f"{API_URL}/2/tweets",
            headers=self._auth_headers(),
            json={"text": message},
        )
        post_id = response.json()["data"]["id"]
        return PublishOutcome(posted_url=f"https://x.com/i/web/status/{post_id}")
