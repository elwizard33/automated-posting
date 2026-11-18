"""Application settings, read from environment variables or a local .env file."""

from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_PLATFORMS = "bluesky,mastodon,telegram,telegraph,github_gist,devto,huggingface,discord"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_ignore_empty=True,
        extra="ignore",
    )

    log_format: Literal["console", "json"] = "console"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    platform_timeout_seconds: float = 15.0
    access_check_timeout_seconds: float = 5.0
    platforms_enabled: str = DEFAULT_PLATFORMS

    bluesky_handle: str | None = None
    bluesky_app_password: SecretStr | None = None

    mastodon_access_token: SecretStr | None = None
    mastodon_base_url: str | None = None

    telegram_bot_token: SecretStr | None = None
    telegram_channel: str | None = None

    telegraph_access_token: SecretStr | None = None

    github_gist_token: SecretStr | None = None

    devto_api_key: SecretStr | None = None

    huggingface_token: SecretStr | None = None
    huggingface_repo_id: str | None = None
    huggingface_repo_type: Literal["model", "dataset", "space"] = "model"

    discord_webhook_url: SecretStr | None = None

    x_access_token: SecretStr | None = None

    linkedin_access_token: SecretStr | None = None
    linkedin_author_urn: str | None = None
    linkedin_api_version: str = "202610"

    facebook_page_access_token: SecretStr | None = None
    facebook_page_id: str | None = None
    facebook_graph_version: str = "v23.0"

    @property
    def enabled_keys(self) -> tuple[str, ...]:
        """Connector keys from PLATFORMS_ENABLED, in the order given, without blanks."""
        keys = (key.strip().lower() for key in self.platforms_enabled.split(","))
        return tuple(dict.fromkeys(key for key in keys if key))


@lru_cache
def get_settings() -> Settings:
    return Settings()
