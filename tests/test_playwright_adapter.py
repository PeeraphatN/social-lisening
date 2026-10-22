"""Offline contract tests for the private pfbid Playwright tracer bullet."""

import socket
import subprocess
import unittest
from unittest.mock import patch

from facebook_collector.playwright_adapter import (
    collect_live_one,
    extract_pfbid_capture,
    parse_identity,
)


URL = "https://www.facebook.com/acme/posts/pfbidABC123"
PHOTO_URL = "https://www.facebook.com/photo/?fbid=1649985453249994"
PHOTO_URL_WITH_SET = "https://www.facebook.com/photo/?fbid=1649985453249994&set=a.194492012132686"
OTHER_PHOTO_URL = "https://www.facebook.com/photo/?fbid=1649985453249995"
GROUP_LISTING_URL = "https://www.facebook.com/groups/100/?multi_permalinks=200&hoisted_section_header_type=recently_seen"
GROUP_LISTING_NO_HOIST_URL = "https://www.facebook.com/groups/100/?multi_permalinks=200"
GROUP_EXPLICIT_URL = "https://www.facebook.com/groups/100/posts/200/"
GROUP_EXPLICIT_NO_SLASH_URL = "https://www.facebook.com/groups/100/posts/200"
SHARE_URL = "https://www.facebook.com/share/p/19TTvcsmZ8/"


def story_html(*, href=URL, reaction="12", comment="3", share="0", text="Target text"):
    counters = "".join(
        markup for markup in (
            None if reaction is None else f'<div data-counter="reaction">All reactions {reaction}</div>',
            None if comment is None else f'<div data-counter="comment">{comment} comments</div>',
            None if share is None else f'<div data-counter="share">{share} shares</div>',
        ) if markup is not None
    )
    return f'''<article role="article"><a href="{href}">permalink</a>
    <div data-ad-rendering-role="story_message">{text}</div>
    {counters}</article>'''


def group_story_html(*, href=GROUP_EXPLICIT_URL, reaction="12", comment="3", share="0", text="Target text"):
    return story_html(href=href, reaction=reaction, comment=comment, share=share, text=text)


class FakeResponse:
    def __init__(self, status, headers=None):
        self.status, self.headers = status, headers or {}


class FakeRequest:
    def __init__(self, url, *, navigation=True):
        self.url, self._navigation = url, navigation
    def is_navigation_request(self): return self._navigation


class FakeRoute:
    def __init__(self, request, response, calls):
        self.request, self.response, self.calls = request, response, calls
    def fetch(self, *, max_redirects):
        self.calls.append(("fetch", self.request.url, max_redirects))
        return self.response
    def fulfill(self, *, response): self.calls.append(("fulfill", self.request.url, response.status))
    def abort(self): self.calls.append(("abort", self.request.url))
    def continue_(self): self.calls.append(("continue", self.request.url))


class FakePage:
    def __init__(self, html, final_url, response=200, error=None, hops=None):
        self.html, self.url, self.final_url, self.response, self.error = html, final_url, final_url, response, error
        self.hops, self.route_handler, self.calls = list(hops or []), None, []
    def route(self, pattern, handler): self.route_handler = handler
    def unroute(self, pattern, handler): self.route_handler = None
    def goto(self, url, *, timeout, wait_until):
        if self.error: raise self.error
        self.timeout, self.wait_until = timeout, wait_until
        if self.route_handler is None:
            return FakeResponse(self.response)
        response = self.hops.pop(0) if self.hops else FakeResponse(self.response)
        route = FakeRoute(FakeRequest(url), response, self.calls)
        self.route_handler(route, route.request)
        if response.status in {301, 302, 303, 307, 308}:
            raise RuntimeError("aborted redirect")
        self.url = self.final_url
        return response
    def content(self): return self.html


class FakeContext:
    def __init__(self, page, calls): self.page, self.calls = page, calls
    def new_page(self): self.calls.append("page"); return self.page
    def close(self): self.calls.append("context.close")


class FakeBrowser:
    def __init__(self, page, calls): self.page, self.calls = page, calls
    def new_context(self): self.calls.append("context"); return FakeContext(self.page, self.calls)


class IdentityAndExtractionTests(unittest.TestCase):
    def test_share_input_uses_safe_pfbid_destination_identity(self):
        result = extract_pfbid_capture(SHARE_URL, URL, story_html())
        self.assertEqual(result["post_identity"], {"kind": "pfbid", "route": "/acme/posts/pfbidABC123"})

    def test_pfbid_identity_requires_matching_final_route(self):
        self.assertEqual(parse_identity(URL), {"kind": "pfbid", "route": "/acme/posts/pfbidABC123"})
        result = extract_pfbid_capture(URL, "https://www.facebook.com/acme/posts/pfbidOTHER", story_html())
        self.assertIsNone(result)

    def test_unique_target_article_extracts_text_and_exact_zero(self):
        result = extract_pfbid_capture(URL, URL, story_html())
        self.assertEqual(result["text"], {"value": "Target text", "status": "candidate_text_unverified", "source": "rendered_dom_story_message"})
        self.assertEqual(result["counters"]["share"], {"value": 0, "raw": "0", "quality": "exact", "source": "target_engagement_row"})

    def test_neighbour_and_ambiguous_target_fail_closed(self):
        html = story_html() + story_html(href="https://www.facebook.com/other/posts/pfbidNOPE", reaction="999", text="Neighbour")
        self.assertEqual(extract_pfbid_capture(URL, URL, html)["counters"]["reaction"]["value"], 12)
        self.assertIsNone(extract_pfbid_capture(URL, URL, story_html() + story_html()))

    def test_photo_forms_require_a_matching_final_photo_identity(self):
        for input_url in (PHOTO_URL, PHOTO_URL_WITH_SET):
            with self.subTest(input_url=input_url):
                result = extract_pfbid_capture(input_url, PHOTO_URL, story_html(href=PHOTO_URL, share="0"))
                self.assertEqual(result["post_identity"], {"kind": "photo", "photo_id": "1649985453249994"})
                self.assertEqual(result["counters"]["share"], {"value": 0, "raw": "0", "quality": "exact", "source": "target_engagement_row"})
        self.assertIsNone(extract_pfbid_capture(PHOTO_URL, OTHER_PHOTO_URL, story_html(href=OTHER_PHOTO_URL)))

    def test_photo_scope_rejects_duplicate_target_and_ignores_neighbour(self):
        html = story_html(href=PHOTO_URL, reaction="12") + story_html(href=OTHER_PHOTO_URL, reaction="999", text="Neighbour")
        self.assertEqual(extract_pfbid_capture(PHOTO_URL, PHOTO_URL, html)["counters"]["reaction"]["value"], 12)
        self.assertIsNone(extract_pfbid_capture(PHOTO_URL, PHOTO_URL, story_html(href=PHOTO_URL) + story_html(href=PHOTO_URL)))

    def test_photo_missing_text_is_partial_and_keeps_missing_metrics(self):
        calls = []
        page = FakePage(story_html(href=PHOTO_URL, text="", comment=None), PHOTO_URL)
        with patch.object(socket, "create_connection", side_effect=AssertionError("socket")), patch.object(
            subprocess, "Popen", side_effect=AssertionError("process")
        ):
            result = collect_live_one(PHOTO_URL, attempt_timeout_seconds=30, browser=FakeBrowser(page, calls))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["text"], {"value": None, "status": "missing", "source": None})
        self.assertEqual(result["counters"]["comment"], {"value": None, "raw": None, "quality": "missing", "source": None})
        self.assertFalse(result["latest_updated"])

    def test_group_listing_and_explicit_routes_share_one_verified_identity(self):
        expected = {"kind": "group", "group_id": "100", "post_id": "200"}
        for requested, final in (
            (GROUP_LISTING_NO_HOIST_URL, GROUP_EXPLICIT_URL),
            (GROUP_LISTING_URL, GROUP_EXPLICIT_URL),
            (GROUP_EXPLICIT_URL, GROUP_LISTING_URL),
            (GROUP_EXPLICIT_NO_SLASH_URL, GROUP_EXPLICIT_URL),
        ):
            with self.subTest(requested=requested, final=final):
                self.assertEqual(parse_identity(requested), expected)
                result = extract_pfbid_capture(requested, final, group_story_html())
                self.assertEqual(result["post_identity"], expected)
                self.assertEqual(result["text"]["value"], "Target text")
                self.assertEqual(result["counters"]["share"]["value"], 0)

    def test_group_target_rejects_route_mismatch_and_ambiguous_articles(self):
        wrong_group = "https://www.facebook.com/groups/101/posts/200/"
        wrong_post = "https://www.facebook.com/groups/100/posts/201/"
        self.assertIsNone(extract_pfbid_capture(GROUP_LISTING_URL, wrong_group, group_story_html()))
        self.assertIsNone(extract_pfbid_capture(GROUP_LISTING_URL, wrong_post, group_story_html()))
        self.assertIsNone(
            extract_pfbid_capture(
                GROUP_LISTING_URL, GROUP_EXPLICIT_URL, group_story_html() + group_story_html()
            )
        )

    def test_group_target_ignores_neighbour_comment_and_menu_numbers(self):
        neighbour = group_story_html(
            href="https://www.facebook.com/groups/100/posts/201/",
            reaction="999",
            comment="888",
            share="777",
            text="Neighbour text",
        )
        menu_noise = "<div>555 comments</div><button>444 shares</button>"
        result = extract_pfbid_capture(
            GROUP_LISTING_URL,
            GROUP_EXPLICIT_URL,
            group_story_html(reaction="0", comment="0", share="0") + neighbour + menu_noise,
        )
        self.assertEqual(result["text"]["value"], "Target text")
        self.assertEqual(
            [result["counters"][name]["value"] for name in ("reaction", "comment", "share")],
            [0, 0, 0],
        )

    def test_group_target_preserves_null_metric_evidence(self):
        result = extract_pfbid_capture(
            GROUP_EXPLICIT_URL,
            GROUP_EXPLICIT_URL,
            group_story_html(reaction="", comment="", share=""),
        )
        self.assertEqual(
            [result["counters"][name]["value"] for name in ("reaction", "comment", "share")],
            [None, None, None],
        )


class AdapterTests(unittest.TestCase):
    def test_share_redirects_validate_each_hop_before_following(self):
        calls = []
        page = FakePage(
            story_html(),
            URL,
            hops=[
                FakeResponse(302, {"location": "/acme/posts/pfbidABC123"}),
                FakeResponse(200),
            ],
        )
        result = collect_live_one(SHARE_URL, attempt_timeout_seconds=30, browser=FakeBrowser(page, calls))
        self.assertEqual((result["input_url"], result["resolved_url"], result["status"]), (SHARE_URL, URL, "collected"))
        self.assertEqual(page.calls, [
            ("fetch", SHARE_URL, 0),
            ("abort", SHARE_URL),
            ("fetch", URL, 0),
            ("fulfill", URL, 200),
        ])

    def test_unsafe_redirect_is_aborted_before_following(self):
        unsafe_locations = (
            "https://evil.example/",
            "http://www.facebook.com/acme/posts/pfbidABC123",
            "https://user@www.facebook.com/acme/posts/pfbidABC123",
            "https://www.facebook.com:8443/acme/posts/pfbidABC123",
            "https://www.facebook.com/search/",
            "https://www.facebook.com/acme/posts/pfbidABC123?tracking=1",
        )
        for location in unsafe_locations:
            with self.subTest(location=location):
                calls = []
                page = FakePage("", URL, hops=[FakeResponse(302, {"location": location})])
                result = collect_live_one(SHARE_URL, attempt_timeout_seconds=30, browser=FakeBrowser(page, calls))
                self.assertEqual((result["status"], result["reason"], result["resolved_url"], result["_retryable"] if "_retryable" in result else False), ("invalid_input", "unsafe_redirect", None, False))
                self.assertEqual(page.calls, [("fetch", SHARE_URL, 0), ("abort", SHARE_URL)])

    def test_adapter_uses_nonpersistent_context_and_closes_it(self):
        calls = []
        page = FakePage(story_html(), URL)
        with patch.object(socket, "create_connection", side_effect=AssertionError("socket")), patch.object(
            subprocess, "Popen", side_effect=AssertionError("process")
        ):
            result = collect_live_one(URL, attempt_timeout_seconds=30, browser=FakeBrowser(page, calls))
        self.assertEqual(result["status"], "collected")
        self.assertEqual((page.timeout, page.wait_until), (30000, "domcontentloaded"))
        self.assertEqual(calls, ["context", "page", "context.close"])

    def test_redirect_http_and_timeout_are_fail_closed(self):
        calls = []
        redirect = collect_live_one(URL, attempt_timeout_seconds=30, browser=FakeBrowser(FakePage("", "https://evil.example/", 200), calls))
        self.assertEqual((redirect["status"], redirect["reason"]), ("invalid_input", "unsafe_redirect"))
        unavailable = collect_live_one(URL, attempt_timeout_seconds=30, browser=FakeBrowser(FakePage("", URL, 404), []))
        self.assertEqual((unavailable["status"], unavailable["reason"], unavailable["_event_http_status"]), ("error", "post_unavailable", 404))
        timeout = collect_live_one(URL, attempt_timeout_seconds=30, browser=FakeBrowser(FakePage("", URL, error=TimeoutError()), []))
        self.assertEqual((timeout["status"], timeout["_retryable"]), ("timeout", True))

    def test_group_listing_live_flow_uses_final_explicit_route_and_fake_browser_only(self):
        calls = []
        page = FakePage(group_story_html(), GROUP_EXPLICIT_URL)
        with patch.object(socket, "create_connection", side_effect=AssertionError("socket")), patch.object(
            socket.socket, "connect", side_effect=AssertionError("socket")
        ), patch.object(subprocess, "Popen", side_effect=AssertionError("process")):
            result = collect_live_one(
                GROUP_LISTING_URL,
                attempt_timeout_seconds=30,
                browser=FakeBrowser(page, calls),
            )
        self.assertEqual(result["status"], "collected")
        self.assertEqual(result["post_identity"], {"kind": "group", "group_id": "100", "post_id": "200"})
        self.assertEqual(calls, ["context", "page", "context.close"])
