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
    write_offline_run,
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

    def test_offline_run_write_failure_leaves_no_result_files(self):
        capture = load_offline_capture(self.write_fixture(valid_fixture()))
        outcome = build_outcome(capture["submitted_url"], capture)
        real_write_text = Path.write_text

        def fail_results(path, *args, **kwargs):
            if path.name == "results.json":
                raise OSError("synthetic results failure")
            return real_write_text(path, *args, **kwargs)

        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"
            with patch.object(Path, "write_text", autospec=True, side_effect=fail_results):
                with self.assertRaisesRegex(OfflineCaptureError, "write offline run"):
                    write_offline_run(output_dir, outcome)

            result_files = [path for path in output_dir.rglob("*") if path.is_file()]
            self.assertEqual(result_files, [])


if __name__ == "__main__":
    unittest.main()
