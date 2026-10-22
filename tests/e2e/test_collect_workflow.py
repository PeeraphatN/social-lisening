"""Offline end-to-end acceptance test for one collected Facebook post."""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from facebook_collector import collect_posts


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).with_name("fixtures") / "single-collected.json"
SYNTHETIC_URL = "https://www.facebook.com/900000007654321/posts/900000001234567/"
EXPECTED_IDENTITY = {
    "kind": "post",
    "post_id": "900000001234567",
    "owner_id": "900000007654321",
}
EXPECTED_TEXT = "ทดสอบการเก็บข้อมูลแบบออฟไลน์ 🌿\nบรรทัดที่สอง"
EXPECTED_COUNTERS = {
    "reaction": (1200, "1.2K", "approximate"),
    "comment": (25, "25 ความคิดเห็น", "exact"),
    "share": (3, "3 แชร์", "exact"),
}
EXPECTED_CSV_HEADER = (
    "schema_version,input_index,duplicate_of,input_url,resolved_url,identity_kind,"
    "identity_post_id,identity_owner_id,identity_photo_id,identity_group_id,identity_route,"
    "attempted_at,collected_at,status,reason,text_value,text_status,text_source,"
    "reaction_value,reaction_raw,reaction_quality,reaction_source,comment_value,comment_raw,"
    "comment_quality,comment_source,share_value,share_raw,share_quality,share_source,"
    "latest_updated"
)


def assert_utc_rfc3339(test_case: unittest.TestCase, value: object) -> None:
    test_case.assertIsInstance(value, str)
    test_case.assertTrue(value.endswith("Z"))
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    test_case.assertEqual(parsed.utcoffset(), timedelta(0))
    test_case.assertEqual(parsed.tzinfo, timezone.utc)


class CollectWorkflowE2ETests(unittest.TestCase):
    def test_collects_one_offline_capture_and_exports_latest_record(self):
        """The public API and CLI export the same offline capture outcome."""
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"
            api_output_dir = Path(directory) / "api-output"
            environment = os.environ.copy()
            environment.update(
                {
                    "FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": str(FIXTURE),
                    "FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1",
                }
            )

            with patch.dict(
                os.environ,
                {
                    "FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": str(FIXTURE),
                    "FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1",
                },
            ):
                api_results = collect_posts([SYNTHETIC_URL], api_output_dir)

            api_written = json.loads(
                (api_output_dir / "runs" / api_results["run_id"] / "results.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(api_results, api_written)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "facebook_collector",
                    "collect",
                    "--url",
                    SYNTHETIC_URL,
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=REPO_ROOT,
                env=environment,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            self.assertEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )

            run_root = output_dir / "runs"
            run_directories = [path for path in run_root.iterdir() if path.is_dir()]
            self.assertEqual(len(run_directories), 1)
            run_directory = run_directories[0]

            results = json.loads((run_directory / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(results["schema_version"], api_results["schema_version"])
            self.assertEqual(results["run_status"], api_results["run_status"])
            self.assertEqual(results["stop_reason"], api_results["stop_reason"])
            self.assertEqual(
                {key: value for key, value in results["outcomes"][0].items() if key != "attempted_at"},
                {
                    key: value
                    for key, value in api_results["outcomes"][0].items()
                    if key != "attempted_at"
                },
            )
            self.assertEqual(results["schema_version"], "1")
            self.assertEqual(results["run_id"], run_directory.name)
            self.assertEqual(results["run_status"], "completed")
            self.assertIsNone(results["stop_reason"])
            self.assertEqual(len(results["outcomes"]), 1)

            outcome = results["outcomes"][0]
            self.assertEqual(outcome["input_index"], 0)
            self.assertIsNone(outcome["duplicate_of"])
            self.assertEqual(outcome["status"], "collected")
            self.assertIsNone(outcome["reason"])
            self.assertEqual(outcome["input_url"], SYNTHETIC_URL)
            self.assertEqual(outcome["resolved_url"], SYNTHETIC_URL)
            self.assertEqual(outcome["post_identity"], EXPECTED_IDENTITY)
            assert_utc_rfc3339(self, outcome["attempted_at"])
            assert_utc_rfc3339(self, outcome["collected_at"])
            self.assertEqual(outcome["text"]["value"], EXPECTED_TEXT)
            self.assertEqual(outcome["text"]["status"], "candidate_text_unverified")
            self.assertIsInstance(outcome["text"]["source"], str)
            self.assertTrue(outcome["text"]["source"])
            self.assertTrue(outcome["latest_updated"])

            for name, (value, raw, quality) in EXPECTED_COUNTERS.items():
                with self.subTest(counter=name):
                    counter = outcome["counters"][name]
                    self.assertEqual(counter["value"], value)
                    self.assertEqual(counter["raw"], raw)
                    self.assertEqual(counter["quality"], quality)
                    self.assertIsInstance(counter["source"], str)
                    self.assertTrue(counter["source"])

            posts_csv = (run_directory / "posts.csv").read_text(encoding="utf-8")
            latest_csv = (output_dir / "posts-latest.csv").read_text(encoding="utf-8")
            self.assertEqual(posts_csv.splitlines()[0], EXPECTED_CSV_HEADER)
            self.assertEqual(latest_csv.splitlines()[0], EXPECTED_CSV_HEADER)
            self.assertIn(EXPECTED_TEXT, posts_csv)
            self.assertIn(EXPECTED_TEXT, latest_csv)
            self.assertIn("1.2K", posts_csv)
            self.assertIn("1.2K", latest_csv)

            artifacts = [
                path
                for path in output_dir.rglob("*")
                if path.is_file()
                and (
                    path.suffix.lower() in {".htm", ".html", ".jpeg", ".jpg", ".png", ".webp"}
                    or "screenshot" in path.name.lower()
                )
            ]
            self.assertEqual(artifacts, [])


if __name__ == "__main__":
    unittest.main()
