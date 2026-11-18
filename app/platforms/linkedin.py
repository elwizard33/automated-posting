"""LinkedIn: create a public post as a member or an organisation."""

import re
from typing import ClassVar

from app.platforms.auth import BearerToken
from app.platforms.base import Connector, ConnectorSpec, PublishOutcome

API_URL = "https://api.linkedin.com"
_RESERVED_RE = re.compile(r"([\\|{}@\[\]()<>#*_~])")


class LinkedInConnector(Connector):
    spec: ClassVar[ConnectorSpec] = ConnectorSpec(
        key="linkedin",
        name="LinkedIn",
        auth=BearerToken(fields=("linkedin_access_token", "linkedin_author_urn")),
        docs_url=(
            "https://learn.microsoft.com/en-us/linkedin/marketing/"
            "community-management/shares/posts-api"
        ),
        max_length=3000,
        notes="Off by default: posting needs an approved LinkedIn app. Not live-tested.",
    )

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        response = await self._request(
            "POST",
            f"{API_URL}/rest/posts",
            headers={
                **self._auth_headers(),
                "LinkedIn-Version": self._settings.linkedin_api_version,
                "X-Restli-Protocol-Version": "2.0.0",
            },
            json={
                "author": self._value("linkedin_author_urn"),
                "commentary": escape_commentary(message),
                "visibility": "PUBLIC",
                "distribution": {
                    "feedDistribution": "MAIN_FEED",
                    "targetEntities": [],
                    "thirdPartyDistributionChannels": [],
                },
                "lifecycleState": "PUBLISHED",
                "isReshareDisabledByAuthor": False,
            },
        )
        # The new post's URN comes back in a header; the body is empty.
        post_urn = response.headers["x-restli-id"]
        return PublishOutcome(posted_url=f"https://www.linkedin.com/feed/update/{post_urn}/")


def escape_commentary(text: str) -> str:
    """Escape the characters LinkedIn's post text format treats as markup."""
    return _RESERVED_RE.sub(r"\\\1", text)
