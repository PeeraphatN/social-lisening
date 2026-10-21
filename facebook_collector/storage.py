"""Version-1 artifact and latest-store persistence for collector outcomes."""

from copy import deepcopy
import csv
import json
import os
from pathlib import Path
import re
import tempfile
import uuid


SCHEMA_VERSION = "1"
CSV_FIELDS = (
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
)
COUNTER_NAMES = ("reaction", "comment", "share")
LATEST_STATUSES = {"collected", "partial"}
COUNTER_QUALITIES = {"exact", "approximate", "unverified", "missing"}


def _identity_key(identity: dict) -> str:
    return json.dumps(identity, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _identity_columns(identity: object) -> dict[str, str]:
    columns = {
        "identity_kind": "",
        "identity_post_id": "",
        "identity_owner_id": "",
        "identity_photo_id": "",
        "identity_group_id": "",
        "identity_route": "",
    }
    if not isinstance(identity, dict):
        return columns
    kind = identity.get("kind")
    columns["identity_kind"] = kind if isinstance(kind, str) else ""
    if kind == "post":
        columns["identity_post_id"] = _cell(identity.get("post_id"))
        columns["identity_owner_id"] = _cell(identity.get("owner_id"))
    elif kind == "photo":
        columns["identity_photo_id"] = _cell(identity.get("photo_id"))
    elif kind == "pfbid":
        columns["identity_route"] = _cell(identity.get("route"))
    elif kind == "group":
        columns["identity_post_id"] = _cell(identity.get("post_id"))
        columns["identity_group_id"] = _cell(identity.get("group_id"))
    return columns


def _cell(value: object) -> str | int:
    return "" if value is None else value  # csv accepts integers without changing their meaning


def _outcome_to_row(outcome: dict) -> dict:
    text = outcome.get("text") if isinstance(outcome.get("text"), dict) else {}
    counters = outcome.get("counters") if isinstance(outcome.get("counters"), dict) else {}
    row = {
        "schema_version": SCHEMA_VERSION,
        "input_index": _cell(outcome.get("input_index")),
        "duplicate_of": _cell(outcome.get("duplicate_of")),
        "input_url": _cell(outcome.get("input_url")),
        "resolved_url": _cell(outcome.get("resolved_url")),
        **_identity_columns(outcome.get("post_identity")),
        "attempted_at": _cell(outcome.get("attempted_at")),
        "collected_at": _cell(outcome.get("collected_at")),
        "status": _cell(outcome.get("status")),
        "reason": _cell(outcome.get("reason")),
        "text_value": _cell(text.get("value")),
        "text_status": _cell(text.get("status")),
        "text_source": _cell(text.get("source")),
        "latest_updated": str(bool(outcome.get("latest_updated"))).lower(),
    }
    for name in COUNTER_NAMES:
        counter = counters.get(name) if isinstance(counters.get(name), dict) else {}
        row.update(
            {
                f"{name}_value": _cell(counter.get("value")),
                f"{name}_raw": _cell(counter.get("raw")),
                f"{name}_quality": _cell(counter.get("quality")),
                f"{name}_source": _cell(counter.get("source")),
            }
        )
    return row


def _valid_identity(identity: object) -> bool:
    if not isinstance(identity, dict):
        return False
    kind = identity.get("kind")
    required_by_kind = {
        "post": ("post_id", "owner_id"),
        "photo": ("photo_id",),
        "pfbid": ("route",),
        "group": ("group_id", "post_id"),
    }
    required = required_by_kind.get(kind)
    return required is not None and all(
        isinstance(identity.get(name), str) and identity[name] for name in required
    )


def _is_latest_eligible(outcome: dict) -> bool:
    text = outcome.get("text")
    return (
        outcome.get("duplicate_of") is None
        and outcome.get("status") in LATEST_STATUSES
        and _valid_identity(outcome.get("post_identity"))
        and isinstance(text, dict)
        and text.get("status") == "candidate_text_unverified"
        and bool(outcome.get("collected_at"))
    )


def _required_string(value: object, name: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise ValueError(f"malformed posts-latest.csv: {name}")
    return value


def _optional_string(value: object, name: str) -> str | None:
    value = _required_string(value, name, allow_empty=True)
    return value or None


def _parse_index(value: object, name: str, *, optional: bool = False) -> int | None:
    if optional and value == "":
        return None
    value = _required_string(value, name)
    if not re.fullmatch(r"[0-9]+", value):
        raise ValueError(f"malformed posts-latest.csv: {name}")
    return int(value)


def _identity_from_row(row: dict) -> dict:
    kind = _required_string(row["identity_kind"], "identity_kind")
    values = {
        "post_id": row["identity_post_id"],
        "owner_id": row["identity_owner_id"],
        "photo_id": row["identity_photo_id"],
        "group_id": row["identity_group_id"],
        "route": row["identity_route"],
    }
    required_by_kind = {
        "post": ("post_id", "owner_id"),
        "photo": ("photo_id",),
        "pfbid": ("route",),
        "group": ("group_id", "post_id"),
    }
    required = required_by_kind.get(kind)
    if required is None:
        raise ValueError("malformed posts-latest.csv: identity_kind")
    if any(values[name] != "" for name in set(values) - set(required)):
        raise ValueError("malformed posts-latest.csv: route-specific identity")
    identity = {"kind": kind}
    identity.update({name: _required_string(values[name], f"identity_{name}") for name in required})
    return identity


def _outcome_from_row(row: dict) -> dict:
    if row.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("malformed posts-latest.csv: schema_version")
    identity = _identity_from_row(row)
    status = _required_string(row["status"], "status")
    if status not in LATEST_STATUSES:
        raise ValueError("malformed posts-latest.csv: status")
    text_status = _required_string(row["text_status"], "text_status")
    if text_status != "candidate_text_unverified":
        raise ValueError("malformed posts-latest.csv: text_status")
    latest_updated = _required_string(row["latest_updated"], "latest_updated")
    if latest_updated not in {"true", "false"}:
        raise ValueError("malformed posts-latest.csv: latest_updated")
    counters = {}
    for name in COUNTER_NAMES:
        value = row[f"{name}_value"]
        if value == "":
            parsed_value = None
        elif re.fullmatch(r"[0-9]+", value or ""):
            parsed_value = int(value)
        else:
            raise ValueError(f"malformed posts-latest.csv: {name}_value")
        quality = _required_string(row[f"{name}_quality"], f"{name}_quality")
        if quality not in COUNTER_QUALITIES:
            raise ValueError(f"malformed posts-latest.csv: {name}_quality")
        counters[name] = {
            "value": parsed_value,
            "raw": _optional_string(row[f"{name}_raw"], f"{name}_raw"),
            "quality": quality,
            "source": _optional_string(row[f"{name}_source"], f"{name}_source"),
        }
    return {
        "input_index": _parse_index(row["input_index"], "input_index"),
        "duplicate_of": _parse_index(row["duplicate_of"], "duplicate_of", optional=True),
        "input_url": _required_string(row["input_url"], "input_url"),
        "resolved_url": _required_string(row["resolved_url"], "resolved_url"),
        "post_identity": identity,
        "attempted_at": _required_string(row["attempted_at"], "attempted_at"),
        "collected_at": _required_string(row["collected_at"], "collected_at"),
        "status": status,
        "reason": _optional_string(row["reason"], "reason"),
        "text": {
            "value": _optional_string(row["text_value"], "text_value"),
            "status": text_status,
            "source": _required_string(row["text_source"], "text_source"),
        },
        "counters": counters,
        "latest_updated": latest_updated == "true",
    }


def read_latest(path: Path) -> dict:
    """Read a validated latest CSV keyed by canonical compact identity JSON."""
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames != list(CSV_FIELDS):
                raise ValueError("malformed posts-latest.csv: header")
            records = {}
            for row in reader:
                if None in row or set(row) != set(CSV_FIELDS):
                    raise ValueError("malformed posts-latest.csv: row shape")
                outcome = _outcome_from_row(row)
                key = _identity_key(outcome["post_identity"])
                if key in records:
                    raise ValueError("malformed posts-latest.csv: duplicate identity")
                records[key] = outcome
            return records
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        raise ValueError("cannot read posts-latest.csv") from error


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
            writer.writerows(_outcome_to_row(outcome) for outcome in outcomes)
        os.replace(temporary_name, path)
    except OSError:
        if temporary_name:
            Path(temporary_name).unlink(missing_ok=True)
        raise


def _remove_run_artifacts(run_directory: Path) -> None:
    (run_directory / "results.json").unlink(missing_ok=True)
    (run_directory / "posts.csv").unlink(missing_ok=True)
    run_directory.rmdir()


def write_run(
    output_dir: Path,
    outcomes: list[dict],
    run_status: str,
    stop_reason: str | None,
    *,
    run_id: str | None = None,
) -> dict:
    """Write version-1 run artifacts and safely update the identity-keyed latest store."""
    stored_outcomes = deepcopy(outcomes)
    latest_candidates = [outcome for outcome in stored_outcomes if _is_latest_eligible(outcome)]
    latest_path = output_dir / "posts-latest.csv"
    latest = read_latest(latest_path) if latest_candidates else {}
    changed_latest = False
    for outcome in stored_outcomes:
        outcome["latest_updated"] = False
        if _is_latest_eligible(outcome):
            key = _identity_key(outcome["post_identity"])
            latest[key] = deepcopy(outcome)
            latest[key]["latest_updated"] = True
            outcome["latest_updated"] = True
            changed_latest = True

    run_id = uuid.uuid4().hex if run_id is None else run_id
    results = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "run_status": run_status,
        "stop_reason": stop_reason,
        "outcomes": stored_outcomes,
    }
    run_directory = output_dir / "runs" / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    try:
        (run_directory / "results.json").write_text(
            json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        _write_csv_atomically(run_directory / "posts.csv", stored_outcomes)
    except (OSError, TypeError, ValueError):
        _remove_run_artifacts(run_directory)
        raise
    try:
        if changed_latest or not latest_path.exists():
            _write_csv_atomically(latest_path, list(latest.values()))
    except (OSError, TypeError, ValueError):
        _remove_run_artifacts(run_directory)
        raise
    return results
