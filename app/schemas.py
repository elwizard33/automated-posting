"""Request and response models for the API."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.text import find_links, validate_link

MAX_MESSAGE_LENGTH = 200
EXAMPLE_MESSAGE = (
    "Check out our latest business platform and grow your online visibility. https://example.com"
)


class PostingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(
        description=(
            f"Text to publish. At most {MAX_MESSAGE_LENGTH} characters and exactly one "
            "http(s) link."
        ),
        examples=[EXAMPLE_MESSAGE],
        json_schema_extra={"maxLength": MAX_MESSAGE_LENGTH},
    )

    @field_validator("message")
    @classmethod
    def _check_message(cls, value: str) -> str:
        if not value:
            raise ValueError("Message must not be empty")
        if len(value) > MAX_MESSAGE_LENGTH:
            raise ValueError(
                f"Message must not exceed {MAX_MESSAGE_LENGTH} characters (got {len(value)})"
            )
        links = find_links(value)
        if len(links) != 1:
            raise ValueError(f"Message must contain exactly one link (found {len(links)})")
        validate_link(links[0])
        return value

    @property
    def link(self) -> str:
        return find_links(self.message)[0]


class PostStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"


class PlatformResult(BaseModel):
    platform: str = Field(examples=["Bluesky"])
    status: PostStatus
    posted_url: str | None = Field(default=None, examples=["https://bsky.app/profile/x/post/3k"])
    public_access: bool = False
    date: str | None = Field(
        default=None, description="UTC date, YYYY-MM-DD", examples=["2026-11-18"]
    )
    time: str | None = Field(default=None, description="UTC time, HH:MM:SS", examples=["14:03:22"])
    error: str | None = None


class Summary(BaseModel):
    total: int
    succeeded: int
    failed: int


class PostingResponse(BaseModel):
    success: bool = Field(description="True when at least one platform published the message")
    summary: Summary
    results: list[PlatformResult]


class ConnectorInfo(BaseModel):
    key: str
    name: str
    auth: str
    enabled: bool
    configured: bool
    missing_settings: list[str]
    public: bool
    max_length: int | None
    docs_url: str
    notes: str | None


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ErrorDetail(BaseModel):
    field: str
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[ErrorDetail] = Field(default_factory=list)


class ErrorResponse(BaseModel):
    success: Literal[False] = False
    error: ErrorBody
