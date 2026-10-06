import unittest

from run_repeats import compare_post


class RepeatComparisonTests(unittest.TestCase):
    def setUp(self):
        self.reference = {"publisher": "Example Page", "text": "ข้อความไทย 😀\nครบ"}
        self.result = {"status": "candidate_text_unverified", "text": "ข้อความไทย 😀 ครบ",
                       "body_preview": "Example Page\nข้อความไทย 😀 ครบ", "http_status": 200}

    def test_whitespace_changes_do_not_fail_a_reviewed_text(self):
        self.assertEqual(compare_post(self.result, self.reference), "match")

    def test_missing_text_is_not_a_success(self):
        self.result.update(status="preview_only", text=None)
        self.assertEqual(compare_post(self.result, self.reference), "text_unavailable")

    def test_changed_emoji_is_detected(self):
        self.result["text"] = "ข้อความไทย 😢 ครบ"
        self.assertEqual(compare_post(self.result, self.reference), "text_changed")

    def test_missing_publisher_is_reported_separately(self):
        self.result["body_preview"] = "ข้อความไทย 😀 ครบ"
        self.assertEqual(compare_post(self.result, self.reference), "publisher_not_confirmed")

    def test_throttled_response_is_not_a_match(self):
        self.result["http_status"] = 429
        self.assertEqual(compare_post(self.result, self.reference), "blocked")


if __name__ == "__main__":
    unittest.main()
