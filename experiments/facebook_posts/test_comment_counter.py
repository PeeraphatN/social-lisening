"""Minimal, synthetic copies of the saved engagement-summary structure."""

import base64
import json
import unittest

from probe_post import extract_comment_counter


URL = "https://www.facebook.com/story.php?story_fbid=123&id=456"


def summary(post_id="123", count=0):
    feedback_id = base64.b64encode(f"feedback:{post_id}".encode()).decode()
    return {"comet_ufi_summary_and_actions_renderer": {"feedback": {
        "id": feedback_id,
        "comments_count_summary_renderer": {"feedback": {
            "id": feedback_id,
            "comment_rendering_instance": {"comments": {"total_count": count}},
        }},
    }}}


def html(data):
    return '<script type="application/json">' + json.dumps(data) + '</script>'


class CommentCounterTests(unittest.TestCase):
    def test_target_zero_has_explicit_evidence(self):
        result = extract_comment_counter(html(summary()), URL)
        self.assertEqual(result["count"], 0)
        self.assertEqual(result["post_id"], "123")
        self.assertEqual(result["source"], "embedded_comment_summary")

    def test_positive_counter_uses_same_structure(self):
        self.assertEqual(extract_comment_counter(html(summary(count=3)), URL)["count"], 3)

    def test_other_post_and_reply_zero_are_not_target_zero(self):
        self.assertIsNone(extract_comment_counter(html(summary(post_id="999")), URL))
        self.assertIsNone(extract_comment_counter(html(summary(post_id="123_999")), URL))
        self.assertIsNone(extract_comment_counter(html({"feedback": {
            "comment_rendering_instance": {"comments": {"total_count": 0}}
        }}), URL))

    def test_absent_invalid_or_conflicting_counts_stay_missing(self):
        for data in ({}, summary(count=None), summary(count=False), summary(count=-1),
                     summary(count="0"), summary(count=0.5),
                     [summary(count=0), summary(count=1)]):
            with self.subTest(data=data):
                self.assertIsNone(extract_comment_counter(html(data), URL))
        self.assertIsNone(extract_comment_counter('<script type="application/json">bad</script>', URL))

    def test_inner_feedback_identity_must_match_too(self):
        data = summary()
        data["comet_ufi_summary_and_actions_renderer"]["feedback"]["comments_count_summary_renderer"]["feedback"]["id"] = "other"
        self.assertIsNone(extract_comment_counter(html(data), URL))

    def test_unresolved_or_ambiguous_target_stays_missing(self):
        for url in ("https://www.facebook.com/share/p/token/",
                    "https://www.facebook.com/story.php?story_fbid=123&story_fbid=999",
                    "https://www.facebook.com/story.php?story_fbid=bad"):
            with self.subTest(url=url):
                self.assertIsNone(extract_comment_counter(html(summary()), url))


if __name__ == "__main__":
    unittest.main()
