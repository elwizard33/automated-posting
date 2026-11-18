"""Providers wired into routes with Depends(), so tests can replace them."""

from typing import Annotated

import httpx
from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.platforms.registry import build_enabled
from app.services.access_checker import AccessChecker
from app.services.posting_service import PostingService

SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_http_client(request: Request) -> httpx.AsyncClient:
    client: httpx.AsyncClient = request.app.state.http_client
    return client


HttpClientDep = Annotated[httpx.AsyncClient, Depends(get_http_client)]


def get_posting_service(settings: SettingsDep, client: HttpClientDep) -> PostingService:
    return PostingService(
        connectors=build_enabled(client, settings),
        access_checker=AccessChecker(client, settings.access_check_timeout_seconds),
        timeout_seconds=settings.platform_timeout_seconds,
    )


PostingServiceDep = Annotated[PostingService, Depends(get_posting_service)]
