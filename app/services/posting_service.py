"""Publishes one message to every enabled platform at the same time."""

import asyncio
import time
from collections.abc import Callable, Sequence
from datetime import UTC, datetime

import httpx
import structlog

from app.platforms.base import Connector, PlatformError
from app.schemas import PlatformResult, PostingResponse, PostStatus, Summary
from app.services.access_checker import AccessChecker

log = structlog.get_logger(__name__)


def utc_now() -> datetime:
    return datetime.now(UTC)


class PostingService:
    def __init__(
        self,
        connectors: Sequence[Connector],
        access_checker: AccessChecker,
        timeout_seconds: float,
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        self._connectors = connectors
        self._access_checker = access_checker
        self._timeout_seconds = timeout_seconds
        self._clock = clock

    async def publish(self, message: str, link: str) -> PostingResponse:
        # _publish_one never raises, so one platform failing cannot cancel the others.
        results = await asyncio.gather(
            *(self._publish_one(connector, message, link) for connector in self._connectors)
        )
        succeeded = sum(result.status is PostStatus.SUCCESS for result in results)
        return PostingResponse(
            success=succeeded > 0,
            summary=Summary(
                total=len(results), succeeded=succeeded, failed=len(results) - succeeded
            ),
            results=list(results),
        )

    async def _publish_one(self, connector: Connector, message: str, link: str) -> PlatformResult:
        spec = connector.spec
        started = time.perf_counter()

        def failed(error: str) -> PlatformResult:
            log.warning(
                "platform_post",
                platform=spec.name,
                status="failed",
                duration_ms=_elapsed_ms(started),
                error=error,
            )
            return PlatformResult(platform=spec.name, status=PostStatus.FAILED, error=error)

        missing = connector.missing_settings()
        if missing:
            return failed(f"Not configured: set {', '.join(missing)}")
        if spec.max_length is not None and len(message) > spec.max_length:
            return failed(f"Message is longer than {spec.name}'s {spec.max_length}-character limit")

        # No retries: a publish call that timed out may still have gone through,
        # and sending it again would post the message twice.
        try:
            async with asyncio.timeout(self._timeout_seconds):
                outcome = await connector.publish(message, link)
        except PlatformError as exc:
            return failed(str(exc))
        except (TimeoutError, httpx.TimeoutException):
            return failed(f"Timed out after {self._timeout_seconds:g} seconds")
        except httpx.HTTPError as exc:
            # Only the error type: httpx messages can include the request URL,
            # and some platforms carry their token in it.
            return failed(f"Network error ({type(exc).__name__})")
        except Exception:
            log.exception("platform_post_crashed", platform=spec.name)
            return failed("Unexpected error")

        posted_at = self._clock()
        try:
            public_access = await self._access_checker.is_public(
                outcome.posted_url, declared=spec.public
            )
        except Exception:
            # The post exists at this point; a broken check must not hide its URL.
            log.exception("access_check_crashed", platform=spec.name)
            public_access = spec.public
        log.info(
            "platform_post",
            platform=spec.name,
            status="success",
            duration_ms=_elapsed_ms(started),
            posted_url=outcome.posted_url,
            public_access=public_access,
        )
        return PlatformResult(
            platform=spec.name,
            status=PostStatus.SUCCESS,
            posted_url=outcome.posted_url,
            public_access=public_access,
            date=posted_at.strftime("%Y-%m-%d"),
            time=posted_at.strftime("%H:%M:%S"),
        )


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)
