"""Internal, deterministic offline capture seam used by the contract E2E test."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from facebook_collector.model import capture_status, empty_outcome
from facebook_collector.storage import write_run


FIXTURE_SCHEMA = "offline-observed-capture-v1"
COUNTER_NAMES = ("reaction", "comment", "share")
RFC3339_UTC_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$"
)
FIXTURE_POST_PATH_PATTERN = re.compile(r"^/[0-9]+/posts/[0-9]+/?$")


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

    synthetic_outcomes = document.get("synthetic_outcomes", [])
    if not isinstance(synthetic_outcomes, list):
        raise OfflineCaptureError("synthetic_outcomes must be a list")
    normalized_synthetic_outcomes = {}
    for index, outcome in enumerate(synthetic_outcomes):
        outcome = _required_mapping(outcome, f"synthetic_outcomes[{index}]")
        submitted_url = _fixture_post_url(
            outcome.get("submitted_url"), f"synthetic_outcomes[{index}].submitted_url"
        )
        status = outcome.get("status")
        if status not in {"identity_unverified", "blocked"}:
            raise OfflineCaptureError(
                f"synthetic_outcomes[{index}].status must be identity_unverified or blocked"
            )
        if submitted_url in normalized_synthetic_outcomes:
            raise OfflineCaptureError("synthetic_outcomes must not repeat submitted_url")
        normalized_synthetic_outcomes[submitted_url] = status

    submitted_url = _fixture_post_url(capture.get("submitted_url"), "submitted_url")
    if submitted_url in normalized_synthetic_outcomes:
        raise OfflineCaptureError("synthetic_outcomes must not repeat observed_capture submitted_url")
    return {
        "submitted_url": submitted_url,
        "resolved_url": _fixture_post_url(capture.get("resolved_url"), "resolved_url"),
        "validated_identity": validated_identity,
        "captured_at": _utc_rfc3339(capture.get("captured_at")),
        "candidate_text": normalized_text,
        "engagement": normalized_engagement,
        "synthetic_outcomes": normalized_synthetic_outcomes,
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
        "input_index": 0,
        "duplicate_of": None,
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


def build_synthetic_outcome(input_url: str, outcome: str) -> dict:
    """Build a complete offline item-error envelope after a synthetic attempt."""
    if outcome == "identity_unverified":
        result = empty_outcome(input_url, 0, "error", outcome)
    elif outcome == "blocked":
        result = empty_outcome(input_url, 0, outcome, outcome)
    else:
        raise OfflineCaptureError("unsupported synthetic outcome")
    result["attempted_at"] = utc_now()
    return result


def write_offline_run(output_dir: Path, outcome: dict) -> Path:
    """Write one offline capture through the versioned collector storage path."""
    try:
        results = write_run(output_dir, [outcome], "completed", None)
    except (OSError, TypeError, ValueError) as error:
        raise OfflineCaptureError("cannot write offline run output") from error
    return output_dir / "runs" / results["run_id"]
