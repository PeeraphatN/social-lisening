"""Focused validation tests for the internal offline capture seam."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from facebook_collector.offline import (
    OfflineCaptureError,
    build_outcome,
    load_offline_capture,
    offline_enabled,
    read_latest_rows,
    write_latest,
)


def valid_fixture() -> dict:
    return {
        "fixture_schema": "offline-observed-capture-v1",
        "observed_capture": {
            "submitted_url": "https://www.facebook.com/900000007654321/posts/900000001234567/",
            "resolved_url": "https://www.facebook.com/900000007654321/posts/900000001234567/",
            "validated_identity": {
                "kind": "post",
                "post_id": "900000001234567",
                "owner_id": "900000007654321",
            },
            "captured_at": "2026-10-21T04:30:15Z",
            "candidate_text": {"value": "synthetic", "source": "synthetic_source"},
            "engagement": {
                name: {
                    "observed_value": value,
                    "raw": str(value),
                    "quality": "exact",
                    "source": "synthetic_source",
                }
                for name, value in (("reaction", 1), ("comment", 2), ("share", 3))
            },
        },
    }


class OfflineCaptureValidationTests(unittest.TestCase):
    def write_fixture(self, document: dict) -> Path:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "capture.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def test_seam_requires_both_environment_settings(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(offline_enabled())
        with patch.dict(os.environ, {"FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": "capture.json"}, clear=True):
            self.assertFalse(offline_enabled())
        with patch.dict(os.environ, {"FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1"}, clear=True):
            self.assertFalse(offline_enabled())
        with patch.dict(
            os.environ,
            {
                "FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": "capture.json",
                "FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1",
            },
            clear=True,
        ):
            self.assertTrue(offline_enabled())

    def test_load_rejects_boolean_metric_values_and_bad_identity(self):
        document = valid_fixture()
        document["observed_capture"]["engagement"]["reaction"]["observed_value"] = True
        document["observed_capture"]["validated_identity"] = {"kind": "post", "post_id": "post"}

        with self.assertRaisesRegex(OfflineCaptureError, "identity|observed_value"):
            load_offline_capture(self.write_fixture(document))

    def test_load_returns_validated_capture(self):
        capture = load_offline_capture(self.write_fixture(valid_fixture()))

        self.assertEqual(capture["validated_identity"]["post_id"], "900000001234567")
        self.assertEqual(capture["engagement"]["share"]["observed_value"], 3)

    def test_load_rejects_noncanonical_captured_at_values(self):
        for timestamp in (
            "20261021T043015Z",
            "2026-10-21 04:30:15Z",
            "2026-10-21X04:30:15Z",
            "2026-10-21T04:30:15+00:00",
            "2026-02-30T04:30:15Z",
            "2026-10-21T25:30:15Z",
        ):
            with self.subTest(timestamp=timestamp):
                document = valid_fixture()
                document["observed_capture"]["captured_at"] = timestamp
                with self.assertRaisesRegex(OfflineCaptureError, "captured_at"):
                    load_offline_capture(self.write_fixture(document))

    def test_load_accepts_canonical_fractional_captured_at(self):
        document = valid_fixture()
        document["observed_capture"]["captured_at"] = "2026-10-21T04:30:15.123456Z"

        capture = load_offline_capture(self.write_fixture(document))

        self.assertEqual(capture["captured_at"], "2026-10-21T04:30:15.123456Z")

    def test_load_rejects_urls_outside_the_internal_fixture_route_family(self):
        invalid_urls = (
            "http://www.facebook.com/900000007654321/posts/900000001234567/",
            "https://facebook.com/900000007654321/posts/900000001234567/",
            "https://www.facebook.com.evil.example/900000007654321/posts/900000001234567/",
            "https://evil.www.facebook.com/900000007654321/posts/900000001234567/",
            "https://user@www.facebook.com/900000007654321/posts/900000001234567/",
            "https://www.facebook.com:8443/900000007654321/posts/900000001234567/",
            "https://www.facebook.com/owner/posts/900000001234567/",
            "https://www.facebook.com/900000007654321/posts/post/",
            "https://www.facebook.com/900000007654321/photos/900000001234567/",
        )
        for field in ("submitted_url", "resolved_url"):
            for url in invalid_urls:
                with self.subTest(field=field, url=url):
                    document = valid_fixture()
                    document["observed_capture"][field] = url
                    with self.assertRaisesRegex(OfflineCaptureError, field):
                        load_offline_capture(self.write_fixture(document))

    def test_build_outcome_requires_the_cli_url_to_match_the_submitted_url(self):
        capture = load_offline_capture(self.write_fixture(valid_fixture()))

        with self.assertRaisesRegex(OfflineCaptureError, "input URL"):
            build_outcome("https://www.facebook.com/900000007654321/posts/900000001234568/", capture)


class LatestCsvTests(unittest.TestCase):
    def outcome(self, post_id: str, text: str) -> dict:
        return {
            "input_url": f"https://www.facebook.com/owner/posts/{post_id}/",
            "resolved_url": f"https://www.facebook.com/owner/posts/{post_id}/",
            "post_identity": {"kind": "post", "post_id": post_id, "owner_id": "owner"},
            "attempted_at": "2026-10-21T04:30:15Z",
            "collected_at": "2026-10-21T04:30:15Z",
            "status": "collected",
            "reason": None,
            "text": {"value": text, "status": "candidate_text_unverified", "source": "source"},
            "counters": {
                name: {"value": value, "raw": str(value), "quality": "exact", "source": "source"}
                for name, value in (("reaction", 1), ("comment", 2), ("share", 3))
            },
            "latest_updated": True,
        }

    def test_latest_replaces_matching_identity_and_preserves_unrelated_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "posts-latest.csv"
            write_latest(path, self.outcome("one", "old"))
            write_latest(path, self.outcome("two", "other"))
            write_latest(path, self.outcome("one", "new"))

            rows = read_latest_rows(path)

        one = '{"kind":"post","owner_id":"owner","post_id":"one"}'
        two = '{"kind":"post","owner_id":"owner","post_id":"two"}'
        self.assertEqual(set(rows), {one, two})
        self.assertEqual(rows[one]["text"]["value"], "new")
        self.assertEqual(rows[two]["text"]["value"], "other")

    def test_latest_identity_keys_do_not_collide_when_components_contain_colons(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "posts-latest.csv"
            first = self.outcome("3", "first")
            first["post_identity"] = {"kind": "post", "owner_id": "1:2", "post_id": "3"}
            second = self.outcome("2:3", "second")
            second["post_identity"] = {"kind": "post", "owner_id": "1", "post_id": "2:3"}
            write_latest(path, first)
            write_latest(path, second)

            rows = read_latest_rows(path)

        self.assertEqual(len(rows), 2)
        self.assertEqual({record["text"]["value"] for record in rows.values()}, {"first", "second"})

    def test_latest_rejects_a_malformed_header_without_replacing_the_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "posts-latest.csv"
            original = b"identity_kind,identity_post_id\\npost,123\\n"
            path.write_bytes(original)

            with self.assertRaisesRegex(OfflineCaptureError, "schema"):
                write_latest(path, self.outcome("new", "new text"))

            self.assertEqual(path.read_bytes(), original)

    def test_latest_rejects_a_malformed_row_without_replacing_the_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "posts-latest.csv"
            write_latest(path, self.outcome("old", "old text"))
            original = path.read_text(encoding="utf-8")
            original = original.replace(
                "2026-10-21T04:30:15Z,2026-10-21T04:30:15Z",
                "2026-10-21T04:30:15Z,bad timestamp",
            )
            path.write_text(original, encoding="utf-8")

            with self.assertRaisesRegex(OfflineCaptureError, "collected_at"):
                write_latest(path, self.outcome("new", "new text"))

            self.assertEqual(path.read_text(encoding="utf-8"), original)


if __name__ == "__main__":
    unittest.main()
