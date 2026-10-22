"""Synthetic contract tests for storage artifacts; no Facebook access required."""

import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import facebook_collector.storage as storage
from facebook_collector.storage import read_latest, write_run


CSV_HEADER = [
    "schema_version",
    "input_index",
    "duplicate_of",
    "input_url",
    "resolved_url",
    "identity_kind",
    "identity_post_id",
    "identity_owner_id",
    "identity_photo_id",
    "identity_group_id",
    "identity_route",
    "attempted_at",
    "collected_at",
    "status",
    "reason",
    "text_value",
    "text_status",
    "text_source",
    "reaction_value",
    "reaction_raw",
    "reaction_quality",
    "reaction_source",
    "comment_value",
    "comment_raw",
    "comment_quality",
    "comment_source",
    "share_value",
    "share_raw",
    "share_quality",
    "share_source",
    "latest_updated",
]


def outcome(identity, *, index=0, status="collected", text_status="candidate_text_unverified"):
    """Return a complete synthetic outcome with no network-derived dependencies."""
    return {
        "input_index": index,
        "duplicate_of": None,
        "input_url": f"https://www.facebook.com/synthetic/{index}",
        "resolved_url": f"https://www.facebook.com/resolved/{index}",
        "post_identity": identity,
        "attempted_at": "2026-10-21T04:30:15Z",
        "collected_at": "2026-10-21T04:30:16Z",
        "status": status,
        "reason": None,
        "text": {
            "value": "synthetic text",
            "status": text_status,
            "source": "synthetic",
        },
        "counters": {
            name: {"value": 1, "raw": "1", "quality": "exact", "source": "synthetic"}
            for name in ("reaction", "comment", "share")
        },
        "latest_updated": False,
    }


class StorageContractTests(unittest.TestCase):
    def test_event_write_failure_removes_run_artifacts_without_mutating_latest(self):
        record = outcome({"kind": "post", "post_id": "123", "owner_id": "456"})
        event = {"event_version": "1", "event": "accepted"}
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"
            with patch("facebook_collector.storage._write_events_atomically", side_effect=OSError("event failure")):
                with self.assertRaisesRegex(OSError, "event failure"):
                    write_run(output_dir, [record], "completed", None, run_id="event-failure", events=[event])

            self.assertFalse((output_dir / "runs" / "event-failure").exists())
            self.assertFalse((output_dir / "posts-latest.csv").exists())

    def test_write_run_returns_the_exact_results_document_and_writes_contract_header(self):
        record = outcome({"kind": "post", "post_id": "123", "owner_id": "456"})
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"

            results = write_run(output_dir, [record], "completed", None, run_id="run-contract")

            run_dir = output_dir / "runs" / "run-contract"
            written = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
            self.assertEqual(results, written)
            self.assertEqual(
                results,
                {
                    "schema_version": "1",
                    "run_id": "run-contract",
                    "run_status": "completed",
                    "stop_reason": None,
                    "outcomes": [{**record, "latest_updated": True}],
                },
            )
            with (run_dir / "posts.csv").open(encoding="utf-8", newline="") as file:
                reader = csv.DictReader(file)
                self.assertEqual(reader.fieldnames, CSV_HEADER)
                row = next(reader)
            self.assertEqual(row["schema_version"], "1")
            self.assertEqual(row["identity_post_id"], "123")
            self.assertEqual(row["identity_owner_id"], "456")
            self.assertEqual(row["identity_photo_id"], "")

    def test_posts_csv_flattens_each_route_specific_identity(self):
        records = [
            outcome({"kind": "post", "post_id": "post-id", "owner_id": "owner-id"}, index=0),
            outcome({"kind": "photo", "photo_id": "photo-id"}, index=1),
            outcome({"kind": "pfbid", "route": "/page/posts/pfbidabc"}, index=2),
            outcome({"kind": "group", "group_id": "group-id", "post_id": "group-post"}, index=3),
        ]
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"
            write_run(output_dir, records, "completed", None, run_id="routes")
            with (output_dir / "runs" / "routes" / "posts.csv").open(
                encoding="utf-8", newline=""
            ) as file:
                rows = list(csv.DictReader(file))

        self.assertEqual(
            [
                (row["identity_kind"], row["identity_post_id"], row["identity_owner_id"], row["identity_photo_id"], row["identity_group_id"], row["identity_route"])
                for row in rows
            ],
            [
                ("post", "post-id", "owner-id", "", "", ""),
                ("photo", "", "", "photo-id", "", ""),
                ("pfbid", "", "", "", "", "/page/posts/pfbidabc"),
                ("group", "group-post", "", "", "group-id", ""),
            ],
        )

    def test_eligible_successful_nulls_replace_the_whole_latest_record(self):
        identity = {"kind": "post", "post_id": "123", "owner_id": "456"}
        old = outcome(identity)
        replacement = outcome(identity, index=1, status="partial")
        replacement["text"]["value"] = None
        replacement["counters"]["reaction"] = {
            "value": None,
            "raw": None,
            "quality": "unverified",
            "source": "synthetic-null",
        }
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"
            write_run(output_dir, [old], "completed", None, run_id="old")
            result = write_run(output_dir, [replacement], "completed", None, run_id="replacement")
            latest = read_latest(output_dir / "posts-latest.csv")

        key = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertTrue(result["outcomes"][0]["latest_updated"])
        self.assertEqual(latest[key], {**replacement, "latest_updated": True})

    def test_identity_keys_do_not_collide_when_components_contain_colons(self):
        first = outcome({"kind": "post", "owner_id": "1:2", "post_id": "3"}, index=0)
        second = outcome({"kind": "post", "owner_id": "1", "post_id": "2:3"}, index=1)
        first["text"]["value"] = "first"
        second["text"]["value"] = "second"

        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"
            write_run(output_dir, [first, second], "completed", None, run_id="colon-identities")
            latest = read_latest(output_dir / "posts-latest.csv")

        self.assertEqual(len(latest), 2)
        self.assertEqual(
            {record["text"]["value"] for record in latest.values()},
            {"first", "second"},
        )

    def test_failure_preview_and_duplicate_never_replace_an_existing_latest_record(self):
        identity = {"kind": "photo", "photo_id": "789"}
        old = outcome(identity)
        failure = outcome(identity, index=1, status="error")
        failure["reason"] = "synthetic failure"
        preview = outcome(identity, index=2, status="partial", text_status="preview_only")
        duplicate = outcome(identity, index=3)
        duplicate["duplicate_of"] = 0
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"
            write_run(output_dir, [old], "completed", None, run_id="old")
            result = write_run(output_dir, [failure, preview, duplicate], "completed", None, run_id="preserve")
            latest = read_latest(output_dir / "posts-latest.csv")

        key = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertEqual([row["latest_updated"] for row in result["outcomes"]], [False, False, False])
        self.assertEqual(latest[key], {**old, "latest_updated": True})

    def test_missing_text_with_evidenced_photo_counters_never_replaces_latest(self):
        identity = {"kind": "photo", "photo_id": "789"}
        old = outcome(identity)
        missing_text = outcome(identity, index=1, status="partial", text_status="missing")
        missing_text["text"] = {"value": None, "status": "missing", "source": None}
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"
            write_run(output_dir, [old], "completed", None, run_id="old")
            result = write_run(output_dir, [missing_text], "completed", None, run_id="missing-text")
            latest = read_latest(output_dir / "posts-latest.csv")

        key = json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        self.assertFalse(result["outcomes"][0]["latest_updated"])
        self.assertEqual(latest[key], {**old, "latest_updated": True})

    def test_latest_write_failure_removes_new_run_artifacts(self):
        record = outcome({"kind": "post", "post_id": "123", "owner_id": "456"})
        real_replace = storage.os.replace
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"
            latest_path = output_dir / "posts-latest.csv"

            def fail_latest(source, destination):
                if Path(destination) == latest_path:
                    raise OSError("synthetic latest failure")
                return real_replace(source, destination)

            with patch("facebook_collector.storage.os.replace", side_effect=fail_latest):
                with self.assertRaises(OSError):
                    write_run(output_dir, [record], "completed", None, run_id="failed-latest")

            self.assertFalse((output_dir / "runs" / "failed-latest").exists())
            self.assertFalse(latest_path.exists())

    def test_malformed_existing_latest_is_preserved_without_replacement(self):
        record = outcome({"kind": "post", "post_id": "123", "owner_id": "456"})
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"
            latest_path = output_dir / "posts-latest.csv"
            latest_path.parent.mkdir(parents=True)
            malformed = "schema_version,wrong\\n1,data\\n"
            latest_path.write_text(malformed, encoding="utf-8")

            with self.assertRaises(ValueError):
                write_run(output_dir, [record], "completed", None, run_id="must-not-replace")

            self.assertEqual(latest_path.read_text(encoding="utf-8"), malformed)

    def test_csv_value_error_removes_temporary_and_run_artifacts(self):
        record = outcome({"kind": "post", "post_id": "123", "owner_id": "456"})
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"
            run_directory = output_dir / "runs" / "invalid-csv"

            with patch.object(
                csv.DictWriter,
                "writerows",
                side_effect=ValueError("synthetic CSV failure"),
            ):
                with self.assertRaisesRegex(ValueError, "synthetic CSV failure"):
                    write_run(output_dir, [record], "completed", None, run_id="invalid-csv")

            self.assertFalse(run_directory.exists())
            self.assertEqual(
                [path for path in output_dir.rglob("*") if path.is_file()],
                [],
            )

    def test_run_artifact_failure_does_not_mutate_existing_latest(self):
        old = outcome({"kind": "post", "post_id": "old", "owner_id": "owner"})
        replacement = outcome({"kind": "post", "post_id": "new", "owner_id": "owner"})
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"
            write_run(output_dir, [old], "completed", None, run_id="existing-run")
            latest_path = output_dir / "posts-latest.csv"
            original_latest = latest_path.read_bytes()

            with self.assertRaises(FileExistsError):
                write_run(output_dir, [replacement], "completed", None, run_id="existing-run")

            self.assertEqual(latest_path.read_bytes(), original_latest)

    def test_failure_only_run_creates_an_empty_latest_csv(self):
        failure = outcome({"kind": "photo", "photo_id": "789"}, status="error")
        failure["reason"] = "synthetic failure"
        with tempfile.TemporaryDirectory() as directory:
            output_dir = Path(directory) / "output"
            write_run(output_dir, [failure], "completed", None, run_id="failure-only")
            latest_path = output_dir / "posts-latest.csv"

            self.assertEqual(latest_path.read_bytes(), (",".join(CSV_HEADER) + "\r\n").encode())
            with latest_path.open(encoding="utf-8", newline="") as file:
                reader = csv.DictReader(file)
                self.assertEqual(reader.fieldnames, CSV_HEADER)
                self.assertEqual(list(reader), [])


if __name__ == "__main__":
    unittest.main()
