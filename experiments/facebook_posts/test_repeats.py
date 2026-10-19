import csv
import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_repeats
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

    def test_repeated_success_updates_one_post_and_failure_preserves_latest_success(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runs = root / "runs"
            runs.mkdir()
            references = []
            for number in range(1, 6):
                sample = f"P{number:02}"
                text = f"Public post {sample}"
                references.append({
                    "sample_id": sample,
                    "publisher": "Example Page",
                    "text": text,
                    "input_url": f"https://www.facebook.com/story.php?story_fbid={number}&id=1",
                    "fetch_url": f"https://www.facebook.com/story.php?story_fbid={number}&id=1",
                    "review": {"text_sha256": hashlib.sha256(text.encode()).hexdigest()},
                })
            (runs / "references.json").write_text(json.dumps(references), encoding="utf-8")

            def inspect(command, **_kwargs):
                run_id = command[-1]
                round_number, sample_id = run_id.rsplit("-r", 1)[1].split("-")
                if sample_id == "p01" and round_number == "3":
                    raise subprocess.TimeoutExpired(command, timeout=60)
                sample_number = int(sample_id[1:])
                reference = references[sample_number - 1]
                result = {
                    "status": "candidate_text_unverified",
                    "text": reference["text"],
                    "body_preview": f"Example Page\n{reference['text']}",
                    "http_status": 200,
                    "resolved_url": reference["fetch_url"],
                    "collected_at": f"2026-01-01T00:0{round_number}:00Z",
                    "reaction_count": int(round_number) * 100 + sample_number,
                    "comment_count": int(round_number) * 10 + sample_number,
                    "share_count": int(round_number) * 5 + sample_number,
                }
                if sample_id == "p03" and round_number == "3":
                    result["share_count"] = None
                (runs / f"{run_id}-inspection.json").write_text(
                    json.dumps(result), encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, "", "")

            with (patch.object(run_repeats, "__file__", str(root / "run_repeats.py")),
                  patch.object(run_repeats.subprocess, "run", side_effect=inspect),
                  patch.object(run_repeats.time, "sleep")):
                run_repeats.main()

            output = next(path for path in runs.iterdir() if path.is_dir())
            with (output / "posts.csv").open(encoding="utf-8-sig", newline="") as file:
                posts = {row["sample_id"]: row for row in csv.DictReader(file)}
            self.assertEqual(len(posts), 5)
            self.assertEqual(posts["P01"]["reaction_count"], "201")
            self.assertEqual(posts["P01"]["comment_count"], "21")
            self.assertEqual(posts["P01"]["share_count"], "11")
            self.assertEqual(posts["P01"]["collected_at"], "2026-01-01T00:02:00Z")
            self.assertEqual(posts["P01"]["matched_round"], "2")
            self.assertEqual(posts["P02"]["reaction_count"], "302")
            self.assertEqual(posts["P02"]["comment_count"], "32")
            self.assertEqual(posts["P02"]["share_count"], "17")
            self.assertEqual(posts["P02"]["collected_at"], "2026-01-01T00:03:00Z")
            self.assertEqual(posts["P02"]["matched_round"], "3")
            self.assertEqual(posts["P03"]["share_count"], "")

            with (output / "checks.csv").open(encoding="utf-8-sig", newline="") as file:
                checks = list(csv.DictReader(file))
            failed = next(row for row in checks
                          if row["sample_id"] == "P01" and row["round"] == "3")
            self.assertEqual(failed["status"], "request_failed")


if __name__ == "__main__":
    unittest.main()
