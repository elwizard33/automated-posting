"""Application entry point: `uvicorn app.main:app --host 0.0.0.0 --port 4000`."""

import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import structlog
from fastapi import FastAPI, Request, Response
from fastapi.responses import FileResponse

from app.api.routes import connectors, health, posting
from app.config import get_settings
from app.core.errors import register_error_handlers
from app.core.logging import configure_logging
from app.platforms.registry import validate_enabled

USER_AGENT = "automated-posting/1.0"
INDEX_PAGE = Path(__file__).parent / "static" / "index.html"


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings)
    validate_enabled(settings)
    # One client for the whole process, so connections to each platform are reused.
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(settings.platform_timeout_seconds),
        headers={"User-Agent": USER_AGENT},
    ) as client:
        app.state.http_client = client
        yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Automated Multi-Platform Posting",
        version="1.0.0",
        description="Publishes one short message with a single link to several platforms.",
        lifespan=lifespan,
    )
    register_error_handlers(app)

    @app.middleware("http")
    async def add_request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        request_id = uuid.uuid4().hex[:12]
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    app.include_router(posting.router)
    app.include_router(connectors.router)
    app.include_router(health.router)

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(INDEX_PAGE)

    return app


app = create_app()
