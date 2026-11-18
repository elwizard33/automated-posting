"""Hugging Face: open a community discussion on a repository the account owns."""

from typing import ClassVar

from app.platforms.auth import BearerToken
from app.platforms.base import Connector, ConnectorSpec, PublishOutcome
from app.utils.text import derive_title

HUB_URL = "https://huggingface.co"
# Model repositories live at the site root; the other types have a path prefix.
_WEB_PREFIX = {"model": "", "dataset": "datasets/", "space": "spaces/"}


class HuggingFaceConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        key="huggingface",
        name="Hugging Face",
        auth=BearerToken(fields=("huggingface_token", "huggingface_repo_id")),
        docs_url="https://huggingface.co/docs/huggingface_hub/guides/community",
    )

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        repo_id = self._value("huggingface_repo_id")
        repo_type = self._settings.huggingface_repo_type
        response = await self._request(
            "POST",
            f"{HUB_URL}/api/{repo_type}s/{repo_id}/discussions",
            headers=self._auth_headers(),
            json={
                "title": derive_title(message, link),
                "description": message,
                "pullRequest": False,
            },
        )
        number = response.json()["num"]
        return PublishOutcome(
            posted_url=f"{HUB_URL}/{_WEB_PREFIX[repo_type]}{repo_id}/discussions/{number}"
        )
