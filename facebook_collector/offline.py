"""Internal, deterministic offline capture seam used by the contract E2E test."""

import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tempfile
import uuid
from urllib.parse import urlsplit

from facebook_collector.model import capture_status, update_latest


FIXTURE_SCHEMA = "offline-observed-capture-v1"
COUNTER_NAMES = ("reaction", "comment", "share")
COUNTER_QUALITIES = {"exact", "approximate", "unverified"}
LATEST_STATUSES = {"collected", "partial"}
TEXT_STATUSES = {"candidate_text_unverified"}
RFC3339_UTC_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$"
)
FIXTURE_POST_PATH_PATTERN = re.compile(r"^/[0-9]+/posts/[0-9]+/?$")
CSV_FIELDS = (
    "identity_kind",
    "identity_post_id",
    "identity_owner_id",
    "input_url",
    "resolved_url",
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
)


class OfflineCaptureError(ValueError):
    """An untrusted capture does not satisfy the internal seam contract."""


def offline_enabled(environment: dict | None = None) -> bool:
    """Return whether the explicitly opt-in offline seam is active."""
    environment = os.environ if environment is None else environment
    return bool(environment.get("FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE")) and (
        environment.get("FACEBOOK_COLLECTOR_NETWORK_DISABLED") == "1"
    )


def _required_string(value: object, name: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value):
        raise OfflineCaptureError(f"{name} must be a {'nonempty ' if nonempty else ''}string")
    return value


def _required_mapping(value: object, name: str) -> dict:
    if not isinstance(value, dict):
        raise OfflineCaptureError(f"{name} must be an object")
    return value


def _utc_rfc3339(value: object, name: str = "captured_at") -> str:
    timestamp = _required_string(value, name)
    if not RFC3339_UTC_PATTERN.fullmatch(timestamp):
        raise OfflineCaptureError(f"{name} must be UTC RFC3339")
    try:
        parsed = datetime.fromisoformat(timestamp[:-1] + "+00:00")
    except ValueError as error:
        raise OfflineCaptureError(f"{name} must be UTC RFC3339") from error
    if parsed.tzinfo != timezone.utc or parsed.utcoffset() is None:
        raise OfflineCaptureError(f"{name} must be UTC RFC3339")
    return timestamp


def _fixture_post_url(value: object, name: str) -> str:
    url = _required_string(value, name)
    try:
        parsed = urlsplit(url)
    except ValueError as error:
        raise OfflineCaptureError(f"{name} must use the approved fixture post route") from error
    if (
        parsed.scheme != "https"
        or parsed.netloc != "www.facebook.com"
        or parsed.query
        or parsed.fragment
        or not FIXTURE_POST_PATH_PATTERN.fullmatch(parsed.path)
    ):
        raise OfflineCaptureError(f"{name} must use the approved fixture post route")
    return url


def load_offline_capture(path: Path) -> dict:
    """Load and normalize exactly one trusted-after-validation capture."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise OfflineCaptureError("cannot read offline capture") from error

    document = _required_mapping(document, "fixture")
    if document.get("fixture_schema") != FIXTURE_SCHEMA:
        raise OfflineCaptureError("fixture_schema is not supported")
    capture = _required_mapping(document.get("observed_capture"), "observed_capture")

    identity = _required_mapping(capture.get("validated_identity"), "validated_identity")
    if identity.get("kind") != "post":
        raise OfflineCaptureError("validated_identity.kind must be post")
    validated_identity = {
        "kind": "post",
        "post_id": _required_string(identity.get("post_id"), "validated_identity.post_id"),
        "owner_id": _required_string(identity.get("owner_id"), "validated_identity.owner_id"),
    }

    candidate_text = _required_mapping(capture.get("candidate_text"), "candidate_text")
    normalized_text = {
        "value": _required_string(candidate_text.get("value"), "candidate_text.value"),
        "source": _required_string(candidate_text.get("source"), "candidate_text.source"),
    }

    engagement = _required_mapping(capture.get("engagement"), "engagement")
    if set(engagement) != set(COUNTER_NAMES):
        raise OfflineCaptureError("engagement must contain exactly reaction, comment, and share")
    normalized_engagement = {}
    for name in COUNTER_NAMES:
        metric = _required_mapping(engagement[name], f"engagement.{name}")
        value = metric.get("observed_value")
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise OfflineCaptureError(f"engagement.{name}.observed_value must be a nonnegative integer")
        quality = metric.get("quality")
        if quality not in {"exact", "approximate"}:
            raise OfflineCaptureError(f"engagement.{name}.quality must be exact or approximate")
        normalized_engagement[name] = {
            "observed_value": value,
            "raw": _required_string(metric.get("raw"), f"engagement.{name}.raw", nonempty=False),
            "quality": quality,
            "source": _required_string(metric.get("source"), f"engagement.{name}.source"),
        }

    return {
        "submitted_url": _fixture_post_url(capture.get("submitted_url"), "submitted_url"),
        "resolved_url": _fixture_post_url(capture.get("resolved_url"), "resolved_url"),
        "validated_identity": validated_identity,
        "captured_at": _utc_rfc3339(capture.get("captured_at")),
        "candidate_text": normalized_text,
        "engagement": normalized_engagement,
    }


def utc_now() -> str:
    """Return an RFC3339 UTC timestamp for the collection attempt."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def build_outcome(input_url: str, capture: dict) -> dict:
    """Make the contracted outcome from a normalized offline capture."""
    if input_url != capture["submitted_url"]:
        raise OfflineCaptureError("input URL does not match capture submitted_url")
    counters = {
        name: {
            "value": capture["engagement"][name]["observed_value"],
            "raw": capture["engagement"][name]["raw"],
            "quality": capture["engagement"][name]["quality"],
            "source": capture["engagement"][name]["source"],
        }
        for name in COUNTER_NAMES
    }
    text = {
        "value": capture["candidate_text"]["value"],
        "status": "candidate_text_unverified",
        "source": capture["candidate_text"]["source"],
    }
    return {
        "input_url": input_url,
        "resolved_url": capture["resolved_url"],
        "post_identity": capture["validated_identity"],
        "attempted_at": utc_now(),
        "collected_at": capture["captured_at"],
        "status": capture_status(text, counters),
        "reason": None,
        "text": text,
        "counters": counters,
        "latest_updated": False,
    }


def _value_for_csv(value: object) -> str | int:
    return "" if value is None else value


def outcome_to_row(outcome: dict) -> dict:
    """Flatten one outcome without losing identity, text, or counter semantics."""
    identity = outcome["post_identity"]
    row = {
        "identity_kind": identity["kind"],
        "identity_post_id": identity["post_id"],
        "identity_owner_id": identity["owner_id"],
        "input_url": outcome["input_url"],
        "resolved_url": outcome["resolved_url"],
        "attempted_at": outcome["attempted_at"],
        "collected_at": outcome["collected_at"],
        "status": outcome["status"],
        "reason": _value_for_csv(outcome["reason"]),
        "text_value": outcome["text"]["value"],
        "text_status": outcome["text"]["status"],
        "text_source": outcome["text"]["source"],
        "latest_updated": str(outcome["latest_updated"]).lower(),
    }
    for name in COUNTER_NAMES:
        metric = outcome["counters"][name]
        row[f"{name}_value"] = _value_for_csv(metric["value"])
        row[f"{name}_raw"] = _value_for_csv(metric["raw"])
        row[f"{name}_quality"] = metric["quality"]
        row[f"{name}_source"] = metric["source"]
    return row


def _identity_key(identity: dict) -> str:
    return json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _row_to_outcome(row: dict) -> dict:
    if any(name not in row for name in CSV_FIELDS):
        raise OfflineCaptureError("existing posts-latest.csv has an unsupported schema")
    identity = {
        "kind": _required_string(row["identity_kind"], "existing identity_kind"),
        "post_id": _required_string(row["identity_post_id"], "existing identity_post_id"),
        "owner_id": _required_string(row["identity_owner_id"], "existing identity_owner_id"),
    }
    if identity["kind"] != "post":
        raise OfflineCaptureError("existing identity_kind must be post")
    input_url = _required_string(row["input_url"], "existing input_url")
    resolved_url = _required_string(row["resolved_url"], "existing resolved_url")
    attempted_at = _utc_rfc3339(row["attempted_at"], "existing attempted_at")
    collected_at = _utc_rfc3339(row["collected_at"], "existing collected_at")
    status = row["status"]
    if status not in LATEST_STATUSES:
        raise OfflineCaptureError("existing status is invalid")
    text_status = row["text_status"]
    if text_status not in TEXT_STATUSES:
        raise OfflineCaptureError("existing text_status is invalid")
    text_value = _required_string(row["text_value"], "existing text_value")
    text_source = _required_string(row["text_source"], "existing text_source")
    latest_updated = row["latest_updated"]
    if latest_updated not in {"true", "false"}:
        raise OfflineCaptureError("existing latest_updated is invalid")
    counters = {}
    for name in COUNTER_NAMES:
        value = row[f"{name}_value"]
        if value == "":
            parsed_value = None
        elif not isinstance(value, str) or not re.fullmatch(r"[0-9]+", value):
            raise OfflineCaptureError("existing posts-latest.csv has an invalid counter")
        else:
            parsed_value = int(value)
        quality = row[f"{name}_quality"]
        if quality not in COUNTER_QUALITIES:
            raise OfflineCaptureError("existing posts-latest.csv has an invalid counter quality")
        counters[name] = {
            "value": parsed_value,
            "raw": None if row[f"{name}_raw"] == "" else row[f"{name}_raw"],
            "quality": quality,
            "source": _required_string(row[f"{name}_source"], f"existing {name}_source"),
        }
    return {
        "input_url": input_url,
        "resolved_url": resolved_url,
        "post_identity": identity,
        "attempted_at": attempted_at,
        "collected_at": collected_at,
        "status": status,
        "reason": None if row["reason"] == "" else row["reason"],
        "text": {
            "value": text_value,
            "status": text_status,
            "source": text_source,
        },
        "counters": counters,
        "latest_updated": latest_updated == "true",
    }


def read_latest_rows(path: Path) -> dict:
    """Read a collector-generated latest CSV, rejecting malformed input safely."""
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise OfflineCaptureError("existing posts-latest.csv has no header")
            if reader.fieldnames != list(CSV_FIELDS):
                raise OfflineCaptureError("existing posts-latest.csv has an unsupported schema")
            records = {}
            for row in reader:
                outcome = _row_to_outcome(row)
                key = _identity_key(outcome["post_identity"])
                if key in records:
                    raise OfflineCaptureError("existing posts-latest.csv has duplicate identities")
                records[key] = outcome
            return records
    except (OSError, csv.Error) as error:
        raise OfflineCaptureError("cannot read existing posts-latest.csv") from error


def _write_csv_atomically(path: Path, outcomes: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="", delete=False, dir=path.parent
        ) as temporary:
            temporary_name = temporary.name
            writer = csv.DictWriter(temporary, fieldnames=CSV_FIELDS)
            writer.writeheader()
            writer.writerows(outcome_to_row(outcome) for outcome in outcomes)
        os.replace(temporary_name, path)
    except OSError as error:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
        raise OfflineCaptureError(f"cannot write {path.name}") from error


def write_latest(path: Path, outcome: dict) -> bool:
    """Atomically replace one eligible latest record while retaining other identities."""
    existing = read_latest_rows(path)
    updated, latest_updated = update_latest(existing, outcome)
    if not latest_updated:
        return False
    for record in updated.values():
        if record.get("post_identity") == outcome["post_identity"]:
            record["latest_updated"] = True
            break
    _write_csv_atomically(path, list(updated.values()))
    return True


def write_offline_run(output_dir: Path, outcome: dict) -> Path:
    """Write latest and the per-run artifacts for a completed one-item offline run."""
    outcome["latest_updated"] = write_latest(output_dir / "posts-latest.csv", outcome)
    if not outcome["latest_updated"]:
        raise OfflineCaptureError("capture is not eligible for latest output")

    run_id = uuid.uuid4().hex
    run_directory = output_dir / "runs" / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    try:
        results = {
            "schema_version": "1",
            "run_status": "completed",
            "stop_reason": None,
            "outcomes": [outcome],
        }
        (run_directory / "results.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        _write_csv_atomically(run_directory / "posts.csv", [outcome])
    except (OSError, TypeError, ValueError) as error:
        raise OfflineCaptureError("cannot write offline run output") from error
    return run_directory
