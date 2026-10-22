"""Offline contract tests for opt-in collector event logging."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from facebook_collector import collect_posts


FIXTURE = Path(__file__).parent / "e2e" / "fixtures" / "single-collected.json"
POST_URL = "https://www.facebook.com/900000007654321/posts/900000001234567/"
RETRY_URL = "https://www.facebook.com/900000007654321/posts/900000001234570/"
HTTP_URL = "https://www.facebook.com/900000007654321/posts/900000001234571/"
IDENTITY_URL = "https://www.facebook.com/900000007654321/posts/900000001234568/"
BLOCKED_URL = "https://www.facebook.com/900000007654321/posts/900000001234569/"


class StructuredLoggingTests(unittest.TestCase):
    def fixture(self, directory, synthetic_outcomes):
        document = json.loads(FIXTURE.read_text(encoding="utf-8"))
        document["synthetic_outcomes"] = synthetic_outcomes
        path = Path(directory) / "capture.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return path

    def collect(self, directory, urls, fixture, *, log):
        with patch.dict(
            os.environ,
            {
                "FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": str(fixture),
                "FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1",
            },
        ), patch("facebook_collector.model.time.sleep"), patch(
            "facebook_collector.collector.utc_now", return_value="2026-10-22T08:00:00Z"
        ), patch(
            "facebook_collector.offline.utc_now", return_value="2026-10-22T08:00:00Z"
        ):
            return collect_posts(urls, Path(directory) / "output", log=log)

    def test_default_off_writes_no_events_and_enabled_logging_preserves_results_and_latest(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.fixture(root, [])
            disabled = self.collect(root / "off", [POST_URL], fixture, log=False)
            enabled = self.collect(root / "on", [POST_URL], fixture, log=True)

            self.assertEqual(
                {key: value for key, value in disabled.items() if key != "run_id"},
                {key: value for key, value in enabled.items() if key != "run_id"},
            )
            self.assertFalse((root / "off" / "output" / "runs" / disabled["run_id"] / "events.jsonl").exists())
            self.assertEqual(
                (root / "off" / "output" / "posts-latest.csv").read_bytes(),
                (root / "on" / "output" / "posts-latest.csv").read_bytes(),
            )
            events = [
                json.loads(line)
                for line in (root / "on" / "output" / "runs" / enabled["run_id"] / "events.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(events[0]["event"], "accepted")
            self.assertEqual(events[0]["time"], "2026-10-22T08:00:00Z")
            self.assertEqual(events[0]["url_family"], "post")

    def test_enabled_events_cover_synthetic_decisions_without_sensitive_capture_data(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fixture = self.fixture(
                root,
                [
                    {"submitted_url": RETRY_URL, "status": "http", "http_status": 408},
                    {"submitted_url": HTTP_URL, "status": "http", "http_status": 404},
                    {"submitted_url": IDENTITY_URL, "status": "identity_unverified"},
                    {"submitted_url": BLOCKED_URL, "status": "blocked"},
                ],
            )
            results = self.collect(
                root,
                [POST_URL, "not a URL", POST_URL, RETRY_URL, HTTP_URL, IDENTITY_URL, BLOCKED_URL, POST_URL],
                fixture,
                log=True,
            )
            event_path = root / "output" / "runs" / results["run_id"] / "events.jsonl"
            events = [json.loads(line) for line in event_path.read_text(encoding="utf-8").splitlines()]
            names = [event["event"] for event in events]

            self.assertEqual(results["run_status"], "stopped")
            self.assertTrue({"accepted", "rejected", "duplicate", "retry", "timeout", "http", "identity_unverified", "blocked", "stopped"}.issubset(names))
            self.assertEqual([event["attempt"] for event in events if event["event"] == "retry"], [1, 2, 3])
            self.assertEqual([event["http_status"] for event in events if event["event"] == "http"], [408, 404])
            for event in events:
                self.assertEqual(event["event_version"], "1")
                self.assertEqual(event["feature"], "facebook_post_collector")
                self.assertIn("status", event)
                self.assertIn("reason", event)
                self.assertTrue(
                    set(event).issubset(
                        {
                            "event_version",
                            "time",
                            "feature",
                            "event",
                            "status",
                            "reason",
                            "input_index",
                            "url_family",
                            "attempt",
                            "http_status",
                        }
                    )
                )
            rendered = event_path.read_text(encoding="utf-8")
            self.assertNotIn("synthetic text", rendered)
            self.assertNotIn('"raw"', rendered)
            self.assertNotIn("input_url", rendered)

    def test_cli_keeps_events_opt_in(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            environment = os.environ | {
                "FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": str(FIXTURE),
                "FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1",
            }
            for name, extra in (("off", []), ("on", ["--log"])):
                output_dir = root / name
                completed = subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "facebook_collector",
                        "collect",
                        "--url",
                        POST_URL,
                        "--output-dir",
                        str(output_dir),
                        *extra,
                    ],
                    cwd=Path(__file__).parent.parent,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                run_directory = next((output_dir / "runs").iterdir())
                self.assertEqual((run_directory / "events.jsonl").exists(), name == "on")
