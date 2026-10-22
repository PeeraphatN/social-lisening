import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from facebook_collector import CollectionUnavailable, collect_posts
from facebook_collector.__main__ import main
from facebook_collector.model import BatchValidationError


VALID_URL = "https://www.facebook.com/share/p/19TTvcsmZ8/"
SYNTHETIC_URL = "https://www.facebook.com/900000007654321/posts/900000001234567/"
OFFLINE_FIXTURE = Path(__file__).parent / "e2e" / "fixtures" / "single-collected.json"


class CollectorPublicCoreTests(unittest.TestCase):
    def test_cli_delegates_the_offline_seam_to_the_public_core(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": str(OFFLINE_FIXTURE),
                "FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1",
            },
        ), patch("facebook_collector.collect_posts", return_value={}) as collect:
            output_dir = Path(directory) / "output"

            exit_code = main(
                ["collect", "--url", SYNTHETIC_URL, "--output-dir", str(output_dir)]
            )

            self.assertEqual(exit_code, 0)
            collect.assert_called_once_with([SYNTHETIC_URL], output_dir, log=False)

    def test_supported_offline_capture_uses_public_core_and_returns_canonical_artifacts(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            os.environ,
            {
                "FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": str(OFFLINE_FIXTURE),
                "FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1",
            },
        ):
            output_dir = Path(directory) / "output"

            results = collect_posts([SYNTHETIC_URL], output_dir)

            run_directory = output_dir / "runs" / results["run_id"]
            written = json.loads((run_directory / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(results, written)
            self.assertEqual(results["schema_version"], "1")
            self.assertEqual(results["outcomes"][0]["status"], "collected")
            self.assertTrue(results["outcomes"][0]["latest_updated"])
            self.assertTrue((run_directory / "posts.csv").exists())
            self.assertTrue((output_dir / "posts-latest.csv").exists())

    def test_invalid_input_writes_and_returns_one_trustworthy_null_outcome(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"

            results = collect_posts(["not a URL"], output_dir)

            written = json.loads(
                (output_dir / "runs" / results["run_id"] / "results.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(results, written)
            self.assertEqual(results["run_status"], "completed")
            self.assertIsNone(results["stop_reason"])
            self.assertEqual(
                results["outcomes"][0],
                {
                    "input_index": 0,
                    "duplicate_of": None,
                    "input_url": "not a URL",
                    "resolved_url": None,
                    "post_identity": None,
                    "attempted_at": None,
                    "collected_at": None,
                    "status": "invalid_input",
                    "reason": "malformed_url",
                    "text": {"value": None, "status": "missing", "source": None},
                    "counters": {
                        name: {
                            "value": None,
                            "raw": None,
                            "quality": "missing",
                            "source": None,
                        }
                        for name in ("reaction", "comment", "share")
                    },
                    "latest_updated": False,
                },
            )

    def test_exact_duplicate_invalid_input_keeps_two_linked_outcomes(self):
        with tempfile.TemporaryDirectory() as directory:
            results = collect_posts(["not a URL", "not a URL"], Path(directory))

        self.assertEqual(len(results["outcomes"]), 2)
        self.assertIsNone(results["outcomes"][0]["duplicate_of"])
        self.assertEqual(results["outcomes"][1]["duplicate_of"], 0)

    def test_accepted_input_fails_closed_until_live_collection_exists(self):
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"

            with self.assertRaises(CollectionUnavailable):
                collect_posts([VALID_URL], output_dir)

            self.assertFalse(output_dir.exists())

    def test_empty_or_over_limit_batch_rejects_before_output(self):
        cases = [[], [f"https://invalid/{index}" for index in range(11)]]
        for inputs in cases:
            with self.subTest(size=len(inputs)), tempfile.TemporaryDirectory() as directory:
                output_dir = Path(directory) / "output"
                with self.assertRaises(BatchValidationError):
                    collect_posts(inputs, output_dir)
                self.assertFalse(output_dir.exists())


if __name__ == "__main__":
    unittest.main()
