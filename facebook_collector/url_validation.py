"""Admission rules for the approved public Facebook URL forms."""

import re
from urllib.parse import parse_qsl, urlsplit


FACEBOOK_HOST = "www.facebook.com"


class UrlRejected(ValueError):
    """A URL failed the public admission contract."""

    def __init__(self, reason: str, detail_reason: str | None = None):
        super().__init__(reason)
        self.reason = reason
        self.detail_reason = detail_reason


def _reject(reason: str):
    raise UrlRejected(reason)


def _query_values(query: str, fragment: str) -> dict[str, list[str]]:
    if fragment:
        _reject("unsupported_query")
    try:
        pairs = parse_qsl(query, keep_blank_values=True, strict_parsing=True) if query else []
    except ValueError:
        _reject("unsupported_query")
    values: dict[str, list[str]] = {}
    for name, value in pairs:
        values.setdefault(name, []).append(value)
    return values


def _one_numeric(values: dict[str, list[str]], name: str) -> str | None:
    candidates = values.get(name, [])
    if len(candidates) == 1 and re.fullmatch(r"[0-9]+", candidates[0]):
        return candidates[0]
    return None


def validate_public_url(url: str) -> dict:
    """Return the URL family and route identity, or raise a fixed rejection reason."""
    if not isinstance(url, str) or not url or any(character.isspace() for character in url):
        _reject("malformed_url")
    try:
        parsed = urlsplit(url)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        _reject("malformed_url")

    if not parsed.scheme or not parsed.netloc or hostname is None:
        _reject("malformed_url")
    if parsed.scheme.lower() != "https":
        _reject("https_required")
    if parsed.username is not None or parsed.password is not None:
        _reject("credentials_forbidden")
    if port is not None:
        _reject("custom_port_forbidden")
    if hostname.lower() != FACEBOOK_HOST:
        _reject("unsupported_host")

    path = parsed.path
    values = _query_values(parsed.query, parsed.fragment)

    if re.fullmatch(r"/share/p/[A-Za-z0-9]+/", path):
        if values:
            _reject("unsupported_query")
        return {"family": "share", "identity": None}

    if path == "/photo/":
        photo_id = _one_numeric(values, "fbid")
        allowed = {"fbid", "set"}
        sets = values.get("set", [])
        valid_set = not sets or len(sets) == 1 and re.fullmatch(r"a\.[0-9]+", sets[0])
        if photo_id is None or not set(values).issubset(allowed) or not valid_set:
            _reject("unsupported_query")
        return {
            "family": "photo",
            "identity": {"kind": "photo", "photo_id": photo_id},
        }

    pfbid = re.fullmatch(r"/([A-Za-z0-9._-]+)/posts/(pfbid[A-Za-z0-9]+)", path)
    if pfbid:
        if values:
            _reject("unsupported_query")
        return {
            "family": "pfbid",
            "identity": {"kind": "pfbid", "route": path},
        }

    group_listing = re.fullmatch(r"/groups/([0-9]+)/", path)
    if group_listing:
        post_id = _one_numeric(values, "multi_permalinks")
        allowed = {"multi_permalinks", "hoisted_section_header_type"}
        hoisted = values.get("hoisted_section_header_type", [])
        valid_hoisted = not hoisted or hoisted == ["recently_seen"]
        if post_id is None or not set(values).issubset(allowed) or not valid_hoisted:
            _reject("unsupported_query")
        return {
            "family": "group",
            "identity": {
                "kind": "group",
                "group_id": group_listing.group(1),
                "post_id": post_id,
            },
        }

    group_post = re.fullmatch(r"/groups/([0-9]+)/posts/([0-9]+)/?", path)
    if group_post:
        if values:
            _reject("unsupported_query")
        return {
            "family": "group",
            "identity": {
                "kind": "group",
                "group_id": group_post.group(1),
                "post_id": group_post.group(2),
            },
        }

    _reject("unsupported_route")


def validate_redirect_url(url: str) -> dict:
    """Apply the public allowlist while exposing one redirect-safe reason."""
    try:
        return validate_public_url(url)
    except UrlRejected as error:
        raise UrlRejected("unsafe_redirect", detail_reason=error.reason) from error
