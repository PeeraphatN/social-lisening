"""Offline coverage for identity-scoped counters on opaque pfbid routes."""

import unittest

from test_icon_counters import GROUP_URL, PHOTO_URL, html, summary, scoped_metrics


URL = "https://www.facebook.com/example/posts/pfbidRequested"
BODY = "All reactions\n24\nความคิดเห็น 1 รายการ\nแสดงความคิดเห็น"
STORY_ID = "opaque-story-123"
AUTO = object()
MISSING = object()


def route_node(route_url="/example/posts/pfbidRequested", story_id=STORY_ID):
    return {"initialRouteInfo": {"route": {
        "url": route_url,
        "rootView": {"props": {"storyID": story_id}},
    }}}


def story_node(shares=0, *, post_id="123", story_id=STORY_ID,
               nested_story_id=None, nested_post_id=None,
               outer_feedback_id=None, inner_feedback_id=None,
               subscription_target_id=None, include_feedback=True,
               include_share=True, is_empty=AUTO):
    feedback = summary(post_id, comments=4, shares=shares, share_raw=str(shares))
    renderer = feedback["comet_ufi_summary_and_actions_renderer"]["feedback"]
    if is_empty is not MISSING:
        renderer["share_count"]["is_empty"] = shares == 0 if is_empty is AUTO else is_empty
    if outer_feedback_id is not None:
        renderer["id"] = outer_feedback_id
    if inner_feedback_id is not None:
        renderer["comments_count_summary_renderer"]["feedback"]["id"] = inner_feedback_id
    if subscription_target_id is not None:
        renderer["subscription_target_id"] = subscription_target_id
    if not include_share:
        del renderer["share_count"]

    nested_story = {"id": nested_story_id or story_id,
                    "post_id": nested_post_id or post_id}
    if include_feedback:
        nested_story["feedback_context"] = {"feedback_target_with_context": feedback}
    story = {
        "id": story_id,
        "post_id": post_id,
        "permalink_url": "https://www.facebook.com/example/posts/pfbidCanonical",
        "comet_sections": {"feedback": {"story": {
            "story_ufi_container": {"story": nested_story},
        }}},
    }
    return {"data": {"node_v2": story}}


def document(shares=0, *, route_url="/example/posts/pfbidRequested", extra=None, **story_options):
    return html(route_node(route_url), story_node(shares, **story_options), *(extra or []))


class PfbidShareTests(unittest.TestCase):
    def check_missing(self, content):
        metrics = scoped_metrics(BODY, content, URL)
        self.assertEqual(metrics["reaction_count"], 24)
        self.assertEqual(metrics["comment_count"], 1)
        self.assertIsNone(metrics["share_count"])
        self.assertIsNone(metrics["share_text_raw"])
        self.assertIsNone(metrics["share_count_source"])
        return metrics

    def test_matching_identity_chain_preserves_zero(self):
        metrics = scoped_metrics(BODY, document(), URL)
        self.assertEqual(metrics["share_count"], 0)
        self.assertEqual(metrics["share_count_source"], "embedded_ufi_summary")

    def test_matching_identity_chain_returns_positive_share_count(self):
        metrics = scoped_metrics(BODY, document(shares=79), URL)
        self.assertEqual(metrics["share_count"], 79)
        self.assertEqual(metrics["share_text_raw"], "79")

    def test_zero_share_with_is_empty_false_returns_none(self):
        self.check_missing(document(is_empty=False))

    def test_positive_share_with_is_empty_true_returns_none(self):
        self.check_missing(document(shares=79, is_empty=True))

    def test_missing_is_empty_returns_none(self):
        self.check_missing(document(is_empty=MISSING))

    def test_non_boolean_is_empty_returns_none(self):
        for is_empty in (None, 0, 1, "false"):
            with self.subTest(is_empty=is_empty):
                self.check_missing(document(is_empty=is_empty))

    def test_route_mismatch_returns_none(self):
        self.check_missing(document(route_url="/example/posts/pfbidOther"))

    def test_story_identity_mismatch_returns_none(self):
        self.check_missing(document(nested_story_id="other-story"))
        self.check_missing(document(nested_post_id="987"))

    def test_feedback_identity_mismatch_returns_none(self):
        for options in ({"outer_feedback_id": "other"},
                        {"inner_feedback_id": "other"},
                        {"subscription_target_id": "987"}):
            with self.subTest(options=options):
                self.check_missing(document(**options))

    def test_conflicting_matching_summaries_return_none(self):
        self.check_missing(document(extra=[story_node(shares=8)]))

    def test_missing_share_counter_returns_none(self):
        self.check_missing(document(include_share=False))

    def test_displayed_share_counter_takes_precedence(self):
        metrics = scoped_metrics(BODY + "\nแชร์ 406 ครั้ง", document(), URL)
        self.assertEqual(metrics["share_count"], 406)
        self.assertEqual(metrics["share_count_source"], "body_text")

    def test_unrelated_post_json_cannot_supply_a_value(self):
        content = document(include_feedback=False,
                           extra=[story_node(shares=91, story_id="unrelated-story")])
        self.check_missing(content)

    def test_existing_photo_and_group_extraction_is_unchanged(self):
        group = scoped_metrics("All reactions\n391", html(summary()), GROUP_URL)
        media = {"currMedia": {"id": "456", "creation_story": {"post_id": "123"},
                                "container_story": {"post_id": "123"}}}
        photo = scoped_metrics("All reactions\n391", html(media, summary()), PHOTO_URL)
        self.assertEqual((group["comment_count"], group["share_count"]), (77, 79))
        self.assertEqual((photo["comment_count"], photo["share_count"]), (77, 79))


if __name__ == "__main__":
    unittest.main()
