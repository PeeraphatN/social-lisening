"""Synthetic rendered pages; every request is fulfilled locally or aborted."""

import io
import json
import os
import runpy
import shutil
import tempfile
import unittest
from contextlib import nullcontext, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

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
            status=200, content_type="text/html; charset=utf-8", body=content)
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

    def test_unrelated_story_toolbar_cannot_override_target_article(self):
        label = "See who reacted to this story"
        row = (f'<div><span role="toolbar" aria-label="{label}"></span>'
               '<div><span>All reactions</span><span>999</span></div>'
               '<div role="button">888</div><div role="button">777</div></div>')
        target = article(counters="")
        unrelated = article(URL.replace("123", "987"), counters="", extra=row)
        result = self.inspect(target + unrelated)
        for metric in ("reaction", "comment", "share"):
            self.assertIsNone(result[f"{metric}_count"])

    def test_matching_story_toolbar_with_duplicate_messages_is_ambiguous(self):
        label = "See who reacted to this story"
        row = (f'<div><span role="toolbar" aria-label="{label}"></span>'
               '<div><span>All reactions</span><span>999</span></div></div>')
        content = article(counters="", extra=row).replace(
            '<div data-ad-rendering-role="story_message">Synthetic post</div>',
            '<div data-ad-rendering-role="story_message">Synthetic post</div>'
            '<div data-ad-rendering-role="story_message">Duplicate message</div>',
        )
        result = self.inspect(content)
        self.assertIsNone(result["reaction_count"])
        self.assertEqual(result["reaction_scope_status"], "ambiguous")

    def test_detached_story_toolbar_cannot_override_target_article(self):
        label = "See who reacted to this story"
        row = (f'<div><span role="toolbar" aria-label="{label}"></span>'
               '<div><span>All reactions</span><span>999</span></div>'
               '<div role="button">888</div><div role="button">777</div></div>')
        result = self.inspect(article(counters="") + row)
        for metric in ("reaction", "comment", "share"):
            self.assertIsNone(result[f"{metric}_count"])

    def test_standalone_story_row_still_requires_unique_row_and_page_identity(self):
        row = ('<div><span aria-label="See who reacted to this story"></span>'
               '<div>All reactions</div><div>395</div>'
               '<button>77</button><button>79</button></div>')
        for content, requested in ((row + row, URL), (row, URL.replace('123', '987'))):
            with self.subTest(content=content, requested=requested):
                result = self.inspect(content, requested_url=requested)
                for metric in ("reaction", "comment", "share"):
                    self.assertIsNone(result[f"{metric}_count"])

    def test_multiple_story_toolbars_in_one_article_are_ambiguous(self):
        row = ('<div><span aria-label="See who reacted to this story"></span>'
               '<div>All reactions</div><div>395</div>'
               '<button>77</button><button>79</button></div>')
        result = self.inspect(article(counters="", extra=row + row))
        for metric in ("reaction", "comment", "share"):
            self.assertIsNone(result[f"{metric}_count"])
            self.assertEqual(result[f"{metric}_scope_status"], "ambiguous")

    def test_story_toolbar_in_comment_menu_or_message_is_not_post_evidence(self):
        row = ('<div><span aria-label="See who reacted to this story"></span>'
               '<div>All reactions</div><div>999</div>'
               '<button>888</button><button>777</button></div>')
        for wrapper in ('role="comment"', 'role="menu"', 'data-ad-rendering-role="story_message"'):
            with self.subTest(wrapper=wrapper):
                result = self.inspect(article(counters="", extra=f'<div {wrapper}>{row}</div>'))
                for metric in ("reaction", "comment", "share"):
                    self.assertIsNone(result[f"{metric}_count"])

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

    def test_alias_header_and_unique_engagement_row_are_enough(self):
        content = article().replace(f'href="{URL}"', 'href="https://www.facebook.com/alias?rdid=abc"')
        content = content.replace('24 reactions|1 comment|2 shares',
                                  '24 reactions|1 comment|2 shares|Share|ถูกใจ')
        result = self.inspect(content)
        self.assertEqual(result["reaction_count"], 24)
        self.assertEqual(result["comment_count"], 1)
        self.assertEqual(result["share_count"], 2)
        self.assertEqual(result["reaction_scope_status"], "target_scoped")

    def test_p02_unique_story_row_does_not_require_article_or_message(self):
        label = 'ดูว่าใครบ้างที่ได้แสดงความรู้สึกต่อเรื่องราวนี้'
        row = (f'<div><span role="toolbar" aria-label="{label}"></span>'
               '<div><span>ความรู้สึกทั้งหมด</span><span>1.1 พัน</span></div>'
               '<div role="button">374</div><div role="button">353</div>'
               '<button>Like</button><button>Share</button></div>')
        # P02's photo layout has no story_message and its comment articles do
        # not own the engagement row. Keep this shape independent of article().
        comments = '<div role="article"><div role="comment">Reply</div></div>'
        for content in (row, f'<div role="complementary">{comments}{row}</div>', article(PHOTO_URL, counters="", extra=row)):
            with self.subTest(content=content):
                result = self.inspect(content, url=PHOTO_URL)
                self.assertEqual([result[f"{m}_count"] for m in ("reaction", "comment", "share")],
                                 [1100, 374, 353])
                self.assertIn("1.1 พัน", result["reaction_text_raw"])
                self.assertEqual(result["reaction_verification_status"], "approximate")

    def test_post_dialog_keeps_unique_story_row(self):
        row = ('<div><span aria-label="See who reacted to this story"></span>'
               '<div>All reactions</div><div>24</div>'
               '<div>4 comments</div><div>2 shares</div></div>')
        result = self.inspect(f'<div role="dialog">{article(counters="", extra=row)}</div>')
        self.assertEqual([result[f"{m}_count"] for m in ("reaction", "comment", "share")], [24, 4, 2])

    def test_story_toolbar_uses_total_not_reaction_type_breakdown(self):
        label = 'ดูว่าใครบ้างที่ได้แสดงความรู้สึกต่อเรื่องราวนี้'
        row = (f'<div><span role="toolbar" aria-label="{label}"></span>'
               '<div>ความรู้สึกทั้งหมด</div><div>395</div>'
               '<div role="button" aria-label="ถูกใจ: 342 คน">342</div>'
               '<div role="button" aria-label="รักเลย: 44 คน">44</div>'
               '<div role="button">77</div><div role="button">79</div></div>')
        result = self.inspect(article(counters="", extra=row))
        self.assertEqual([result[f"{m}_count"] for m in ("reaction", "comment", "share")], [395, 77, 79])

    def test_story_toolbar_p05_and_explicit_labels(self):
        label = 'See who reacted to this story'
        row = (f'<div><span role="toolbar" aria-label="{label}"></span>'
               '<div><span>All reactions</span><span>395</span></div>'
               '<div role="button" aria-label="77 comments">77</div>'
               '<div role="button" aria-label="79 shares">79</div></div>')
        for content in (row, article(GROUP_URL, counters="", extra=row)):
            with self.subTest(content=content):
                result = self.inspect(content, url=GROUP_URL)
                self.assertEqual([result[f"{m}_count"] for m in ("reaction", "comment", "share")], [395, 77, 79])
        text = 'Synthetic full post beyond the preview'
        content = ('<meta property="og:description" content="Synthetic preview...">'
                   f'<div data-ad-rendering-role="story_message">{text}</div>{row}')
        result = self.inspect(content, url=GROUP_URL)
        post = probe_post.extract_post(content, rendered_messages=[text],
                                       body_scope_status=result['body_scope_status'])
        self.assertEqual(post['status'], 'candidate_text_unverified')
        self.assertEqual(post['text_source'], 'rendered_dom_story_message')
        self.assertEqual(post['text'], text)

    def test_story_row_allows_links_inside_post_message(self):
        row = ('<div><span aria-label="See who reacted to this story"></span>'
               '<div>All reactions</div><div>61</div>'
               '<button>3</button><button>102</button></div>')
        content = article(counters="", extra=row).replace(
            'Synthetic post', '<a href="/story.php?story_fbid=987">Linked post</a>')
        content = content.replace(f'<a href="{URL}">Timestamp</a>', '')
        result = self.inspect(content)
        self.assertEqual([result[f"{m}_count"] for m in ("reaction", "comment", "share")], [61, 3, 102])

    def test_group_story_row_accepts_same_post_with_header_alias(self):
        row = ('<div><span aria-label="See who reacted to this story"></span>'
               '<div>All reactions</div><div>395</div>'
               '<button>77</button><button>79</button></div>')
        numeric = 'https://www.facebook.com/groups/456/posts/123/'
        alias = 'https://www.facebook.com/groups/groupname/posts/123/'
        for resolved, headers in ((numeric, (numeric, alias)), (alias, (numeric,))):
            content = article(headers[0], counters="", extra=row)
            content = content.replace('Timestamp</a>', 'Timestamp</a>' + ''.join(
                f'<a href="{url}">Alias</a>' for url in headers[1:]))
            with self.subTest(resolved=resolved):
                result = self.inspect(content, url=resolved)
                self.assertEqual([result[f"{m}_count"] for m in ("reaction", "comment", "share")], [395, 77, 79])
                # A different post or two conflicting numeric group IDs cannot
                # use the DOM alias exception; URL identity remains strict too.
                for wrong in (alias.replace('/123/', '/987/'), numeric.replace('/456/', '/789/')):
                    rejected = self.inspect(article(wrong, counters="", extra=row), url=numeric)
                    self.assertIsNone(rejected['reaction_count'])
                rejected = self.inspect(content, url=resolved, requested_url=alias if resolved == numeric else numeric)
                self.assertIsNone(rejected['reaction_count'])

    def test_story_summary_does_not_mistake_reactions_for_comment_count(self):
        label = 'ดูว่าใครบ้างที่ได้แสดงความรู้สึกต่อเรื่องราวนี้'
        row = (f'<div><span role="toolbar" aria-label="{label}"></span>'
               '<div>ความรู้สึกทั้งหมด</div><div>275</div>'
               '<div>ความคิดเห็น 1 รายการ</div><div>แชร์ 414 ครั้ง</div></div>')
        result = self.inspect(article(counters="", extra=row))
        self.assertEqual([result[f"{m}_count"] for m in ("reaction", "comment", "share")], [275, 1, 414])

    def test_explicit_share_label_and_same_control_are_one_counter(self):
        label = 'ดูว่าใครบ้างที่ได้แสดงความรู้สึกต่อเรื่องราวนี้'
        row = (f'<div><span role="toolbar" aria-label="{label}"></span>'
               '<div>ความรู้สึกทั้งหมด</div><div>7</div><div>แชร์ 6 ครั้ง</div>'
               '<button aria-label="6 shares">6</button></div>')
        result = self.inspect(article(counters="", extra=row))
        self.assertEqual(result["share_count"], 6)
        self.assertEqual(result["share_scope_status"], "target_scoped")

    def test_conflicting_share_summary_and_control_are_not_silently_deduped(self):
        label = 'ดูว่าใครบ้างที่ได้แสดงความรู้สึกต่อเรื่องราวนี้'
        row = (f'<div><span role="toolbar" aria-label="{label}"></span>'
               '<div>ความรู้สึกทั้งหมด</div><div>7</div><div>แชร์ 6 ครั้ง</div>'
               '<button aria-label="7 shares">7</button></div>')
        result = self.inspect(article(counters="", extra=row))
        self.assertIsNone(result["share_count"])
        self.assertEqual(result["share_scope_status"], "ambiguous")

    def test_story_row_requires_consistent_page_identity_and_unique_toolbar(self):
        label = 'See who reacted to this story'
        row = f'<div><span aria-label="{label}">x</span><button aria-label="Like: 395">395</button><button>77</button><button>79</button></div>'
        content = article(counters="", extra=row)
        self.assertIsNone(self.inspect(content, requested_url=URL.replace('123', '987'))['reaction_count'])
        result = self.inspect(content + content)
        self.assertIsNone(result['reaction_count'])
        self.assertEqual(result['reaction_scope_status'], 'ambiguous')

    def test_story_toolbar_row_explicit_labels_and_like_action(self):
        row = ('<div><span role="toolbar" aria-label="ดูว่าใครบ้างที่ได้แสดงความรู้สึกต่อเรื่องราวนี้"></span>'
               '<div>ความรู้สึกทั้งหมด</div><div>24</div>'
               '<button aria-label="1 comment">1</button><button aria-label="2 shares">2</button>'
               '<button>Like</button><button>Share</button></div>')
        result = self.inspect(article(counters="", extra=row))
        self.assertEqual([result[f"{m}_count"] for m in ("reaction", "comment", "share")], [24, 1, 2])

    def test_story_toolbar_replies_are_excluded_and_duplicate_rows_deduped(self):
        label = 'ดูว่าใครบ้างที่ได้แสดงความรู้สึกต่อเรื่องราวนี้'
        row = (f'<div><span role="toolbar" aria-label="{label}"></span><div>All reactions</div><div>395</div>'
               '<button>77</button><button>79</button>'
               '<div role="comment"><button aria-label="1 reaction on comment">1</button>'
               '<button>Reply</button></div></div>')
        content = article(counters="", extra=row)
        result = self.inspect(content)
        self.assertEqual([result[f"{m}_count"] for m in ("reaction", "comment", "share")], [395, 77, 79])
        duplicate = self.inspect(content + content)
        self.assertIsNone(duplicate["reaction_count"])
        self.assertEqual(duplicate["reaction_scope_status"], "ambiguous")

    def test_story_summary_cannot_read_comment_reply_menu_or_neighbor_text(self):
        noise = '<div>999 comments</div><div>888 shares</div>'
        for wrapper in ('role="comment"', 'role="menu"',
                        'data-ad-rendering-role="story_attachments"', 'role="article"'):
            row = ('<div><span aria-label="See who reacted to this story"></span>'
                   '<div>All reactions</div><div>24</div>'
                   f'<div {wrapper}>{noise}</div>'
                   '<button aria-label="1 comment">1</button>'
                   '<button aria-label="2 shares">2</button></div>')
            for content in (row, article(counters="", extra=row)):
                with self.subTest(wrapper=wrapper, content=content):
                    result = self.inspect(content)
                    self.assertEqual([result[f"{m}_count"] for m in ("reaction", "comment", "share")],
                                     [24, 1, 2])

    def test_story_toolbar_cannot_borrow_summary_from_neighboring_article(self):
        toolbar = '<div><span aria-label="See who reacted to this story"></span></div>'
        neighbor = article(URL.replace('123', '987'), counters="", extra=(
            '<div>All reactions</div><div>999</div>'
            '<div>888 comments</div><div>777 shares</div>'))
        for content in (article(counters="", extra=toolbar) + neighbor,
                        neighbor + article(counters="", extra=toolbar)):
            with self.subTest(content=content):
                result = self.inspect(content)
                for metric in ("reaction", "comment", "share"):
                    self.assertIsNone(result[f"{metric}_count"])

    def test_story_controls_containing_comment_or_nested_post_are_ineligible(self):
        for wrapper in ('role="comment"', 'role="article"', 'role="menu"'):
            row = ('<div><span aria-label="See who reacted to this story"></span>'
                   '<div>All reactions</div><div>24</div>'
                   f'<button><div {wrapper}>999 comments</div></button>'
                   '<button aria-label="1 comment">1</button>'
                   '<button aria-label="2 shares">2</button></div>')
            with self.subTest(wrapper=wrapper):
                result = self.inspect(row)
                self.assertEqual([result[f"{m}_count"] for m in ("reaction", "comment", "share")],
                                 [24, 1, 2])

    def test_conflicting_story_toolbar_rows_fail_closed(self):
        label = 'ดูว่าใครบ้างที่ได้แสดงความรู้สึกต่อเรื่องราวนี้'
        row = lambda n: f'<div><button aria-label="{label}">{n}</button><button>77</button><button>79</button></div>'
        result = self.inspect(article(counters="", extra=row(395)) +
                              article(counters="", extra=row(396)))
        self.assertIsNone(result["reaction_count"])

    def test_link_inside_message_cannot_prove_target(self):
        content = article().replace(f'<a href="{URL}">Timestamp</a>', '').replace(
            'Synthetic post', f'<a href="{URL}">Quoted target</a>')
        self.assertIsNone(self.inspect(content)["reaction_count"])

    def test_comment_and_reply_controls_without_nested_articles_are_not_post_counters(self):
        noise = ('<div role="comment"><div role="button">999 reactions</div>'
                 '<button>888 comments</button><div role="comment">'
                 '<div role="button">777 shares</div></div></div>')
        for counters, expected in (("", [None, None, None]),
                                   ("24 reactions|1 comment|2 shares", [24, 1, 2])):
            with self.subTest(counters=counters):
                result = self.inspect(article(counters=counters, extra=noise))
                for metric, count in zip(("reaction", "comment", "share"), expected):
                    self.assertEqual(result[f"{metric}_count"], count)
                    if count is None:
                        self.assertIsNone(result[f"{metric}_body_evidence"])
                        self.assertIsNone(result[f"{metric}_count_source"])
                        self.assertEqual(result[f"{metric}_scope_status"], "missing")
                    else:
                        self.assertEqual(result[f"{metric}_scope_status"], "target_scoped")

    def test_comment_aggregate_and_controls_containing_comments_are_ineligible(self):
        for noise in ('<div role="comment"><div><div>All reactions</div><span>999</span></div></div>',
                      '<div role="button"><div role="comment">999 reactions</div></div>',
                      '<div><div>All reactions</div><div role="comment">999</div></div>'):
            with self.subTest(noise=noise):
                result = self.inspect(article(counters="", extra=noise))
                self.assertIsNone(result["reaction_count"])
                self.assertIsNone(result["reaction_body_evidence"])

    def test_inspection_persists_metrics_and_evidence_from_one_snapshot(self):
        page = self.browser.new_page()
        content = '<title>Before mutation</title>' + article()
        page.route("**/*", lambda route: route.fulfill(
            status=200, content_type="text/html; charset=utf-8", body=content)
            if route.request.is_navigation_request() else route.abort())

        class MutatingPage:
            def __getattr__(self, name):
                return getattr(page, name)

            def goto(self, *args, **kwargs):
                response = page.goto(*args, **kwargs)
                page.evaluate("""() => {
                    window.observationTime = '2026-10-19T00:00:00.000Z';
                    const NativeDate = Date;
                    window.Date = class extends NativeDate {
                        constructor(...args) { super(...(args.length ? args : [window.observationTime])); }
                    };
                }""")
                return response

            def mutate(self):
                page.evaluate("""() => {
                    document.title = 'After mutation';
                    document.querySelector('[data-ad-rendering-role="story_message"]').innerText = 'Changed post';
                    document.querySelector('[role="button"]').innerText = '999 reactions';
                    window.observationTime = '2026-10-19T01:00:00.000Z';
                }""")

            def content(self):
                captured = page.content()
                self.mutate()
                return captured

            def evaluate(self, *args, **kwargs):
                captured = page.evaluate(*args, **kwargs)
                self.mutate()
                return captured

        browser = SimpleNamespace(new_page=lambda **kwargs: MutatingPage(), close=lambda: None)
        playwright = SimpleNamespace(chromium=SimpleNamespace(launch=lambda **kwargs: browser))
        try:
            with tempfile.TemporaryDirectory() as directory:
                script = Path(directory) / "inspect_browser.py"
                shutil.copyfile(Path(__file__).with_name("inspect_browser.py"), script)
                with patch("playwright.sync_api.sync_playwright", return_value=nullcontext(playwright)), \
                        patch("sys.argv", [str(script), URL, "--run-id", "atomic"]), \
                        patch.dict(os.environ), redirect_stdout(io.StringIO()):
                    runpy.run_path(str(script), run_name="__main__")
                output = Path(directory) / "runs"
                result = json.loads((output / "atomic-inspection.json").read_text(encoding="utf-8"))
                saved_html = (output / "atomic-page.html").read_text(encoding="utf-8")
                saved_body = (output / "atomic-body.txt").read_text(encoding="utf-8")
                self.assertEqual(result["reaction_count"], 24)
                self.assertIn("24 reactions", saved_html)
                self.assertIn("24 reactions", saved_body)
                self.assertNotIn("999 reactions", saved_html + saved_body)
                self.assertEqual(result["page_title"], "Before mutation")
                self.assertEqual(result["dom_messages"], ["Synthetic post"])
                self.assertEqual(result["body_preview"], saved_body[:1800])
                self.assertEqual(result["collected_at"], "2026-10-19T00:00:00.000Z")
                self.assertEqual(page.title(), "After mutation")
                self.assertIn("999 reactions", page.locator("body").inner_text())
        finally:
            page.close()

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
