"""Load and migrate the hash-only baseline used by repeat runs."""

import hashlib
import json
import re
from pathlib import Path

from probe_post import validate_url

SCHEMA_VERSION = 1
_HASH = re.compile(r"^[0-9a-f]{64}$")
_REQUIRED_REVIEW = ("normalized_text_sha256", "reviewed_at", "evidence")


def normalize_text(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text must be a non-empty string")
    return " ".join(text.split())


def text_sha256(text):
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def _required_string(row, field):
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"baseline {field} must be a non-empty string")
    return value


def _validate_sample(sample):
    if not isinstance(sample, dict):
        raise ValueError("baseline sample must be an object")
    if "text" in sample:
        raise ValueError("baseline must not contain raw text")
    sample_id = _required_string(sample, "sample_id")
    _required_string(sample, "publisher")
    input_url = _required_string(sample, "input_url")
    fetch_url = _required_string(sample, "fetch_url")
    validate_url(input_url)
    validate_url(fetch_url)
    review = sample.get("review")
    if not isinstance(review, dict):
        raise ValueError("baseline review must be an object")
    if "text" in review:
        raise ValueError("baseline review must not contain raw text")
    for field in _REQUIRED_REVIEW:
        _required_string(review, field)
    digest = review["normalized_text_sha256"]
    if not _HASH.fullmatch(digest):
        raise ValueError("baseline normalized_text_sha256 must be a SHA-256 hex digest")
    return {
        "sample_id": sample_id,
        "publisher": sample["publisher"],
        "input_url": input_url,
        "fetch_url": fetch_url,
        "review": {
            "text_sha256": digest,
            "normalized_text_sha256": digest,
            "reviewed_at": review["reviewed_at"],
            "evidence": review["evidence"],
            **({"method": review["method"]} if isinstance(review.get("method"), str) else {}),
        },
    }


def validate_baseline(baseline):
    if not isinstance(baseline, dict):
        raise ValueError("baseline must be an object")
    if baseline.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"baseline schema_version must be {SCHEMA_VERSION}")
    samples = baseline.get("samples")
    if not isinstance(samples, list) or not samples:
        raise ValueError("baseline samples must be a non-empty array")
    references = [_validate_sample(sample) for sample in samples]
    ids = [reference["sample_id"] for reference in references]
    if len(ids) != len(set(ids)):
        raise ValueError("baseline sample_id values must be unique")
    return references


def load_baseline(path):
    baseline = json.loads(Path(path).read_text(encoding="utf-8"))
    return validate_baseline(baseline)


def migrate_legacy(legacy):
    if not isinstance(legacy, list) or not legacy:
        raise ValueError("legacy references must be a non-empty array")
    samples = []
    for reference in legacy:
        if not isinstance(reference, dict) or not isinstance(reference.get("text"), str):
            raise ValueError("legacy reference must contain raw text")
        old_review = reference.get("review")
        if not isinstance(old_review, dict):
            raise ValueError("legacy reference review must be an object")
        review = {
            "normalized_text_sha256": text_sha256(reference["text"]),
            "reviewed_at": _required_string(old_review, "reviewed_at"),
            "evidence": _required_string(old_review, "evidence"),
        }
        if isinstance(old_review.get("method"), str) and old_review["method"].strip():
            review["method"] = old_review["method"]
        samples.append({
            "sample_id": _required_string(reference, "sample_id"),
            "publisher": _required_string(reference, "publisher"),
            "input_url": _required_string(reference, "input_url"),
            "fetch_url": _required_string(reference, "fetch_url"),
            "review": review,
        })
    baseline = {"schema_version": SCHEMA_VERSION, "samples": samples}
    validate_baseline(baseline)
    return baseline
