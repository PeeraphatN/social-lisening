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


def story_html(*, href=URL, reaction="12", comment="3", share="0", text="Target text"):
    return f'''<article role="article"><a href="{href}">permalink</a>
    <div data-ad-rendering-role="story_message">{text}</div>
    <div data-counter="reaction">All reactions {reaction}</div>
    <div data-counter="comment">{comment} comments</div>
    <div data-counter="share">{share} shares</div></article>'''


class FakeResponse:
    def __init__(self, status): self.status = status


class FakePage:
    def __init__(self, html, final_url, response=200, error=None):
        self.html, self.url, self.response, self.error = html, final_url, response, error
    def goto(self, url, *, timeout, wait_until):
        if self.error: raise self.error
        self.timeout, self.wait_until = timeout, wait_until
        return FakeResponse(self.response)
    def content(self): return self.html


class FakeContext:
    def __init__(self, page, calls): self.page, self.calls = page, calls
    def new_page(self): self.calls.append("page"); return self.page
    def close(self): self.calls.append("context.close")


class FakeBrowser:
    def __init__(self, page, calls): self.page, self.calls = page, calls
    def new_context(self): self.calls.append("context"); return FakeContext(self.page, self.calls)


class IdentityAndExtractionTests(unittest.TestCase):
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


class AdapterTests(unittest.TestCase):
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

