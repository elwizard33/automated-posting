"""Exception handlers that give every error response the same JSON shape."""

from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.schemas import ErrorBody, ErrorDetail, ErrorResponse

log = structlog.get_logger(__name__)

_FRIENDLY_MESSAGES = {
    "missing": "Field is required",
    "extra_forbidden": "Unknown field",
    "string_type": "Must be a string",
    "json_invalid": "Request body is not valid JSON",
    "model_attributes_type": "Request body must be a JSON object",
}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details = [_to_detail(error) for error in exc.errors()]
        return _error_response(422, "validation_error", "Request validation failed", details)

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return _error_response(exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        log.error("unhandled_error", path=request.url.path, exc_info=exc)
        return _error_response(500, "internal_error", "Internal server error")


def _to_detail(error: dict[str, Any]) -> ErrorDetail:
    location = [str(part) for part in error["loc"] if part != "body"]
    message = _FRIENDLY_MESSAGES.get(error["type"]) or str(error["msg"]).removeprefix(
        "Value error, "
    )
    return ErrorDetail(field=".".join(location) or "body", message=message)


def _error_response(
    status_code: int, code: str, message: str, details: list[ErrorDetail] | None = None
) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details or []))
    return JSONResponse(status_code=status_code, content=body.model_dump())
