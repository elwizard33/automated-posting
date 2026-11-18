"""Checks whether a published URL opens without logging in."""

import httpx
import structlog

log = structlog.get_logger(__name__)

_NOT_PUBLIC_STATUSES = frozenset({401, 404, 410})


class AccessChecker:
    def __init__(self, client: httpx.AsyncClient, timeout_seconds: float) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds

    async def is_public(self, url: str, *, declared: bool) -> bool:
        """Fetch the URL anonymously; fall back to the connector's declared visibility.

        This proves the URL is reachable without credentials, not that the content is
        there: some sites answer 200 for any path. Bot challenges, rate limits and
        network errors say nothing about visibility, so they keep the declared value.
        """
        if not declared or not url.startswith("https://"):
            return declared
        try:
            response = await self._client.get(
                url, follow_redirects=True, timeout=self._timeout_seconds
            )
        except (httpx.HTTPError, httpx.InvalidURL) as exc:
            log.warning("access_check_failed", url=url, reason=type(exc).__name__)
            return declared
        if response.is_success:
            return True
        if response.status_code in _NOT_PUBLIC_STATUSES:
            return False
        log.warning("access_check_inconclusive", url=url, status_code=response.status_code)
        return declared
