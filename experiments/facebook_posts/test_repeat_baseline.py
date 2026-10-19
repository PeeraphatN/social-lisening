import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from repeat_baseline import load_baseline, migrate_legacy, normalize_text, text_sha256


class RepeatBaselineTests(unittest.TestCase):
    def test_hash_ignores_whitespace_but_preserves_content(self):
        self.assertEqual(text_sha256("a\n  b"), text_sha256("a b"))
        self.assertNotEqual(text_sha256("a b"), text_sha256("a c"))
        self.assertEqual(len(text_sha256("a b")), hashlib.sha256().digest_size * 2)

    def test_valid_baseline_contains_hash_only_references(self):
        baseline = {
            "schema_version": 1,
            "samples": [{
                "sample_id": "P01",
                "publisher": "Example Page",
                "input_url": "https://www.facebook.com/story.php?story_fbid=1&id=2",
                "fetch_url": "https://www.facebook.com/story.php?story_fbid=1&id=2",
                "review": {
                    "normalized_text_sha256": text_sha256("hello"),
                    "reviewed_at": "2026-10-19T00:00:00Z",
                    "evidence": "runs/example-inspection.json",
                },
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "repeat-baseline.json"
            path.write_text(json.dumps(baseline), encoding="utf-8")
            references = load_baseline(path)
        self.assertEqual(references[0]["review"]["text_sha256"], text_sha256("hello"))
        self.assertNotIn("text", references[0])

    def test_raw_text_is_rejected_from_tracked_baseline(self):
        baseline = {
            "schema_version": 1,
            "samples": [{
                "sample_id": "P01",
                "publisher": "Example Page",
                "input_url": "https://www.facebook.com/story.php?story_fbid=1&id=2",
                "fetch_url": "https://www.facebook.com/story.php?story_fbid=1&id=2",
                "text": "must not be tracked",
                "review": {
                    "normalized_text_sha256": text_sha256("hello"),
                    "reviewed_at": "2026-10-19T00:00:00Z",
                    "evidence": "runs/example-inspection.json",
                },
            }],
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "repeat-baseline.json"
            path.write_text(json.dumps(baseline), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "raw text"):
                load_baseline(path)

    def test_migration_discards_raw_text_and_keeps_provenance(self):
        legacy = [{
            "sample_id": "P01",
            "publisher": "Example Page",
            "text": "hello\nworld",
            "input_url": "https://www.facebook.com/story.php?story_fbid=1&id=2",
            "fetch_url": "https://www.facebook.com/story.php?story_fbid=1&id=2",
            "review": {
                "reviewed_at": "2026-10-19T00:00:00Z",
                "evidence": "runs/old-inspection.json",
                "method": "anonymous_browser_rendered_content",
            },
        }]
        baseline = migrate_legacy(legacy)
        self.assertEqual(baseline["schema_version"], 1)
        sample = baseline["samples"][0]
        self.assertNotIn("text", sample)
        self.assertEqual(sample["review"]["normalized_text_sha256"], text_sha256("hello world"))
        self.assertEqual(sample["review"]["evidence"], "runs/old-inspection.json")
        self.assertEqual(normalize_text(" hello\nworld "), "hello world")

    def test_migration_cli_writes_hash_only_output(self):
        legacy = [{
            "sample_id": "P01",
            "publisher": "Example Page",
            "text": "hello",
            "input_url": "https://www.facebook.com/story.php?story_fbid=1&id=2",
            "fetch_url": "https://www.facebook.com/story.php?story_fbid=1&id=2",
            "review": {
                "reviewed_at": "2026-10-19T00:00:00Z",
                "evidence": "runs/old.json",
            },
        }]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "references.json"
            output = root / "repeat-baseline.json"
            source.write_text(json.dumps(legacy), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(Path(__file__).with_name("migrate_repeat_baseline.py")),
                 str(source), str(output)],
                capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            data = json.loads(output.read_text(encoding="utf-8"))
            self.assertNotIn("text", data["samples"][0])
            self.assertNotIn("text", data["samples"][0]["review"])
            self.assertEqual(data["samples"][0]["review"]["normalized_text_sha256"],
                             text_sha256("hello"))

    def test_missing_or_malformed_baseline_fails_before_use(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "missing.json"
            with self.assertRaises(FileNotFoundError):
                load_baseline(path)
            path.write_text("[]", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "object"):
                load_baseline(path)


if __name__ == "__main__":
    unittest.main()
