"""Private anonymous Playwright transport for the pfbid tracer bullet.

This module deliberately keeps rendered content in memory only.  It exports no
public interface: ``collector.collect_posts`` owns retries, events and files.
"""

from datetime import datetime, timezone
from html.parser import HTMLParser
import re
import time
from urllib.parse import urljoin

from facebook_collector.model import capture_status, empty_outcome
from facebook_collector.url_validation import (
    UrlRejected,
    validate_public_url,
    validate_redirect_url,
)


COUNTERS = ("reaction", "comment", "share")
_COUNT = re.compile(r"(?<![0-9])([0-9][0-9,]*(?:\.[0-9]+)?)([KM])?", re.I)
_MAX_REDIRECT_HOPS = 10


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def parse_identity(url: str) -> dict | None:
    """Return an admitted live-extraction identity, otherwise no identity proof."""
    try:
        admitted = validate_public_url(url)
    except UrlRejected:
        return None
    return admitted["identity"] if admitted["family"] in {"pfbid", "photo", "group"} else None


class _ArticleParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url, self.depth, self.articles, self.current = base_url, 0, [], None
        self._stack: list[tuple[bool, str | None, bool]] = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        hidden = bool(attrs.get("hidden")) or attrs.get("aria-hidden") == "true" or "display:none" in attrs.get("style", "").replace(" ", "").lower()
        starts_article = tag == "article" and attrs.get("role") == "article"
        if starts_article and self.current is None:
            self.current = {"hrefs": [], "message": [], "counter": {name: [] for name in COUNTERS}}
        counter = attrs.get("data-counter") if self.current is not None else None
        if self.current is not None and attrs.get("data-ad-rendering-role") == "story_message":
            counter = "__message__"
        self._stack.append((starts_article, counter if counter in COUNTERS or counter == "__message__" else None, hidden))
        self.depth += 1
        if tag == "a" and self.current is not None and not hidden and attrs.get("href"):
            self.current["hrefs"].append(urljoin(self.base_url, attrs["href"]))

    def handle_endtag(self, tag):
        if not self._stack:
            return
        starts_article, _, _ = self._stack.pop()
        self.depth -= 1
        if starts_article and self.current is not None:
            self.articles.append(self.current)
            self.current = None

    def handle_data(self, data):
        if self.current is None or not data.strip() or any(hidden for _, _, hidden in self._stack):
            return
        roles = [counter for _, counter, _ in self._stack if counter in COUNTERS]
        if roles:
            self.current["counter"][roles[-1]].append(data)
        # Only a declared story-message element is text evidence.
        if any(counter == "__message__" for _, counter, _ in self._stack):
            self.current["message"].append(data)


def _metric(raw: str | None) -> dict:
    if not raw:
        return {"value": None, "raw": None, "quality": "missing", "source": None}
    match = _COUNT.search(raw)
    if match is None:
        return {"value": None, "raw": None, "quality": "unverified", "source": None}
    number = float(match.group(1).replace(",", ""))
    suffix = (match.group(2) or "").upper()
    multiplier = {"": 1, "K": 1_000, "M": 1_000_000}[suffix]
    value = int(number * multiplier)
    return {
        "value": value,
        "raw": match.group(0),
        "quality": "approximate" if suffix or "." in match.group(1) else "exact",
        "source": "target_engagement_row",
    }


def extract_pfbid_capture(input_url: str, resolved_url: str, html: str) -> dict | None:
    """Extract one uniquely scoped pfbid or photo target article.

    A matching route alone is not enough: exactly one rendered article must
    declare the same route.  Text and counters are read only from that article.
    """
    try:
        requested = validate_public_url(input_url)
    except UrlRejected:
        return None
    final = parse_identity(resolved_url)
    if final is None or not isinstance(html, str):
        return None
    if requested["family"] != "share" and requested["identity"] != final:
        return None
    parser = _ArticleParser(resolved_url)
    parser.feed(html)
    target = []
    for article in parser.articles:
        identities = [parse_identity(href) for href in article["hrefs"]]
        if any(identity == final for identity in identities):
            if any(identity is not None and identity != final for identity in identities):
                return None
            target.append(article)
    if len(target) != 1:
        return None
    article = target[0]
    messages = " ".join(article["message"]).strip()
    if not messages:
        text = {"value": None, "status": "missing", "source": None}
    else:
        text = {"value": messages, "status": "candidate_text_unverified", "source": "rendered_dom_story_message"}
    counters = {name: _metric(" ".join(article["counter"][name]).strip() or None) for name in COUNTERS}
    return {"post_identity": final, "text": text, "counters": counters}


def _failure(input_url: str, status: str, reason: str, *, http_status: int | None = None) -> dict:
    outcome = empty_outcome(input_url, 0, status, reason)
    outcome["attempted_at"] = _utc_now()
    if http_status is not None:
        outcome["_event_http_status"] = http_status
    return outcome


def _http_failure(input_url: str, status: int) -> dict | None:
    if status == 200:
        return None
    if status in {401, 403, 429}:
        return _failure(input_url, "blocked", "blocked", http_status=status)
    if status in {408, 504}:
        result = _failure(input_url, "timeout", "transport_timeout", http_status=status)
        result["_retryable"] = True
        return result
    if status in {404, 410}:
        return _failure(input_url, "error", "post_unavailable", http_status=status)
    if 500 <= status <= 503 or status >= 505:
        return _failure(input_url, "error", "facebook_server_error", http_status=status)
    return _failure(input_url, "error", "http_error", http_status=status)


def _looks_blocked(html: str) -> bool:
    """Recognize login/challenge chrome, never user-authored page text alone."""
    text = html.lower()
    has_form = "<form" in text
    login_action = re.search(r'<form[^>]+action=["\'][^"\']*/(?:login|checkpoint)', text)
    login_controls = "name=\"email\"" in text and (
        "name=\"pass\"" in text or 'type="password"' in text
    )
    challenge_surface = re.search(r'(?:id|class)=["\'][^"\']*(?:checkpoint|challenge)', text)
    captcha_control = re.search(r'name=["\'][^"\']*captcha|g-recaptcha|h-captcha', text)
    return bool((has_form and login_action and login_controls) or (has_form and challenge_surface and captcha_control))


def _location(response) -> str | None:
    """Return a redirect Location without accepting malformed response data."""
    headers = getattr(response, "headers", None)
    if not isinstance(headers, dict):
        return None
    for name, value in headers.items():
        if isinstance(name, str) and name.lower() == "location" and isinstance(value, str):
            return value
    return None


def _is_main_navigation(request) -> bool:
    checker = getattr(request, "is_navigation_request", None)
    return bool(checker()) if callable(checker) else False


def _navigate_with_validated_redirects(page, input_url: str, timeout: int):
    """Fetch each main-document hop without auto-following an unchecked Location."""
    state = {"next_url": None, "unsafe": False}
    deadline = time.monotonic() + timeout / 1000

    def route_handler(route, request):
        if not _is_main_navigation(request):
            route.continue_()
            return
        response = route.fetch(max_redirects=0)
        status = getattr(response, "status", 0)
        if status in {301, 302, 303, 307, 308}:
            location = _location(response)
            target = urljoin(request.url, location) if location else None
            try:
                if target is None:
                    raise UrlRejected("unsafe_redirect")
                validate_redirect_url(target)
            except UrlRejected:
                state["unsafe"] = True
            else:
                state["next_url"] = target
            route.abort()
            return
        route.fulfill(response=response)

    page.route("**/*", route_handler)
    current_url = input_url
    hops = 0
    try:
        while True:
            if hops >= _MAX_REDIRECT_HOPS:
                raise TimeoutError("redirect hop limit exhausted")
            remaining = int((deadline - time.monotonic()) * 1000)
            if remaining <= 0:
                raise TimeoutError("redirect deadline exhausted")
            state["next_url"] = None
            try:
                response = page.goto(current_url, timeout=remaining, wait_until="domcontentloaded")
            except Exception:
                if state["unsafe"]:
                    raise UrlRejected("unsafe_redirect")
                if state["next_url"] is None:
                    raise
            if state["unsafe"]:
                raise UrlRejected("unsafe_redirect")
            if state["next_url"] is None:
                return response
            hops += 1
            current_url = state["next_url"]
    finally:
        page.unroute("**/*", route_handler)


def collect_live_one(input_url: str, *, attempt_timeout_seconds: int, browser) -> dict:
    """Perform one anonymous non-persistent context attempt using an injected browser."""
    context = browser.new_context()
    try:
        page = context.new_page()
        try:
            validate_public_url(input_url)
            response = _navigate_with_validated_redirects(
                page, input_url, attempt_timeout_seconds * 1000
            )
        except Exception as error:
            if isinstance(error, UrlRejected):
                return _failure(input_url, "invalid_input", "unsafe_redirect")
            if error.__class__.__name__ == "TimeoutError":
                outcome = _failure(input_url, "timeout", "transport_timeout")
                outcome["_retryable"] = True
                return outcome
            raise
        status = response.status if response is not None else 0
        failed = _http_failure(input_url, status)
        if failed is not None:
            return failed
        try:
            final = validate_redirect_url(page.url)
        except UrlRejected:
            return _failure(input_url, "invalid_input", "unsafe_redirect", http_status=status)
        if final["family"] == "share" or final["identity"] is None:
            return _failure(input_url, "error", "identity_unverified", http_status=status)
        html = page.content()
        if _looks_blocked(html):
            return _failure(input_url, "blocked", "blocked", http_status=status)
        capture = extract_pfbid_capture(input_url, page.url, html)
        if capture is None:
            return _failure(input_url, "error", "identity_unverified", http_status=status)
        outcome = {
            "input_index": 0,
            "duplicate_of": None,
            "input_url": input_url,
            "resolved_url": page.url,
            "post_identity": capture["post_identity"],
            "attempted_at": _utc_now(),
            "collected_at": _utc_now(),
            "text": capture["text"],
            "counters": capture["counters"],
            "latest_updated": False,
        }
        outcome["status"] = capture_status(outcome["text"], outcome["counters"])
        outcome["reason"] = None
        outcome["_event_http_status"] = status
        return outcome
    finally:
        context.close()
