"""GitHub Gist: publish the message as a public gist."""

from typing import ClassVar

from app.platforms.auth import BearerToken
from app.platforms.base import Connector, ConnectorSpec, PublishOutcome
from app.utils.text import derive_title

API_URL = "https://api.github.com"


class GitHubGistConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        key="github_gist",
        name="GitHub Gist",
        auth=BearerToken(fields=("github_gist_token",)),
        docs_url="https://docs.github.com/en/rest/gists/gists#create-a-gist",
    )

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        response = await self._request(
            "POST",
            f"{API_URL}/gists",
            headers={
                **self._auth_headers(),
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={
                "description": derive_title(message, link),
                "public": True,
                "files": {"post.md": {"content": message}},
            },
        )
        return PublishOutcome(posted_url=response.json()["html_url"])
