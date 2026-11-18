import httpx
import pytest
import respx

from app.services.access_checker import AccessChecker

URL = "https://posts.example.test/p/1"


@pytest.mark.parametrize(
    ("status", "expected"),
    [(200, True), (204, True), (401, False), (404, False), (410, False)],
)
async def test_status_decides_visibility(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter, status: int, expected: bool
) -> None:
    respx_mock.get(URL).respond(status)
    assert await AccessChecker(http_client, 5.0).is_public(URL, declared=True) is expected


@pytest.mark.parametrize("status", [403, 429, 500, 503])
async def test_inconclusive_status_keeps_declared_value(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter, status: int
) -> None:
    respx_mock.get(URL).respond(status)
    assert await AccessChecker(http_client, 5.0).is_public(URL, declared=True) is True


async def test_network_error_keeps_declared_value(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(URL).mock(side_effect=httpx.ConnectError("boom"))
    assert await AccessChecker(http_client, 5.0).is_public(URL, declared=True) is True


async def test_redirects_are_followed(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get(URL).respond(302, headers={"Location": "https://posts.example.test/final"})
    respx_mock.get("https://posts.example.test/final").respond(200)
    assert await AccessChecker(http_client, 5.0).is_public(URL, declared=True) is True


async def test_private_platforms_are_not_fetched(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get(URL).respond(200)
    assert await AccessChecker(http_client, 5.0).is_public(URL, declared=False) is False
    assert not route.called


async def test_non_https_urls_are_not_fetched(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    route = respx_mock.get("http://posts.example.test/p/1").respond(200)
    checker = AccessChecker(http_client, 5.0)
    assert await checker.is_public("http://posts.example.test/p/1", declared=True) is True
    assert not route.called


@pytest.mark.parametrize("url", ["https://", "https://[::1/x", "https://exa mple.com/\x00x"])
async def test_unparseable_url_keeps_declared_value(
    http_client: httpx.AsyncClient, url: str
) -> None:
    assert await AccessChecker(http_client, 5.0).is_public(url, declared=True) is True
