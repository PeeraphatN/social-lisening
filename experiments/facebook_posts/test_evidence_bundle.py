import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from evidence_bundle import _bundle_id, export_bundle, import_bundle


class EvidenceBundleTests(unittest.TestCase):
    def test_export_import_selected_files_with_provenance(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "worktree"
            root.mkdir()
            evidence_root = root / "runs"
            source = evidence_root / "session-inspection.json"
            source.parent.mkdir()
            source.write_text('{"status":"match"}\n', encoding="utf-8")
            bundle = Path(directory) / "handoff.zip"
            manifest = export_bundle(evidence_root, bundle, "e50e39b",
                                     [source.relative_to(evidence_root)])
            destination = Path(directory) / "received-runs"
            received = import_bundle(bundle, destination, expected_source_commit="e50e39b")
            self.assertEqual(received["bundle_id"], manifest["bundle_id"])
            self.assertEqual((destination / source.name).read_text(encoding="utf-8"),
                             source.read_text(encoding="utf-8"))
            self.assertFalse((destination / "runs" / source.name).exists())
            provenance = destination / "handoff" / f"{manifest['bundle_id']}.json"
            self.assertEqual(json.loads(provenance.read_text(encoding="utf-8")), received)
            self.assertEqual(manifest["files"][0]["sha256"],
                             hashlib.sha256(source.read_bytes()).hexdigest())

    def test_import_requires_expected_source_commit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "worktree"
            root.mkdir()
            source = root / "runs" / "inspection.json"
            source.parent.mkdir()
            source.write_text("evidence", encoding="utf-8")
            bundle = Path(directory) / "handoff.zip"
            export_bundle(root, bundle, "commit-a", [source.relative_to(root)])
            with self.assertRaisesRegex(ValueError, "expected source commit"):
                import_bundle(bundle, Path(directory) / "received")

    def test_import_rejects_wrong_source_before_writing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "worktree"
            root.mkdir()
            source = root / "runs" / "inspection.json"
            source.parent.mkdir()
            source.write_text("evidence", encoding="utf-8")
            bundle = Path(directory) / "handoff.zip"
            export_bundle(root, bundle, "commit-a", [source.relative_to(root)])
            destination = Path(directory) / "received"
            with self.assertRaisesRegex(ValueError, "source commit"):
                import_bundle(bundle, destination, expected_source_commit="commit-b")
            self.assertFalse(destination.exists())

    def test_import_rejects_tampered_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "worktree"
            root.mkdir()
            source = root / "runs" / "inspection.json"
            source.parent.mkdir()
            source.write_text("evidence", encoding="utf-8")
            bundle = Path(directory) / "handoff.zip"
            export_bundle(root, bundle, "commit-a", [source.relative_to(root)])
            tampered = Path(directory) / "tampered.zip"
            with zipfile.ZipFile(bundle) as original, zipfile.ZipFile(tampered, "w") as changed:
                for item in original.infolist():
                    data = original.read(item.filename)
                    if item.filename != "manifest.json":
                        data += b"tampered"
                    changed.writestr(item, data)
            with self.assertRaisesRegex(ValueError, "sha256"):
                import_bundle(tampered, Path(directory) / "received", expected_source_commit="commit-a")

    def test_import_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory) / "bad.zip"
            manifest = {
                "schema_version": 1,
                "source_commit": "commit-a",
                "files": [{"path": "../escape.txt", "size": 1, "sha256": "0" * 64}],
            }
            manifest["bundle_id"] = _bundle_id(manifest)
            with zipfile.ZipFile(bundle, "w") as archive:
                archive.writestr("manifest.json", json.dumps(manifest))
                archive.writestr("../escape.txt", "x")
            with self.assertRaisesRegex(ValueError, "path"):
                import_bundle(bundle, Path(directory) / "received", expected_source_commit="commit-a")


if __name__ == "__main__":
    unittest.main()
