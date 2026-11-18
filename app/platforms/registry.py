"""The list of connectors and the rules for which ones run."""

import httpx

from app.config import Settings
from app.platforms.base import Connector
from app.platforms.bluesky import BlueskyConnector
from app.platforms.devto import DevtoConnector
from app.platforms.discord import DiscordConnector
from app.platforms.facebook_page import FacebookPageConnector
from app.platforms.github_gist import GitHubGistConnector
from app.platforms.huggingface import HuggingFaceConnector
from app.platforms.linkedin import LinkedInConnector
from app.platforms.mastodon import MastodonConnector
from app.platforms.telegram import TelegramConnector
from app.platforms.telegraph import TelegraphConnector
from app.platforms.x import XConnector
from app.schemas import ConnectorInfo

# Adding a platform means writing its module and adding one line here.
CONNECTORS: tuple[type[Connector], ...] = (
    BlueskyConnector,
    MastodonConnector,
    TelegramConnector,
    TelegraphConnector,
    GitHubGistConnector,
    DevtoConnector,
    HuggingFaceConnector,
    DiscordConnector,
    XConnector,
    LinkedInConnector,
    FacebookPageConnector,
)


def validate_enabled(settings: Settings) -> None:
    """Fail at startup, not on the first request, when PLATFORMS_ENABLED has a typo."""
    known = {connector.spec.key for connector in CONNECTORS}
    unknown = [key for key in settings.enabled_keys if key not in known]
    if unknown:
        raise ValueError(
            f"Unknown platform(s) in PLATFORMS_ENABLED: {', '.join(unknown)}. "
            f"Known platforms: {', '.join(sorted(known))}"
        )


def build_enabled(client: httpx.AsyncClient, settings: Settings) -> list[Connector]:
    """Instantiate the enabled connectors, in registry order."""
    enabled = set(settings.enabled_keys)
    return [
        connector(client, settings) for connector in CONNECTORS if connector.spec.key in enabled
    ]


def catalog(settings: Settings) -> list[ConnectorInfo]:
    """Describe every connector, enabled or not, without exposing any credential."""
    enabled = set(settings.enabled_keys)
    infos = []
    for connector in CONNECTORS:
        spec = connector.spec
        missing = spec.auth.missing(settings)
        infos.append(
            ConnectorInfo(
                key=spec.key,
                name=spec.name,
                auth=spec.auth.kind,
                enabled=spec.key in enabled,
                configured=not missing,
                missing_settings=missing,
                public=spec.public,
                max_length=spec.max_length,
                docs_url=spec.docs_url,
                notes=spec.notes,
            )
        )
    return infos
