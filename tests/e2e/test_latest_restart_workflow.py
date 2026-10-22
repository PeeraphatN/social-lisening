"""Offline restart coverage for public latest-record persistence."""

import csv
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
POST_URL = "https://www.facebook.com/900000007654321/posts/900000001234567/"
POST_IDENTITY = {
    "kind": "post",
    "post_id": "900000001234567",
    "owner_id": "900000007654321",
}

ENTRYPOINT_SCRIPTS = {
    "api": """
import socket
import subprocess
import sys
from pathlib import Path

def forbidden(*args, **kwargs):
    raise AssertionError("network or browser attempted")

socket.create_connection = forbidden
socket.socket.connect = forbidden
subprocess.Popen = forbidden

from facebook_collector import collect_posts
collect_posts([sys.argv[1]], Path(sys.argv[2]))
""",
    "cli": """
import socket
import subprocess
import sys

def forbidden(*args, **kwargs):
    raise AssertionError("network or browser attempted")

socket.create_connection = forbidden
socket.socket.connect = forbidden
subprocess.Popen = forbidden

from facebook_collector.__main__ import main
raise SystemExit(main(["collect", "--url", sys.argv[1], "--output-dir", sys.argv[2]]))
""",
}


def capture(url: str, identity: dict, *, text="old text", text_status="candidate_text_unverified", reaction=1, outcome=None) -> dict:
    """Build a private fixture document for one synthetic public collection."""
    counters = {
        name: {
            "observed_value": value,
            "raw": None if value is None else str(value),
            "quality": "unverified" if value is None else "exact",
            "source": None if value is None else "synthetic",
        }
        for name, value in (("reaction", reaction), ("comment", 2), ("share", 3))
    }
    observed = {
        "submitted_url": url,
        "resolved_url": url,
        "validated_identity": identity,
        "captured_at": "2026-10-22T04:30:15Z" if text == "old text" else "2026-10-22T05:30:15Z",
        "candidate_text": {"value": text, "status": text_status, "source": "synthetic"},
        "engagement": counters,
    }
    if outcome is not None:
        observed["outcome"] = outcome
    return {"fixture_schema": "offline-observed-capture-v1", "observed_capture": observed}


class LatestRestartWorkflowTests(unittest.TestCase):
    def run_entrypoint(self, directory: Path, entrypoint: str, url: str, document: dict):
        fixture = directory / f"{entrypoint}-{len(list(directory.glob('*.json')))}.json"
        fixture.write_text(json.dumps(document), encoding="utf-8")
        environment = os.environ.copy()
        environment.update(
            {
                "FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE": str(fixture),
                "FACEBOOK_COLLECTOR_NETWORK_DISABLED": "1",
            }
        )
        return subprocess.run(
            [sys.executable, "-c", ENTRYPOINT_SCRIPTS[entrypoint], url, str(directory / "output")],
            cwd=REPO_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )

    def assert_succeeded(self, completed):
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def latest_rows(self, output_dir: Path) -> list[dict[str, str]]:
        with (output_dir / "posts-latest.csv").open(encoding="utf-8", newline="") as file:
            return list(csv.DictReader(file))

    def test_new_process_replaces_an_identitys_whole_latest_record_with_successful_nulls(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.assert_succeeded(
                self.run_entrypoint(directory, "api", POST_URL, capture(POST_URL, POST_IDENTITY))
            )
            self.assert_succeeded(
                self.run_entrypoint(
                    directory,
                    "cli",
                    POST_URL,
                    capture(POST_URL, POST_IDENTITY, text="new text", reaction=None),
                )
            )

            rows = self.latest_rows(directory / "output")

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["text_value"], "new text")
        self.assertEqual(rows[0]["reaction_value"], "")
        self.assertEqual(rows[0]["reaction_quality"], "unverified")
        self.assertEqual(rows[0]["collected_at"], "2026-10-22T05:30:15Z")

    def test_ineligible_restart_outcomes_preserve_the_existing_latest_bytes(self):
        cases = (
            ("preview", capture(POST_URL, POST_IDENTITY, text="preview", text_status="preview_only")),
            ("missing", capture(POST_URL, POST_IDENTITY, text=None, text_status="missing")),
            ("timeout", capture(POST_URL, POST_IDENTITY, outcome={"status": "timeout"})),
            ("error", capture(POST_URL, POST_IDENTITY, outcome={"status": "error", "reason": "synthetic_error"})),
            ("blocked", capture(POST_URL, POST_IDENTITY, outcome={"status": "blocked"})),
            (
                "identity-unverified",
                capture(
                    POST_URL,
                    POST_IDENTITY,
                    outcome={"status": "error", "reason": "identity_unverified"},
                ),
            ),
        )
        for name, replacement in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                self.assert_succeeded(
                    self.run_entrypoint(directory, "cli", POST_URL, capture(POST_URL, POST_IDENTITY))
                )
                latest_path = directory / "output" / "posts-latest.csv"
                before = latest_path.read_bytes()

                completed = self.run_entrypoint(directory, "cli", POST_URL, replacement)

                self.assert_succeeded(completed)
                self.assertEqual(latest_path.read_bytes(), before)

    def test_route_specific_identities_do_not_collide_and_malformed_latest_fails_closed(self):
        captures = (
            (POST_URL, POST_IDENTITY),
            ("https://www.facebook.com/photo/?fbid=200", {"kind": "photo", "photo_id": "200"}),
            (
                "https://www.facebook.com/page/posts/pfbidABC123",
                {"kind": "pfbid", "route": "/page/posts/pfbidABC123"},
            ),
            (
                "https://www.facebook.com/groups/300/posts/400/",
                {"kind": "group", "group_id": "300", "post_id": "400"},
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for index, (url, identity) in enumerate(captures):
                self.assert_succeeded(
                    self.run_entrypoint(
                        directory,
                        "cli",
                        url,
                        capture(url, identity, text=f"identity {index}"),
                    )
                )
            rows = self.latest_rows(directory / "output")
            self.assertEqual(len(rows), 4)
            self.assertEqual(
                {row["identity_kind"] for row in rows},
                {"post", "photo", "pfbid", "group"},
            )

            latest_path = directory / "output" / "posts-latest.csv"
            malformed = b"schema_version,wrong\r\n1,data\r\n"
            latest_path.write_bytes(malformed)
            completed = self.run_entrypoint(directory, "cli", POST_URL, capture(POST_URL, POST_IDENTITY))

            self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
            self.assertEqual(latest_path.read_bytes(), malformed)


if __name__ == "__main__":
    unittest.main()
