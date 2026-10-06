import unittest

from probe_post import extract_post, validate_url


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


if __name__ == "__main__":
    unittest.main()
