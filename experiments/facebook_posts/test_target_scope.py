"""Synthetic rendered pages; every request is fulfilled locally or aborted."""

import os
import unittest
from pathlib import Path

browser_path = Path(__file__).resolve().parent / ".playwright"
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(browser_path))

from playwright.sync_api import sync_playwright

import probe_post
from test_icon_counters import GROUP_URL, PHOTO_URL, html, summary
from test_pfbid_share import URL as PFBID_URL, document


URL = "https://www.facebook.com/story.php?story_fbid=123&id=456"


def article(url=URL, counters="24 reactions|1 comment|2 shares", extra=""):
    controls = "".join(f'<div role="button">{text}</div>' for text in counters.split("|") if text)
    return (f'<div role="article"><a href="{url}">Timestamp</a>'
            '<div data-ad-rendering-role="story_message">Synthetic post</div>'
            f'{controls}{extra}</div>')


class TargetScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.playwright = sync_playwright().start()
        cls.browser = cls.playwright.chromium.launch(headless=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close()
        cls.playwright.stop()

    def inspect(self, content, url=URL, requested_url=None):
        page = self.browser.new_page()
        # No page script or external resource can contact Facebook during tests.
        page.route("**/*", lambda route: route.fulfill(
            status=200, content_type="text/html", body=content)
            if route.request.is_navigation_request() else route.abort())
        try:
            page.goto(url, wait_until="domcontentloaded")
            return probe_post.inspect_browser_metrics(page, requested_url or url)
        finally:
            page.close()

    def test_whole_page_body_is_never_target_evidence(self):
        result = probe_post.extract_browser_metrics("24 reactions\n1 comment\n2 shares", "", URL)
        for metric in ("reaction", "comment", "share"):
            self.assertIsNone(result[f"{metric}_count"])

    def test_unrelated_larger_counters_and_order_do_not_change_target(self):
        unrelated = article(URL.replace("123", "987"), "999 reactions|888 comments|777 shares")
        for content in (unrelated + article(), article() + unrelated):
            result = self.inspect(content)
            self.assertEqual([result[f"{m}_count"] for m in ("reaction", "comment", "share")], [24, 1, 2])
            self.assertEqual(result["reaction_scope_status"], "target_scoped")
            self.assertEqual(result["reaction_body_evidence"]["identity"]["post_id"], "123")

    def test_missing_duplicate_and_conflicting_containers_fail_closed(self):
        for content, status in ((article(URL.replace("123", "987")), "missing"),
                                (article() + article(), "ambiguous"),
                                (article() + article(counters="999 reactions"), "ambiguous"),
                                (article(extra='<a href="/story.php?story_fbid=987">Other</a>'), "target_scoped")):
            result = self.inspect(content)
            if status == "target_scoped":
                self.assertEqual(result["reaction_count"], 24)  # Links after the message are not headers.
            else:
                self.assertIsNone(result["reaction_count"])
                self.assertEqual(result["reaction_scope_status"], status)

    def test_conflicting_header_and_multiple_messages_are_rejected(self):
        for content in (article().replace('Timestamp</a>', 'Timestamp</a><a href="/story.php?story_fbid=987">Other</a>'),
                        article(extra='<div data-ad-rendering-role="story_message">Other post</div>')):
            result = self.inspect(content)
            self.assertIsNone(result["reaction_count"])

    def test_malformed_header_identity_cannot_be_ignored_beside_target(self):
        content = article().replace('Timestamp</a>', 'Timestamp</a><a href="/story.php?story_fbid=bad">Other</a>')
        result = self.inspect(content)
        self.assertIsNone(result["reaction_count"])
        self.assertEqual(result["reaction_scope_status"], "malformed")

    def test_comments_replies_menus_previews_and_post_text_are_not_counters(self):
        noise = ('<div role="article"><div role="button">999 comments</div></div>'
                 '<div role="menu"><div role="button">888 shares</div></div>'
                 '<aside><div role="button">777 reactions</div></aside>'
                 '<div data-ad-rendering-role="story_attachments"><div role="button">666 shares</div></div>')
        content = article(counters="", extra=noise).replace("Synthetic post", '<div role="button">555 reactions</div>')
        result = self.inspect(content)
        for metric in ("reaction", "comment", "share"):
            self.assertIsNone(result[f"{metric}_count"])

    def test_link_inside_message_cannot_prove_target(self):
        content = article().replace(f'<a href="{URL}">Timestamp</a>', '').replace(
            'Synthetic post', f'<a href="{URL}">Quoted target</a>')
        self.assertIsNone(self.inspect(content)["reaction_count"])

    def test_hidden_target_and_hidden_conflicting_counters_are_ignored(self):
        self.assertIsNone(self.inspect('<div hidden>' + article() + '</div>')["reaction_count"])
        result = self.inspect(article(extra='<div style="display:none"><div role="button">999 reactions</div></div>'))
        self.assertEqual(result["reaction_count"], 24)

    def test_svg_icons_do_not_break_rendered_snapshot(self):
        result = self.inspect(article(extra='<svg role="button"><path d="M0 0"/></svg>'))
        self.assertEqual(result["reaction_count"], 24)

    def test_explicit_zero_and_aggregate_reactions_are_supported(self):
        content = article(counters="0 comments|0 shares", extra='<div><div>All reactions</div><span>0</span></div>')
        result = self.inspect(content)
        self.assertEqual([result[f"{m}_count"] for m in ("reaction", "comment", "share")], [0, 0, 0])

    def test_labels_before_counts_keep_existing_body_semantics(self):
        result = self.inspect(article(counters="Reactions 24|Comments 1|Shares 2"))
        self.assertEqual([result[f"{m}_count"] for m in ("reaction", "comment", "share")], [24, 1, 2])

    def test_malformed_and_duplicate_counter_labels_are_rejected(self):
        for raw in ("-1 shares", "1.5 shares", "7,9 shares", "about 79 shares", "79 posts 100 shares", "79 shares|80 shares"):
            self.assertIsNone(self.inspect(article(counters=raw))["share_count"], raw)

    def test_invalid_and_ambiguous_numeric_identities_are_rejected(self):
        for url in (URL.replace("123", "bad"), URL + "&story_fbid=123", URL.replace("123", ""),
                    GROUP_URL.replace("123", "bad"), GROUP_URL + "&multi_permalinks=123"):
            self.assertIsNone(self.inspect(article(url), url)["reaction_count"])

    def test_requested_resolved_mismatch_rejects_all_evidence(self):
        result = self.inspect(article() + html(summary(comments=0)), requested_url=URL.replace("123", "987"))
        self.assertIsNone(result["reaction_count"])
        self.assertIsNone(result["comment_count"])
        self.assertEqual(result["comment_scope_status"], "conflicting")

    def test_share_redirect_can_use_proven_resolved_container(self):
        self.assertEqual(self.inspect(article(), requested_url="https://www.facebook.com/share/p/token/")["reaction_count"], 24)

    def test_body_precedence_preserves_structured_disagreement(self):
        result = self.inspect(article(GROUP_URL) + html(summary()), GROUP_URL)
        self.assertEqual((result["comment_count"], result["share_count"]), (1, 2))
        self.assertEqual(result["share_count_source"], "body_text")
        self.assertEqual(result["share_counter_evidence"]["count"], 79)
        self.assertEqual(result["share_body_evidence"]["count"], 2)
        self.assertEqual(result["share_scope_status"], "conflicting")
        self.assertEqual(result["share_verification_status"], "unverified")

    def test_identity_scoped_fallback_survives_missing_or_ambiguous_body(self):
        for content in ("", article(GROUP_URL) + article(GROUP_URL)):
            result = self.inspect(content + html(summary()), GROUP_URL)
            self.assertIsNone(result["reaction_count"])
            self.assertEqual((result["comment_count"], result["share_count"]), (77, 79))
            self.assertEqual(result["share_scope_status"], "identity_scoped_fallback")

    def test_photo_and_opaque_pfbid_fallbacks_remain_identity_scoped(self):
        media = {"currMedia": {"id": "456", "creation_story": {"post_id": "123"}}}
        photo = self.inspect(html(media, summary()), PHOTO_URL)
        opaque = self.inspect(document(), PFBID_URL)
        self.assertEqual(photo["share_count"], 79)
        self.assertEqual(opaque["share_count"], 0)
        self.assertIsNone(photo["reaction_count"])

    def test_opaque_fallback_requires_numeric_post_identity(self):
        for post_id in ("bad", "123_456", "", "\u0e51\u0e52\u0e53"):
            result = self.inspect(document(post_id=post_id), PFBID_URL)
            self.assertIsNone(result["comment_count"])
            self.assertIsNone(result["share_count"])

    def test_exact_raw_contradiction_and_compact_rounding_are_checked(self):
        for count, raw in ((80, "79"), (5000, "1.2K"), (1250, "1.2K")):
            self.assertIsNone(self.inspect(html(summary(shares=count, share_raw=raw)), GROUP_URL)["share_count"])
        result = self.inspect(article(GROUP_URL, "1.2K shares") + html(summary(shares=1234, share_raw="1.2K")), GROUP_URL)
        self.assertEqual(result["share_count"], 1200)
        self.assertEqual(result["share_verification_status"], "approximate")


if __name__ == "__main__":
    unittest.main()
