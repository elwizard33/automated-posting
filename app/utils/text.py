"""Link detection and title derivation for incoming messages."""

import ipaddress
import re
from urllib.parse import urlsplit

_LINK_RE = re.compile(r"(?<![\w@])(?:[a-z][a-z0-9+.-]*://|www\.)\S+", re.IGNORECASE)
_TRAILING_PUNCTUATION = ".,;:!?)]}'\""
_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
_TLD_RE = re.compile(r"^([a-z]{2,63}|xn--[a-z0-9-]{1,59})$")
_SENTENCE_END_RE = re.compile(r"[.!?](?:\s|$)")
_TITLE_EDGE_CHARS = " \t\n-:|,."
MAX_TITLE_LENGTH = 60


def find_links(text: str) -> list[str]:
    """Return every link-like token: anything with a scheme, or starting with www."""
    links = (_strip_trailing(match.group(0)) for match in _LINK_RE.finditer(text))
    return [link for link in links if link]


def _strip_trailing(link: str) -> str:
    """Drop sentence punctuation after a link, keeping a ')' that closes one in the link."""
    while link and link[-1] in _TRAILING_PUNCTUATION:
        if link[-1] == ")" and link.count("(") >= link.count(")"):
            break
        link = link[:-1]
    return link


def validate_link(link: str) -> None:
    """Raise ValueError with a client-safe message unless link is a public http(s) URL."""
    if not link.lower().startswith(("http://", "https://")):
        raise ValueError("Link must start with http:// or https://")
    try:
        parts = urlsplit(link)
        host = parts.hostname
        _ = parts.port  # reading it validates the port
    except ValueError:
        raise ValueError("Link is not a valid URL") from None
    if not host:
        raise ValueError("Link is not a valid URL")
    if parts.username is not None or parts.password is not None:
        raise ValueError("Link must not contain credentials")
    if _is_ip_address(host) or host == "localhost" or host.endswith(".localhost"):
        raise ValueError("Link must point to a public domain name")
    try:
        labels = host.encode("idna").decode("ascii").lower().split(".")
    except UnicodeError:
        raise ValueError("Link is not a valid URL") from None
    valid_labels = all(_LABEL_RE.match(label) for label in labels)
    if len(labels) < 2 or not valid_labels or not _TLD_RE.match(labels[-1]):
        raise ValueError("Link is not a valid URL")


def derive_title(message: str, link: str) -> str:
    """Build a short title for platforms that need one, from the text around the link."""
    text = " ".join(message.replace(link, " ").split()).strip(_TITLE_EDGE_CHARS)
    if not text:
        return urlsplit(link).hostname or link
    sentence_end = _SENTENCE_END_RE.search(text)
    if sentence_end:
        text = text[: sentence_end.start()]
    if len(text) > MAX_TITLE_LENGTH:
        head = text[: MAX_TITLE_LENGTH + 1]
        text = head[: head.rindex(" ")] if " " in head else text[:MAX_TITLE_LENGTH]
    return text.strip(_TITLE_EDGE_CHARS)


def _is_ip_address(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True
