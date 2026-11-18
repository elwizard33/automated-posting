import json

import httpx
import pytest
import respx

from app.platforms.base import PlatformError
from app.platforms.huggingface import HuggingFaceConnector
from tests.factories import make_settings

LINK = "https://example.com"
MESSAGE = f"Launch day {LINK}"


def _connector(client: httpx.AsyncClient, repo_type: str = "model") -> HuggingFaceConnector:
    settings = make_settings(
        huggingface_token="hf_token",
        huggingface_repo_id="demo/posting-test",
        huggingface_repo_type=repo_type,
    )
    return HuggingFaceConnector(client, settings)


async def test_publish_opens_discussion_on_model_repo(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.post(
        "https://huggingface.co/api/models/demo/posting-test/discussions"
    ).respond(200, json={"num": 7, "title": "Launch day"})

    outcome = await _connector(http_client).publish(MESSAGE, LINK)

    assert outcome.posted_url == "https://huggingface.co/demo/posting-test/discussions/7"
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer hf_token"
    assert json.loads(request.content) == {
        "title": "Launch day",
        "description": MESSAGE,
        "pullRequest": False,
    }


@pytest.mark.parametrize(
    ("repo_type", "api_path", "web_path"),
    [
        ("dataset", "datasets", "datasets/demo/posting-test"),
        ("space", "spaces", "spaces/demo/posting-test"),
    ],
)
async def test_other_repo_types_use_their_own_paths(
    http_client: httpx.AsyncClient,
    respx_mock: respx.MockRouter,
    repo_type: str,
    api_path: str,
    web_path: str,
) -> None:
    respx_mock.post(f"https://huggingface.co/api/{api_path}/demo/posting-test/discussions").respond(
        200, json={"num": 3}
    )

    outcome = await _connector(http_client, repo_type).publish(MESSAGE, LINK)

    assert outcome.posted_url == f"https://huggingface.co/{web_path}/discussions/3"


async def test_bad_token_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post("https://huggingface.co/api/models/demo/posting-test/discussions").respond(
        401, json={"error": "Invalid username or password."}
    )

    with pytest.raises(PlatformError, match=r"^HTTP 401: Invalid username or password\.$"):
        await _connector(http_client).publish(MESSAGE, LINK)


async def test_malformed_response_is_reported(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.post("https://huggingface.co/api/models/demo/posting-test/discussions").respond(
        200, json={"title": "Launch day"}
    )

    with pytest.raises(PlatformError, match=r"^Unexpected response from Hugging Face$"):
        await _connector(http_client).publish(MESSAGE, LINK)
