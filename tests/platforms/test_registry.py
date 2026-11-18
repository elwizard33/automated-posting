import httpx
import pytest

from app.config import DEFAULT_PLATFORMS
from app.platforms.registry import CONNECTORS, build_enabled, catalog, validate_enabled
from tests.factories import make_settings

ALL_KEYS = [
    "bluesky",
    "mastodon",
    "telegram",
    "telegraph",
    "github_gist",
    "devto",
    "huggingface",
    "discord",
    "x",
    "linkedin",
    "facebook_page",
]


def test_registry_lists_every_connector_once() -> None:
    assert [connector.spec.key for connector in CONNECTORS] == ALL_KEYS


def test_default_platforms_are_the_eight_live_ones() -> None:
    validate_enabled(make_settings())
    assert DEFAULT_PLATFORMS.split(",") == ALL_KEYS[:8]


def test_validate_enabled_rejects_unknown_keys() -> None:
    settings = make_settings(platforms_enabled="telegram,twiter,myspace")
    with pytest.raises(
        ValueError, match=r"Unknown platform\(s\) in PLATFORMS_ENABLED: twiter, myspace"
    ):
        validate_enabled(settings)


async def test_build_enabled_keeps_registry_order(http_client: httpx.AsyncClient) -> None:
    settings = make_settings(platforms_enabled="discord,x,bluesky")
    connectors = build_enabled(http_client, settings)
    assert [connector.spec.key for connector in connectors] == ["bluesky", "discord", "x"]


def test_catalog_describes_every_connector_without_secrets() -> None:
    settings = make_settings(
        platforms_enabled="telegram,discord",
        telegram_bot_token="123456:ABC-token",
        telegram_channel="@demo",
    )

    infos = {info.key: info for info in catalog(settings)}

    assert list(infos) == ALL_KEYS
    telegram = infos["telegram"]
    assert telegram.enabled is True
    assert telegram.configured is True
    assert telegram.missing_settings == []
    assert telegram.auth == "token_in_request"
    assert telegram.max_length == 4096
    discord = infos["discord"]
    assert discord.enabled is True
    assert discord.configured is False
    assert discord.missing_settings == ["DISCORD_WEBHOOK_URL"]
    assert discord.public is False
    x = infos["x"]
    assert x.enabled is False
    assert x.notes is not None and "paid" in x.notes
    assert "ABC-token" not in "".join(info.model_dump_json() for info in infos.values())
