import unittest

from probe_post import extract_post, extract_social_metrics, parse_count, validate_url


class PostProbeTests(unittest.TestCase):
    def test_preview_is_not_reported_as_full_post(self):
        result = extract_post('<meta property="og:description" content="ข้อความ…">')
        self.assertEqual(result["status"], "preview_only")
        self.assertIsNone(result["text"])
        self.assertEqual(result["preview_text"], "ข้อความ…")

    def test_matching_message_is_a_candidate_until_manually_verified(self):
        html = '''<meta property="og:description" content="ข้อความไทย...">
        <script type="application/json">{"data": [
          {"message": {"text": "ความคิดเห็นของคนอื่น"}},
          {"message": {"text": "ข้อความไทยฉบับยาว 😀"}}
        ]}</script>'''
        result = extract_post(html)
        self.assertEqual(result["text"], "ข้อความไทยฉบับยาว 😀")
        self.assertEqual(result["status"], "candidate_text_unverified")

    def test_multiple_matches_require_review_instead_of_picking_longest(self):
        html = '''<meta property="og:description" content="ข้อความ...">
        <script type="application/json">[{"message":{"text":"ข้อความหนึ่ง"}},
        {"message":{"text":"ข้อความสอง"}}]</script>'''
        result = extract_post(html)
        self.assertEqual(result["status"], "ambiguous")
        self.assertIsNone(result["text"])

    def test_credentials_or_non_facebook_urls_are_rejected(self):
        for url in ("http://www.facebook.com/", "https://example.com/",
                    "https://user:password@www.facebook.com/"):
            with self.assertRaises(ValueError):
                validate_url(url)

    def test_parse_count_supports_compact_numbers(self):
        self.assertEqual(parse_count("1.2K comments"), 1200)
        self.assertEqual(parse_count("แชร์ 3 ครั้ง"), 3)

    def test_extract_social_metrics_keeps_raw_counter_text(self):
        result = extract_social_metrics("Like\n1.2K comments\nแชร์ 3 ครั้ง")
        self.assertEqual(result["comment_count"], 1200)
        self.assertEqual(result["comment_text_raw"], "1.2K comments")
        self.assertEqual(result["share_count"], 3)
        self.assertEqual(result["share_text_raw"], "แชร์ 3 ครั้ง")

    def test_extract_social_metrics_reads_all_reactions_pair(self):
        result = extract_social_metrics("ความรู้สึกทั้งหมด\n161\n65 ความคิดเห็น")
        self.assertEqual(result["reaction_count"], 161)
        self.assertEqual(result["reaction_text_raw"], "ความรู้สึกทั้งหมด 161")

    def test_extract_social_metrics_ignores_long_post_text(self):
        result = extract_social_metrics("ผมเสียเวลา 555 คนพวกนี้มา comment ว่าคนใช้ Codex ไม่ฉลาด")
        self.assertIsNone(result["comment_count"])


if __name__ == "__main__":
    unittest.main()
