import unittest

from facebook_collector.url_validation import (
    UrlRejected,
    validate_public_url,
    validate_redirect_url,
)


class PublicUrlValidationTests(unittest.TestCase):
    def test_accepts_only_the_approved_tested_forms(self):
        cases = {
            "https://www.facebook.com/share/p/19TTvcsmZ8/": {
                "family": "share",
                "identity": None,
            },
            "https://www.facebook.com/photo/?fbid=1649985453249994": {
                "family": "photo",
                "identity": {"kind": "photo", "photo_id": "1649985453249994"},
            },
            "https://www.facebook.com/photo/?fbid=1649985453249994&set=a.194492012132686": {
                "family": "photo",
                "identity": {"kind": "photo", "photo_id": "1649985453249994"},
            },
            "https://www.facebook.com/quantcornerthailand/posts/pfbid036bewdSfgEUJvMagUQJ98": {
                "family": "pfbid",
                "identity": {
                    "kind": "pfbid",
                    "route": "/quantcornerthailand/posts/pfbid036bewdSfgEUJvMagUQJ98",
                },
            },
            "https://www.facebook.com/groups/1108191221217612/?multi_permalinks=1455325143170883": {
                "family": "group",
                "identity": {
                    "kind": "group",
                    "group_id": "1108191221217612",
                    "post_id": "1455325143170883",
                },
            },
            "https://www.facebook.com/groups/1108191221217612/?multi_permalinks=1455325143170883&hoisted_section_header_type=recently_seen": {
                "family": "group",
                "identity": {
                    "kind": "group",
                    "group_id": "1108191221217612",
                    "post_id": "1455325143170883",
                },
            },
            "https://www.facebook.com/groups/1108191221217612/posts/1455325143170883": {
                "family": "group",
                "identity": {
                    "kind": "group",
                    "group_id": "1108191221217612",
                    "post_id": "1455325143170883",
                },
            },
            "https://www.facebook.com/groups/1108191221217612/posts/1455325143170883/": {
                "family": "group",
                "identity": {
                    "kind": "group",
                    "group_id": "1108191221217612",
                    "post_id": "1455325143170883",
                },
            },
        }

        for url, expected in cases.items():
            with self.subTest(url=url):
                self.assertEqual(validate_public_url(url), expected)

    def test_rejects_each_fixed_input_reason(self):
        cases = {
            "not a URL": "malformed_url",
            "http://www.facebook.com/share/p/19TTvcsmZ8/": "https_required",
            "https://m.facebook.com/share/p/19TTvcsmZ8/": "unsupported_host",
            "https://user@www.facebook.com/share/p/19TTvcsmZ8/": "credentials_forbidden",
            "https://www.facebook.com:443/share/p/19TTvcsmZ8/": "custom_port_forbidden",
            "https://www.facebook.com/search/posts/": "unsupported_route",
            "https://www.facebook.com/share/p/19TTvcsmZ8/?tracking=1": "unsupported_query",
        }

        for url, reason in cases.items():
            with self.subTest(reason=reason):
                with self.assertRaises(UrlRejected) as raised:
                    validate_public_url(url)
                self.assertEqual(raised.exception.reason, reason)

    def test_rejects_unapproved_or_ambiguous_identity_queries(self):
        urls = [
            "https://www.facebook.com/photo/",
            "https://www.facebook.com/photo/?fbid=abc",
            "https://www.facebook.com/photo/?fbid=1&fbid=2",
            "https://www.facebook.com/photo/?fbid=1&set=b.2",
            "https://www.facebook.com/groups/1/",
            "https://www.facebook.com/groups/1/?multi_permalinks=abc",
            "https://www.facebook.com/groups/1/?multi_permalinks=2&multi_permalinks=3",
            "https://www.facebook.com/groups/1/?multi_permalinks=2&hoisted_section_header_type=other",
            "https://www.facebook.com/groups/1/posts/2/?tracking=1",
            "https://www.facebook.com/share/p/token/#fragment",
        ]

        for url in urls:
            with self.subTest(url=url):
                with self.assertRaises(UrlRejected) as raised:
                    validate_public_url(url)
                self.assertEqual(raised.exception.reason, "unsupported_query")

    def test_redirect_reuses_allowlist_and_maps_any_rejection_to_unsafe_redirect(self):
        accepted = "https://www.facebook.com/photo/?fbid=123"
        self.assertEqual(validate_redirect_url(accepted), validate_public_url(accepted))

        with self.assertRaises(UrlRejected) as raised:
            validate_redirect_url("https://example.com/posts/123")

        self.assertEqual(raised.exception.reason, "unsafe_redirect")
        self.assertEqual(raised.exception.detail_reason, "unsupported_host")


if __name__ == "__main__":
    unittest.main()
