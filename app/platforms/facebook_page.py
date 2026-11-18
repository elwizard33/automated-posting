"""Facebook: publish to the feed of a Page with a Page access token."""

from typing import ClassVar

from app.platforms.auth import BearerToken
from app.platforms.base import Connector, ConnectorSpec, PublishOutcome

API_URL = "https://graph.facebook.com"


class FacebookPageConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        key="facebook_page",
        name="Facebook Page",
        auth=BearerToken(fields=("facebook_page_access_token", "facebook_page_id")),
        docs_url="https://developers.facebook.com/docs/pages-api/posts",
        max_length=63206,
        notes="Off by default: needs a Meta app and a Page access token. Not live-tested.",
    )

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        version = self._settings.facebook_graph_version
        page_id = self._value("facebook_page_id")
        response = await self._request(
            "POST",
            f"{API_URL}/{version}/{page_id}/feed",
            headers=self._auth_headers(),
            data={"message": message, "link": link},
        )
        return PublishOutcome(posted_url=f"https://www.facebook.com/{response.json()['id']}")
