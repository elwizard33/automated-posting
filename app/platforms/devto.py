"""DEV Community: publish the message as a short article."""

from typing import ClassVar

from app.platforms.auth import ApiKeyHeader
from app.platforms.base import Connector, ConnectorSpec, PublishOutcome
from app.utils.text import derive_title

API_URL = "https://dev.to/api"


class DevtoConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        key="devto",
        name="DEV Community",
        auth=ApiKeyHeader(fields=("devto_api_key",), header="api-key"),
        docs_url="https://developers.forem.com/api/v1#tag/articles/operation/createArticle",
    )

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        response = await self._request(
            "POST",
            f"{API_URL}/articles",
            headers={**self._auth_headers(), "Accept": "application/vnd.forem.api-v1+json"},
            json={
                "article": {
                    "title": derive_title(message, link),
                    "body_markdown": message,
                    "published": True,
                }
            },
        )
        return PublishOutcome(posted_url=response.json()["url"])
