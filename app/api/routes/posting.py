from typing import Annotated, Any

from fastapi import APIRouter, Body

from app.api.dependencies import PostingServiceDep
from app.schemas import EXAMPLE_MESSAGE, ErrorResponse, PostingRequest, PostingResponse

router = APIRouter(tags=["posting"])

_VALIDATION_ERROR_EXAMPLE: dict[str, Any] = {
    "success": False,
    "error": {
        "code": "validation_error",
        "message": "Request validation failed",
        "details": [
            {"field": "message", "message": "Message must contain exactly one link (found 2)"}
        ],
    },
}


@router.post(
    "/posting",
    summary="Publish a message to every enabled platform",
    description=(
        "Validates the message, then posts it to all enabled platforms at the same time. "
        "Each platform is reported separately, so one failure never hides the others. "
        "The response is 200 whenever the input is valid; check `success` and `results`."
    ),
    responses={
        422: {
            "model": ErrorResponse,
            "description": "The message broke a validation rule",
            "content": {"application/json": {"example": _VALIDATION_ERROR_EXAMPLE}},
        }
    },
)
async def create_posting(
    body: Annotated[
        PostingRequest,
        Body(
            openapi_examples={
                "valid": {"summary": "Valid message", "value": {"message": EXAMPLE_MESSAGE}},
                "two_links": {
                    "summary": "Rejected: two links",
                    "value": {"message": "See https://a.example.com and https://b.example.com"},
                },
            }
        ),
    ],
    service: PostingServiceDep,
) -> PostingResponse:
    return await service.publish(body.message, body.link)
