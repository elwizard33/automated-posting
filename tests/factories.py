from typing import Any

from app.config import Settings


def make_settings(**overrides: Any) -> Settings:
    """Settings built only from the given values, never from a real .env file."""
    return Settings(_env_file=None, **overrides)
