import pytest

from app.config import DEFAULT_PLATFORMS, Settings
from tests.factories import make_settings


def test_defaults() -> None:
    settings = make_settings()
    assert settings.platform_timeout_seconds == 15.0
    assert settings.access_check_timeout_seconds == 5.0
    assert settings.log_format == "console"
    assert settings.platforms_enabled == DEFAULT_PLATFORMS
    assert settings.enabled_keys == (
        "bluesky",
        "mastodon",
        "telegram",
        "telegraph",
        "github_gist",
        "devto",
        "huggingface",
        "discord",
    )
    assert settings.bluesky_app_password is None


def test_enabled_keys_are_normalised() -> None:
    settings = make_settings(platforms_enabled=" Telegram, discord ,,telegram ")
    assert settings.enabled_keys == ("telegram", "discord")


def test_reads_environment_variables(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.setenv("PLATFORMS_ENABLED", "telegram")
    settings = Settings(_env_file=None)
    assert settings.telegram_bot_token is not None
    assert settings.telegram_bot_token.get_secret_value() == "123:abc"
    assert settings.enabled_keys == ("telegram",)


def test_empty_environment_value_counts_as_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEVTO_API_KEY", "")
    assert Settings(_env_file=None).devto_api_key is None


def test_secrets_are_masked_in_repr() -> None:
    settings = make_settings(devto_api_key="super-secret")
    assert "super-secret" not in repr(settings)
