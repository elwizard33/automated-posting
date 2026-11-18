import pytest
from pydantic import ValidationError

from app.schemas import PostingRequest

LINK = "https://example.com"


def _error(message: str) -> str:
    with pytest.raises(ValidationError) as excinfo:
        PostingRequest(message=message)
    errors = excinfo.value.errors()
    assert len(errors) == 1
    return str(errors[0]["msg"]).removeprefix("Value error, ")


def test_accepts_sample_message() -> None:
    request = PostingRequest(
        message="Check out our latest business platform and grow your online visibility. "
        "https://example.com"
    )
    assert request.link == LINK


def test_strips_surrounding_whitespace() -> None:
    request = PostingRequest(message=f"   hello {LINK}  \n")
    assert request.message == f"hello {LINK}"


def test_accepts_exactly_200_characters() -> None:
    message = "a" * (200 - len(LINK) - 1) + " " + LINK
    assert len(message) == 200
    assert PostingRequest(message=message).link == LINK


def test_rejects_201_characters() -> None:
    message = "a" * (201 - len(LINK) - 1) + " " + LINK
    assert _error(message) == "Message must not exceed 200 characters (got 201)"


def test_length_is_measured_after_stripping() -> None:
    message = "a" * (200 - len(LINK) - 1) + " " + LINK + "     "
    assert PostingRequest(message=message).link == LINK


@pytest.mark.parametrize("message", ["", "    "])
def test_rejects_empty_message(message: str) -> None:
    assert _error(message) == "Message must not be empty"


def test_rejects_message_without_link() -> None:
    assert _error("no link at all") == "Message must contain exactly one link (found 0)"


def test_rejects_two_links() -> None:
    message = "first https://a.example.com second https://b.example.com"
    assert _error(message) == "Message must contain exactly one link (found 2)"


def test_www_link_counts_towards_the_limit() -> None:
    assert (
        _error("www.a.com and https://b.example.com")
        == "Message must contain exactly one link (found 2)"
    )


def test_rejects_link_without_scheme() -> None:
    assert _error("visit www.example.com") == "Link must start with http:// or https://"


def test_rejects_non_http_scheme() -> None:
    assert _error("files at ftp://example.com/x") == "Link must start with http:// or https://"


def test_rejects_localhost_link() -> None:
    assert _error("see http://localhost:4000/docs") == "Link must point to a public domain name"


def test_trailing_punctuation_is_not_part_of_the_link() -> None:
    assert PostingRequest(message=f"Read this: {LINK}.").link == LINK


def test_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError) as excinfo:
        PostingRequest.model_validate({"message": f"hi {LINK}", "platforms": ["x"]})
    assert excinfo.value.errors()[0]["type"] == "extra_forbidden"
