"""Telegraph: publish the message as a short public page."""

from typing import Any, ClassVar

from app.platforms.auth import TokenInRequest
from app.platforms.base import Connector, ConnectorSpec, PlatformError, PublishOutcome
from app.utils.text import derive_title

API_URL = "https://api.telegra.ph"


class TelegraphConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        key="telegraph",
        name="Telegraph",
        auth=TokenInRequest(fields=("telegraph_access_token",)),
        docs_url="https://telegra.ph/api#createPage",
    )

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        response = await self._request(
            "POST",
            f"{API_URL}/createPage",
            json={
                "access_token": self._value("telegraph_access_token"),
                "title": derive_title(message, link),
                "content": page_content(message, link),
            },
        )
        data = response.json()
        # Telegraph reports failures with HTTP 200 and ok=false.
        if not data["ok"]:
            raise PlatformError(
                f"Telegraph rejected the page: {data.get('error', 'unknown error')}"
            )
        return PublishOutcome(posted_url=data["result"]["url"])


def page_content(message: str, link: str) -> list[dict[str, Any]]:
    """One paragraph in Telegraph's node format, with the link as a real anchor."""
    before, _, after = message.partition(link)
    anchor = {"tag": "a", "attrs": {"href": link}, "children": [link]}
    return [{"tag": "p", "children": [part for part in (before, anchor, after) if part]}]
