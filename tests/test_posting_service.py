import asyncio
from datetime import UTC, datetime
from typing import ClassVar

import httpx
import respx

from app.platforms.auth import BearerToken
from app.platforms.base import Connector, ConnectorSpec, PlatformError, PublishOutcome
from app.schemas import PostStatus
from app.services.access_checker import AccessChecker
from app.services.posting_service import PostingService
from tests.factories import make_settings

LINK = "https://example.com"
MESSAGE = f"Launch day {LINK}"
FIXED_NOW = datetime(2026, 11, 18, 14, 3, 22, 987654, tzinfo=UTC)


def _spec(name: str, *, public: bool = True, max_length: int | None = None) -> ConnectorSpec:
    return ConnectorSpec(
        key=name.lower(),
        name=name,
        auth=BearerToken(fields=("devto_api_key",)),
        docs_url="https://example.test/docs",
        public=public,
        max_length=max_length,
    )


class Works(Connector):
    spec: ClassVar[ConnectorSpec] = _spec("Works")

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        return PublishOutcome(posted_url="https://works.example.test/p/1")


class Private(Connector):
    spec: ClassVar[ConnectorSpec] = _spec("Private", public=False)

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        return PublishOutcome(posted_url="https://private.example.test/p/1")


class Rejects(Connector):
    spec: ClassVar[ConnectorSpec] = _spec("Rejects")

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        raise PlatformError("HTTP 401: Bad credentials")


class Hangs(Connector):
    spec: ClassVar[ConnectorSpec] = _spec("Hangs")

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        await asyncio.sleep(30)
        raise AssertionError("unreachable")


class Offline(Connector):
    spec: ClassVar[ConnectorSpec] = _spec("Offline")

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        raise httpx.ConnectError("connect to https://api.test/bot123456:SECRET/send failed")


class ReadTimesOut(Connector):
    spec: ClassVar[ConnectorSpec] = _spec("ReadTimesOut")

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        raise httpx.ReadTimeout("slow")


class Crashes(Connector):
    spec: ClassVar[ConnectorSpec] = _spec("Crashes")

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        raise RuntimeError("bug with SECRET inside")


class Short(Connector):
    spec: ClassVar[ConnectorSpec] = _spec("Short", max_length=10)

    async def _publish(self, message: str, link: str) -> PublishOutcome:
        raise AssertionError("must not be called")


def _service(
    client: httpx.AsyncClient,
    *connector_types: type[Connector],
    configured: bool = True,
    timeout_seconds: float = 0.05,
) -> PostingService:
    settings = make_settings(devto_api_key="k1") if configured else make_settings()
    return PostingService(
        connectors=[connector(client, settings) for connector in connector_types],
        access_checker=AccessChecker(client, 1.0),
        timeout_seconds=timeout_seconds,
        clock=lambda: FIXED_NOW,
    )


async def test_success_result_has_url_date_and_time(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get("https://works.example.test/p/1").respond(200)

    response = await _service(http_client, Works).publish(MESSAGE, LINK)

    assert response.success is True
    assert response.summary.model_dump() == {"total": 1, "succeeded": 1, "failed": 0}
    assert response.results[0].model_dump(mode="json") == {
        "platform": "Works",
        "status": "success",
        "posted_url": "https://works.example.test/p/1",
        "public_access": True,
        "date": "2026-11-18",
        "time": "14:03:22",
        "error": None,
    }


async def test_public_access_is_false_when_the_url_needs_login(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get("https://works.example.test/p/1").respond(404)

    response = await _service(http_client, Works).publish(MESSAGE, LINK)

    assert response.results[0].status is PostStatus.SUCCESS
    assert response.results[0].public_access is False


async def test_private_platform_reports_public_access_false(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    response = await _service(http_client, Private).publish(MESSAGE, LINK)

    assert response.results[0].status is PostStatus.SUCCESS
    assert response.results[0].public_access is False


async def test_one_failure_does_not_stop_the_others(
    http_client: httpx.AsyncClient, respx_mock: respx.MockRouter
) -> None:
    respx_mock.get("https://works.example.test/p/1").respond(200)
    service = _service(http_client, Rejects, Hangs, Offline, ReadTimesOut, Crashes, Works)

    response = await service.publish(MESSAGE, LINK)

    assert response.success is True
    assert response.summary.model_dump() == {"total": 6, "succeeded": 1, "failed": 5}
    assert [
        (result.platform, result.status.value, result.error) for result in response.results
    ] == [
        ("Rejects", "failed", "HTTP 401: Bad credentials"),
        ("Hangs", "failed", "Timed out after 0.05 seconds"),
        ("Offline", "failed", "Network error (ConnectError)"),
        ("ReadTimesOut", "failed", "Timed out after 0.05 seconds"),
        ("Crashes", "failed", "Unexpected error"),
        ("Works", "success", None),
    ]


async def test_failed_result_matches_the_documented_shape(http_client: httpx.AsyncClient) -> None:
    response = await _service(http_client, Rejects).publish(MESSAGE, LINK)

    assert response.success is False
    assert response.results[0].model_dump(mode="json") == {
        "platform": "Rejects",
        "status": "failed",
        "posted_url": None,
        "public_access": False,
        "date": None,
        "time": None,
        "error": "HTTP 401: Bad credentials",
    }


async def test_errors_never_contain_secrets_from_exceptions(http_client: httpx.AsyncClient) -> None:
    response = await _service(http_client, Offline, Crashes).publish(MESSAGE, LINK)

    assert "SECRET" not in response.model_dump_json()


async def test_unconfigured_platform_is_reported_not_called(
    http_client: httpx.AsyncClient,
) -> None:
    response = await _service(http_client, Works, configured=False).publish(MESSAGE, LINK)

    assert response.success is False
    assert response.results[0].error == "Not configured: set DEVTO_API_KEY"


async def test_message_longer_than_platform_limit_is_not_sent(
    http_client: httpx.AsyncClient,
) -> None:
    response = await _service(http_client, Short).publish(MESSAGE, LINK)

    assert response.results[0].error == "Message is longer than Short's 10-character limit"


async def test_no_enabled_platforms_gives_an_empty_unsuccessful_response(
    http_client: httpx.AsyncClient,
) -> None:
    response = await _service(http_client).publish(MESSAGE, LINK)

    assert response.success is False
    assert response.summary.model_dump() == {"total": 0, "succeeded": 0, "failed": 0}
    assert response.results == []


async def test_platforms_run_concurrently(http_client: httpx.AsyncClient) -> None:
    service = _service(http_client, Hangs, Hangs, Hangs, timeout_seconds=0.2)

    started = asyncio.get_running_loop().time()
    await service.publish(MESSAGE, LINK)

    assert asyncio.get_running_loop().time() - started < 0.5


class BrokenChecker(AccessChecker):
    async def is_public(self, url: str, *, declared: bool) -> bool:
        raise RuntimeError("checker bug")


async def test_access_check_failure_keeps_the_post_as_success(
    http_client: httpx.AsyncClient,
) -> None:
    settings = make_settings(devto_api_key="k1")
    service = PostingService(
        connectors=[Works(http_client, settings)],
        access_checker=BrokenChecker(http_client, 1.0),
        timeout_seconds=1.0,
        clock=lambda: FIXED_NOW,
    )

    response = await service.publish(MESSAGE, LINK)

    assert response.results[0].status is PostStatus.SUCCESS
    assert response.results[0].posted_url == "https://works.example.test/p/1"
    assert response.results[0].public_access is True
