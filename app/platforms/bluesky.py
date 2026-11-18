"""Bluesky: log in with an app password, then create a post record."""

from datetime import UTC, datetime
from typing import Any, ClassVar

from app.platforms.auth import AppPasswordSession
from app.platforms.base import Connector, ConnectorSpec, PublishOutcome

PDS_URL = "https://bsky.social"


class BlueskyConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        key="bluesky",
        name="Bluesky",
        auth=AppPasswordSession(fields=("bluesky_handle", "bluesky_app_password")),
        docs_url="https://docs.bsky.app/docs/api/com-atproto-repo-create-record",
        max_length=300,
    )

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        session = await self._create_session()
        record = {
            "$type": "app.bsky.feed.post",
            "text": message,
            "createdAt": datetime.now(UTC)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "facets": [link_facet(message, link)],
        }
        response = await self._request(
            "POST",
            f"{PDS_URL}/xrpc/com.atproto.repo.createRecord",
            headers={"Authorization": f"Bearer {session['accessJwt']}"},
            json={"repo": session["did"], "collection": "app.bsky.feed.post", "record": record},
        )
        record_key = response.json()["uri"].rsplit("/", 1)[-1]
        return PublishOutcome(
            posted_url=f"https://bsky.app/profile/{session['handle']}/post/{record_key}"
        )

    async def _create_session(self) -> dict[str, Any]:
        response = await self._request(
            "POST",
            f"{PDS_URL}/xrpc/com.atproto.server.createSession",
            json={
                "identifier": self._value("bluesky_handle").removeprefix("@"),
                "password": self._value("bluesky_app_password"),
            },
        )
        session: dict[str, Any] = response.json()
        return session


def link_facet(message: str, link: str) -> dict[str, Any]:
    """Mark the link as clickable. Bluesky indexes facets by UTF-8 byte, not by character."""
    start = len(message[: message.index(link)].encode("utf-8"))
    return {
        "index": {"byteStart": start, "byteEnd": start + len(link.encode("utf-8"))},
        "features": [{"$type": "app.bsky.richtext.facet#link", "uri": link}],
    }
