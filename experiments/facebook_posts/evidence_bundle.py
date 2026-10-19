"""Portable, explicit handoff bundles for selected ignored evidence files."""

import hashlib
import json
import os
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

SCHEMA_VERSION = 1
_HASH = re.compile(r"^[0-9a-f]{64}$")


def _safe_path(value):
    raw = os.fspath(value).replace("\\", "/")
    path = PurePosixPath(raw)
    if (not raw or path.is_absolute() or ":" in path.parts[0]
            or ".." in path.parts or "manifest.json" == str(path)):
        raise ValueError(f"unsafe bundle path: {value}")
    return "/".join(path.parts)


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _bundle_id(manifest):
    unsigned = {key: value for key, value in manifest.items() if key != "bundle_id"}
    return _sha256(_json_bytes(unsigned))[:16]


def export_bundle(root, output, source_commit, paths, source_session=None):
    """Export paths relative to root for import into the corresponding root."""
    root = Path(root).resolve()
    output = Path(output).resolve()
    try:
        output.relative_to(root)
    except ValueError:
        pass
    else:
        raise ValueError("bundle output must be outside the worktree")
    if output.exists():
        raise FileExistsError(output)
    if not isinstance(source_commit, str) or not source_commit.strip():
        raise ValueError("source commit must be a non-empty string")
    files = []
    contents = {}
    for item in paths:
        relative = _safe_path(item)
        path = (root / Path(relative)).resolve()
        try:
            path.relative_to(root)
        except ValueError as error:
            raise ValueError(f"file is outside worktree: {item}") from error
        if not path.is_file():
            raise FileNotFoundError(path)
        data = path.read_bytes()
        if relative in contents:
            raise ValueError(f"duplicate bundle path: {relative}")
        contents[relative] = data
        files.append({"path": relative, "size": len(data), "sha256": _sha256(data)})
    if not files:
        raise ValueError("bundle needs at least one evidence file")
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "source_commit": source_commit,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": sorted(files, key=lambda item: item["path"]),
    }
    if source_session is not None:
        manifest["source_session"] = source_session
    manifest["bundle_id"] = _bundle_id(manifest)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "x", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", _json_bytes(manifest))
        for item in manifest["files"]:
            archive.writestr(item["path"], contents[item["path"]])
    return manifest


def _read_manifest(archive):
    names = archive.namelist()
    if len(names) != len(set(names)):
        raise ValueError("bundle contains duplicate paths")
    if "manifest.json" not in names:
        raise ValueError("bundle is missing manifest.json")
    manifest = json.loads(archive.read("manifest.json"))
    if not isinstance(manifest, dict) or manifest.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported bundle schema")
    if not isinstance(manifest.get("source_commit"), str) or not manifest["source_commit"].strip():
        raise ValueError("bundle source commit is missing")
    if manifest.get("bundle_id") != _bundle_id(manifest):
        raise ValueError("bundle_id does not match manifest")
    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        raise ValueError("bundle files must be a non-empty array")
    expected = set()
    for item in files:
        if not isinstance(item, dict):
            raise ValueError("bundle file entry must be an object")
        path = _safe_path(item.get("path"))
        if path in expected:
            raise ValueError(f"duplicate bundle path: {path}")
        expected.add(path)
        if not isinstance(item.get("size"), int) or isinstance(item["size"], bool) or item["size"] < 0:
            raise ValueError("bundle file size is invalid")
        if not isinstance(item.get("sha256"), str) or not _HASH.fullmatch(item["sha256"]):
            raise ValueError("bundle file sha256 is invalid")
    actual = set(names) - {"manifest.json"}
    if actual != expected:
        raise ValueError("bundle file list does not match archive")
    return manifest


def import_bundle(bundle, destination, expected_source_commit=None):
    """Import into the root represented by the bundle's relative file paths."""
    destination = Path(destination).resolve()
    if not isinstance(expected_source_commit, str) or not expected_source_commit.strip():
        raise ValueError("expected source commit is required")
    with zipfile.ZipFile(bundle) as archive:
        manifest = _read_manifest(archive)
        if manifest["source_commit"] != expected_source_commit:
            raise ValueError("bundle source commit does not match expected source commit")
        contents = {}
        for item in manifest["files"]:
            data = archive.read(item["path"])
            if len(data) != item["size"] or _sha256(data) != item["sha256"]:
                raise ValueError(f"bundle file sha256 mismatch: {item['path']}")
            contents[item["path"]] = data
    provenance = {
        "bundle_id": manifest["bundle_id"],
        "source_commit": manifest["source_commit"],
        "source_session": manifest.get("source_session"),
        "files": manifest["files"],
        "imported_at": datetime.now(timezone.utc).isoformat(),
    }
    provenance_path = destination / "handoff" / f"{manifest['bundle_id']}.json"
    targets = [destination / Path(path) for path in contents]
    if provenance_path.exists() or any(path.exists() for path in targets):
        raise FileExistsError("bundle destination already contains an imported file")
    for path in targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(contents[path.relative_to(destination).as_posix()])
    provenance_path.parent.mkdir(parents=True, exist_ok=True)
    provenance_path.write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
                               encoding="utf-8")
    return provenance
