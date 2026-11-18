import json

import httpx
import pytest
import respx

from app.platforms.base import PlatformError
from app.platforms.github_gist import GitHubGistConnector
from tests.factories import make_settings

GISTS_URL = "https://api.github.com/gists"
LINK = "https://example.com"
MESSAGE = f"Launch day {LINK}"


def _connector(client: httpx.AsyncClient) -> GitHubGistConnector:
    return GitHubGistConnector(client, make_settings(github_gist_token="ghp_token"))


async def test_publish_creates_public_gist(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.post(GISTS_URL).respond(
        201, json={"id": "abc123", "html_url": "https://gist.github.com/demo/abc123"}
    )

    outcome = await _connector(http_client).publish(MESSAGE, LINK)

    assert outcome.posted_url == "https://gist.github.com/demo/abc123"
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer ghp_token"
    assert request.headers["Accept"] == "application/vnd.github+json"
    assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"
    assert json.loads(request.content) == {
        "description": "Launch day",
        "public": True,
        "files": {"post.md": {"content": MESSAGE}},
    }


async def test_bad_credentials_are_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(GISTS_URL).respond(
        401,
        json={"message": "Bad credentials", "documentation_url": "https://docs.github.com/rest"},
    )

    with pytest.raises(PlatformError, match=r"^HTTP 401: Bad credentials$"):
        await _connector(http_client).publish(MESSAGE, LINK)


async def test_malformed_response_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post(GISTS_URL).respond(201, json={"id": "abc123"})

    with pytest.raises(PlatformError, match=r"^Unexpected response from GitHub Gist$"):
        await _connector(http_client).publish(MESSAGE, LINK)
