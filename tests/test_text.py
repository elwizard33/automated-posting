import pytest

from app.utils.text import derive_title, find_links, validate_link

SAMPLE = (
    "Check out our latest business platform and grow your online visibility. https://example.com"
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("no links here", []),
        (SAMPLE, ["https://example.com"]),
        ("see https://example.com.", ["https://example.com"]),
        ("(https://example.com/a?b=1)", ["https://example.com/a?b=1"]),
        (
            "see https://en.wikipedia.org/wiki/Foo_(bar)",
            ["https://en.wikipedia.org/wiki/Foo_(bar)"],
        ),
        (
            "(see https://en.wikipedia.org/wiki/Foo_(bar))",
            ["https://en.wikipedia.org/wiki/Foo_(bar)"],
        ),
        ("https://en.wikipedia.org/wiki/Foo_(bar).", ["https://en.wikipedia.org/wiki/Foo_(bar)"]),
        ("go to www.example.com now", ["www.example.com"]),
        ("ftp://files.example.com/x", ["ftp://files.example.com/x"]),
        ("www.a.com https://b.com", ["www.a.com", "https://b.com"]),
        ("HTTPS://EXAMPLE.COM", ["HTTPS://EXAMPLE.COM"]),
        ("plain example.com and Node.js", []),
        ("mail me at me@www.example.com", []),
    ],
)
def test_find_links(text: str, expected: list[str]) -> None:
    assert find_links(text) == expected


@pytest.mark.parametrize(
    "link",
    [
        "https://example.com",
        "http://example.com/path?q=1#top",
        "https://sub.example.co.uk:8443/x",
        "https://xn--bcher-kva.example",
        "https://bücher.example",
        "HTTPS://Example.COM/Path",
    ],
)
def test_validate_link_accepts_public_http_urls(link: str) -> None:
    validate_link(link)


@pytest.mark.parametrize(
    ("link", "message"),
    [
        ("www.example.com", "Link must start with http:// or https://"),
        ("ftp://example.com", "Link must start with http:// or https://"),
        ("https://", "Link is not a valid URL"),
        ("https://example", "Link is not a valid URL"),
        ("https://exa_mple.com", "Link is not a valid URL"),
        ("https://example.c", "Link is not a valid URL"),
        ("https://example.com:99999", "Link is not a valid URL"),
        ("https://user:pw@example.com", "Link must not contain credentials"),
        ("http://localhost:8000", "Link must point to a public domain name"),
        ("http://127.0.0.1/admin", "Link must point to a public domain name"),
        ("http://[::1]/", "Link must point to a public domain name"),
    ],
)
def test_validate_link_rejects(link: str, message: str) -> None:
    with pytest.raises(ValueError, match=f"^{message}$"):
        validate_link(link)


@pytest.mark.parametrize(
    ("message", "link", "expected"),
    [
        (
            SAMPLE,
            "https://example.com",
            "Check out our latest business platform and grow your online",
        ),
        (
            "Big launch today! More at https://example.com",
            "https://example.com",
            "Big launch today",
        ),
        ("https://example.com", "https://example.com", "example.com"),
        (
            "New pricing page: https://example.com/pricing",
            "https://example.com/pricing",
            "New pricing page",
        ),
        ("a" * 70 + " https://example.com", "https://example.com", "a" * 60),
    ],
)
def test_derive_title(message: str, link: str, expected: str) -> None:
    assert derive_title(message, link) == expected
