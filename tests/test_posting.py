from collections.abc import AsyncIterator

import httpx
import pytest
import respx

from app.api.dependencies import get_http_client
from app.config import get_settings
from app.main import app, create_app, lifespan
from tests.factories import make_settings

LINK = "https://example.com"
MESSAGE = f"Check out our latest business platform and grow your online visibility. {LINK}"
TELEGRAM_URL = "https://api.telegram.org/bot123456:ABC-token/sendMessage"
DISCORD_URL = "https://discord.com/api/webhooks/111/hook-token"
RESULT_FIELDS = {"platform", "status", "posted_url", "public_access", "date", "time", "error"}


@pytest.fixture
async def api(http_client: httpx.AsyncClient) -> AsyncIterator[httpx.AsyncClient]:
    """The app with Telegram and Discord configured and Mastodon enabled but not configured."""
    settings = make_settings(
        platforms_enabled="mastodon,telegram,discord",
        telegram_bot_token="123456:ABC-token",
        telegram_channel="@demo_channel",
        discord_webhook_url=DISCORD_URL,
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_http_client] = lambda: http_client
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


def _mock_platforms(respx_mock: respx.MockRouter, *, telegram_status: int = 200) -> None:
    if telegram_status == 200:
        respx_mock.post(TELEGRAM_URL).respond(200, json={"ok": True, "result": {"message_id": 42}})
        respx_mock.get("https://t.me/demo_channel/42").respond(200)
    else:
        respx_mock.post(TELEGRAM_URL).respond(
            telegram_status, json={"ok": False, "description": "Unauthorized"}
        )
    respx_mock.get(DISCORD_URL).respond(200, json={"guild_id": "222", "channel_id": "333"})
    respx_mock.post(DISCORD_URL).respond(200, json={"id": "444", "channel_id": "333"})


async def test_posting_publishes_to_every_enabled_platform(
    api: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    _mock_platforms(respx_mock)

    response = await api.post("/posting", json={"message": MESSAGE})

    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    body = response.json()
    assert body["success"] is True
    assert body["summary"] == {"total": 3, "succeeded": 2, "failed": 1}
    assert [result["platform"] for result in body["results"]] == ["Mastodon", "Telegram", "Discord"]
    assert all(set(result) == RESULT_FIELDS for result in body["results"])

    mastodon, telegram, discord = body["results"]
    assert mastodon == {
        "platform": "Mastodon",
        "status": "failed",
        "posted_url": None,
        "public_access": False,
        "date": None,
        "time": None,
        "error": "Not configured: set MASTODON_ACCESS_TOKEN, MASTODON_BASE_URL",
    }
    assert telegram["status"] == "success"
    assert telegram["posted_url"] == "https://t.me/demo_channel/42"
    assert telegram["public_access"] is True
    assert len(telegram["date"]) == 10 and telegram["date"][4] == "-"
    assert len(telegram["time"]) == 8 and telegram["time"][2] == ":"
    assert telegram["error"] is None
    assert discord["status"] == "success"
    assert discord["posted_url"] == "https://discord.com/channels/222/333/444"
    assert discord["public_access"] is False


async def test_one_platform_failing_does_not_block_the_rest(
    api: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    _mock_platforms(respx_mock, telegram_status=401)

    body = (await api.post("/posting", json={"message": MESSAGE})).json()

    assert body["success"] is True
    assert body["summary"] == {"total": 3, "succeeded": 1, "failed": 2}
    assert body["results"][1]["error"] == "HTTP 401: Unauthorized"
    assert body["results"][2]["status"] == "success"


@pytest.mark.parametrize(
    ("payload", "field", "message"),
    [
        ({"message": "a" * 201}, "message", "Message must not exceed 200 characters (got 201)"),
        ({"message": "no link here"}, "message", "Message must contain exactly one link (found 0)"),
        (
            {"message": "https://a.example.com https://b.example.com"},
            "message",
            "Message must contain exactly one link (found 2)",
        ),
        ({"message": "see www.example.com"}, "message", "Link must start with http:// or https://"),
        ({"message": "see https://exa_mple.com"}, "message", "Link is not a valid URL"),
        ({"message": "   "}, "message", "Message must not be empty"),
        ({}, "message", "Field is required"),
        ({"message": 42}, "message", "Must be a string"),
        ({"message": MESSAGE, "platforms": ["x"]}, "platforms", "Unknown field"),
    ],
)
async def test_invalid_input_returns_422_in_one_shape(
    api: httpx.AsyncClient, payload: dict[str, object], field: str, message: str
) -> None:
    response = await api.post("/posting", json=payload)

    assert response.status_code == 422
    assert response.json() == {
        "success": False,
        "error": {
            "code": "validation_error",
            "message": "Request validation failed",
            "details": [{"field": field, "message": message}],
        },
    }


async def test_malformed_json_uses_the_same_error_shape(api: httpx.AsyncClient) -> None:
    response = await api.post(
        "/posting", content=b'{"message": ', headers={"Content-Type": "application/json"}
    )

    assert response.status_code == 422
    body = response.json()
    assert body["success"] is False
    assert body["error"]["details"][0]["message"] == "Request body is not valid JSON"


async def test_non_object_body_uses_the_same_error_shape(api: httpx.AsyncClient) -> None:
    response = await api.post("/posting", json=["not", "an", "object"])

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_invalid_input_never_reaches_a_platform(
    api: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    await api.post("/posting", json={"message": "no link here"})

    assert len(respx_mock.calls) == 0


async def test_unknown_route_uses_the_error_shape(api: httpx.AsyncClient) -> None:
    response = await api.get("/nope")

    assert response.status_code == 404
    assert response.json() == {
        "success": False,
        "error": {"code": "http_error", "message": "Not Found", "details": []},
    }


async def test_connectors_lists_all_platforms_without_secrets(api: httpx.AsyncClient) -> None:
    response = await api.get("/connectors")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 11
    by_key = {item["key"]: item for item in body}
    assert by_key["telegram"]["enabled"] is True
    assert by_key["telegram"]["configured"] is True
    assert by_key["mastodon"]["missing_settings"] == ["MASTODON_ACCESS_TOKEN", "MASTODON_BASE_URL"]
    assert by_key["x"]["enabled"] is False
    assert "ABC-token" not in response.text
    assert "hook-token" not in response.text


async def test_health(api: httpx.AsyncClient) -> None:
    response = await api.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_demo_page_is_served_at_root(api: httpx.AsyncClient) -> None:
    response = await api.get("/")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "Automated Posting" in response.text


async def test_docs_describe_the_endpoint_and_its_errors(api: httpx.AsyncClient) -> None:
    schema = (await api.get("/openapi.json")).json()

    operation = schema["paths"]["/posting"]["post"]
    assert set(operation["responses"]) == {"200", "422"}
    assert (
        operation["responses"]["422"]["content"]["application/json"]["example"]["success"] is False
    )
    assert (
        schema["components"]["schemas"]["PostingRequest"]["properties"]["message"]["maxLength"]
        == 200
    )
    assert (await api.get("/docs")).status_code == 200


async def test_unexpected_errors_return_a_generic_500(http_client: httpx.AsyncClient) -> None:
    crashing_app = create_app()

    @crashing_app.get("/boom")
    async def boom() -> None:
        raise RuntimeError("secret detail")

    transport = httpx.ASGITransport(app=crashing_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/boom")

    assert response.status_code == 500
    assert response.json() == {
        "success": False,
        "error": {"code": "internal_error", "message": "Internal server error", "details": []},
    }


async def test_startup_fails_on_unknown_platform(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PLATFORMS_ENABLED", "telegram,myspace")
    monkeypatch.chdir("/")
    get_settings.cache_clear()
    try:
        with pytest.raises(ValueError, match=r"Unknown platform"):
            async with lifespan(app):
                pass
    finally:
        get_settings.cache_clear()


async def test_startup_creates_and_closes_the_shared_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir("/")
    get_settings.cache_clear()
    try:
        async with lifespan(app):
            client = app.state.http_client
            assert client.headers["User-Agent"] == "automated-posting/1.0"
            assert client.timeout.read == 15.0
            assert not client.is_closed
        assert client.is_closed
    finally:
        get_settings.cache_clear()


async def test_client_timeout_follows_the_platform_timeout_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PLATFORM_TIMEOUT_SECONDS", "30")
    monkeypatch.chdir("/")
    get_settings.cache_clear()
    try:
        async with lifespan(app):
            timeout = app.state.http_client.timeout
            assert (timeout.connect, timeout.read, timeout.write, timeout.pool) == (30.0,) * 4
    finally:
        get_settings.cache_clear()
