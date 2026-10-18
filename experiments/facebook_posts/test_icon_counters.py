"""Redacted fixtures reproduce split photo and hoisted group UFI summaries."""

import base64
import json
import unittest

import probe_post


def summary(post_id="123", comments=77, shares=79, share_raw="79"):
    feedback_id = base64.b64encode(f"feedback:{post_id}".encode()).decode()
    return {"comet_ufi_summary_and_actions_renderer": {"feedback": {
        "id": feedback_id, "subscription_target_id": post_id,
        "i18n_share_count": share_raw, "share_count": {"count": shares},
        "comments_count_summary_renderer": {"feedback": {
            "id": feedback_id,
            "comment_rendering_instance": {"comments": {"total_count": comments}},
        }},
    }}}


def html(*nodes):
    return "".join('<script type="application/json">' + json.dumps(node) + '</script>'
                   for node in nodes)


PHOTO_URL = "https://www.facebook.com/photo/?fbid=456&set=a.999"
GROUP_URL = "https://www.facebook.com/groups/999/?multi_permalinks=123"


class IconCounterTests(unittest.TestCase):
    def extract(self, document, url=GROUP_URL, body="All reactions\n391\n77\n79"):
        return probe_post.extract_browser_metrics(body, document, url)

    def test_photo_maps_media_to_story_before_reading_split_summary(self):
        media = {"currMedia": {"__typename": "Photo", "id": "456",
                              "creation_story": {"post_id": "123"},
                              "container_story": {"post_id": "123"}}}
        result = self.extract(html(media, summary(comments=366, shares=345, share_raw="345")),
                              PHOTO_URL, "All reactions\n1.1K\n366\n345")
        self.assertEqual((result["reaction_count"], result["comment_count"], result["share_count"]),
                         (1100, 366, 345))
        evidence = result["comment_counter_evidence"]
        self.assertEqual((evidence["post_id"], evidence["identity"]),
                         ("123", {"photo_id": "456", "post_id": "123"}))
        self.assertEqual(result["comment_text_raw"], "366")
        self.assertEqual(result["share_count_source"], "embedded_ufi_summary")

    def test_group_reads_hoisted_target_and_ignores_other_post(self):
        target = {"group": {"group_hoisted_feed": {"edges": [{"node": summary()}]}}}
        result = self.extract(html(target, {"node": summary("987", 999, 888, "888")}))
        self.assertEqual((result["comment_count"], result["share_count"]), (77, 79))
        self.assertEqual(result["share_counter_evidence"]["post_id"], "123")

    def test_unrelated_summary_is_not_a_counter(self):
        result = self.extract(html(summary("987")))
        self.assertIsNone(result["comment_count"])
        self.assertIsNone(result["share_count"])

    def test_photo_missing_or_conflicting_story_mapping_is_rejected(self):
        for media in ({"id": "999", "creation_story": {"post_id": "123"}},
                      {"id": "456"},
                      {"id": "456", "creation_story": {"post_id": "123"},
                       "container_story": {"post_id": "987"}}):
            with self.subTest(media=media):
                result = self.extract(html({"currMedia": media}, summary()), PHOTO_URL)
                self.assertIsNone(result["comment_count"])
                self.assertIsNone(result["share_count"])

    def test_inner_feedback_must_match_target(self):
        node = summary()
        node["comet_ufi_summary_and_actions_renderer"]["feedback"][
            "comments_count_summary_renderer"]["feedback"]["id"] = "unrelated"
        result = self.extract(html(node))
        self.assertIsNone(result["comment_count"])
        self.assertEqual(result["share_count"], 79)

    def test_malformed_missing_or_conflicting_counts_stay_null(self):
        for count in (None, True, -1, "77", 1.5):
            with self.subTest(count=count):
                result = self.extract(html(summary(comments=count, shares=count)))
                self.assertIsNone(result["comment_count"])
                self.assertIsNone(result["share_count"])
        result = self.extract(html(summary(), summary(comments=78, shares=80, share_raw="80")))
        self.assertIsNone(result["comment_count"])
        self.assertIsNone(result["share_count"])
        node = summary()
        feedback = node["comet_ufi_summary_and_actions_renderer"]["feedback"]
        del feedback["comments_count_summary_renderer"]
        del feedback["share_count"]
        result = self.extract(html(node))
        self.assertIsNone(result["comment_count"])
        self.assertIsNone(result["share_count"])

    def test_explicit_zero_and_compact_share_raw_are_preserved(self):
        result = self.extract(html(summary(comments=0, shares=0, share_raw="0")))
        self.assertEqual((result["comment_count"], result["share_count"]), (0, 0))
        result = self.extract(html(summary(shares=1234, share_raw="1.2 พัน")))
        self.assertEqual(result["share_count"], 1200)
        self.assertEqual(result["share_text_raw"], "1.2 พัน")
        self.assertEqual(result["share_counter_evidence"]["exact_count"], 1234)

    def test_malformed_share_raw_cannot_supply_unrelated_numbers(self):
        for raw in (None, "", "about 79", "79 posts 100 shares", "-79", "7,9", "0.5", "80"):
            with self.subTest(raw=raw):
                self.assertIsNone(self.extract(html(summary(share_raw=raw)))["share_count"])

    def test_mismatched_subscription_target_is_rejected(self):
        node = summary()
        node["comet_ufi_summary_and_actions_renderer"]["feedback"]["subscription_target_id"] = "987"
        result = self.extract(html(node))
        self.assertIsNone(result["comment_count"])
        self.assertIsNone(result["share_count"])

    def test_missing_or_malformed_json_is_not_zero(self):
        for document in ("", '<script type="application/json">{broken}</script>'):
            with self.subTest(document=document):
                result = self.extract(document)
                self.assertIsNone(result["comment_count"])
                self.assertIsNone(result["share_count"])

    def test_ambiguous_group_targets_and_unsupported_permalink_stay_null(self):
        for url in (GROUP_URL + ",987", GROUP_URL + "&multi_permalinks=987",
                    "https://www.facebook.com/user/posts/pfbidUNCONFIRMED"):
            with self.subTest(url=url):
                result = self.extract(html(summary()), url)
                self.assertIsNone(result["comment_count"])
                self.assertIsNone(result["share_count"])

    def test_group_permalink_path_and_body_counter_precedence(self):
        result = self.extract(html(summary()), "https://www.facebook.com/groups/redacted/permalink/123/",
                              "All reactions\n391\n76 comments\n78 shares")
        self.assertEqual((result["comment_count"], result["share_count"]), (76, 78))
        self.assertEqual(result["comment_count_source"], "body_text")

    def test_existing_story_zero_fallback_remains(self):
        result = self.extract(html(summary(comments=0)),
                              "https://www.facebook.com/story.php?story_fbid=123", "All reactions\n5\n2 shares")
        self.assertEqual(result["comment_count"], 0)
        self.assertEqual(result["comment_count_source"], "embedded_comment_summary")

    def test_p03_keeps_browser_comment_counter_without_summing_replies(self):
        result = self.extract(html(summary(comments=1, shares=0, share_raw="0")),
                              "https://www.facebook.com/user/posts/pfbidUNCONFIRMED",
                              "All reactions\n24\n1 comment\nReply\nReply\nReply")
        self.assertEqual((result["reaction_count"], result["comment_count"], result["share_count"]),
                         (24, 1, None))


if __name__ == "__main__":
    unittest.main()
