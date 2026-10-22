"""Internal, deterministic offline capture seam used by the contract E2E test."""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from facebook_collector.model import (
    _IDENTITY_DIAGNOSTIC_REASONS,
    capture_status,
    empty_outcome,
)
from facebook_collector.storage import write_run
from facebook_collector.url_validation import UrlRejected, validate_public_url


FIXTURE_SCHEMA = "offline-observed-capture-v1"
COUNTER_NAMES = ("reaction", "comment", "share")
RFC3339_UTC_PATTERN = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?Z$"
)
FIXTURE_POST_PATH_PATTERN = re.compile(r"^/[0-9]+/posts/[0-9]+/?$")
IDENTITY_FIELDS_BY_KIND = {
    "post": ("post_id", "owner_id"),
    "photo": ("photo_id",),
    "pfbid": ("route",),
    "group": ("group_id", "post_id"),
}
TEXT_STATUSES = {"candidate_text_unverified", "preview_only", "missing"}
SYNTHETIC_TERMINAL_STATUSES = {"timeout", "error", "blocked"}


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
        parsed.scheme == "https"
        and parsed.netloc == "www.facebook.com"
        and not parsed.query
        and not parsed.fragment
        and FIXTURE_POST_PATH_PATTERN.fullmatch(parsed.path)
    ):
        return url
    try:
        validate_public_url(url)
    except UrlRejected as error:
        raise OfflineCaptureError(f"{name} must use the approved fixture post route") from error
    return url


def _validated_identity(value: object) -> dict:
    identity = _required_mapping(value, "validated_identity")
    kind = identity.get("kind")
    required = IDENTITY_FIELDS_BY_KIND.get(kind)
    if required is None:
        raise OfflineCaptureError("validated_identity.kind is not supported")
    normalized = {"kind": kind}
    for field in required:
        normalized[field] = _required_string(identity.get(field), f"validated_identity.{field}")
    return normalized


def _candidate_text(value: object) -> dict:
    candidate_text = _required_mapping(value, "candidate_text")
    status = candidate_text.get("status", "candidate_text_unverified")
    if status not in TEXT_STATUSES:
        raise OfflineCaptureError("candidate_text.status is not supported")
    text_value = candidate_text.get("value")
    source = candidate_text.get("source")
    if status == "candidate_text_unverified":
        return {
            "value": _required_string(text_value, "candidate_text.value"),
            "status": status,
            "source": _required_string(source, "candidate_text.source"),
        }
    if text_value is not None and not isinstance(text_value, str):
        raise OfflineCaptureError("candidate_text.value must be a string or null")
    if source is not None and not isinstance(source, str):
        raise OfflineCaptureError("candidate_text.source must be a string or null")
    return {"value": text_value, "status": status, "source": source}


def _engagement(value: object) -> dict:
    engagement = _required_mapping(value, "engagement")
    if set(engagement) != set(COUNTER_NAMES):
        raise OfflineCaptureError("engagement must contain exactly reaction, comment, and share")
    normalized = {}
    for name in COUNTER_NAMES:
        metric = _required_mapping(engagement[name], f"engagement.{name}")
        observed_value = metric.get("observed_value")
        quality = metric.get("quality")
        if observed_value is None:
            if quality not in {"missing", "unverified"}:
                raise OfflineCaptureError(f"engagement.{name}.quality must match a null value")
            raw = metric.get("raw")
            source = metric.get("source")
            if raw is not None and not isinstance(raw, str):
                raise OfflineCaptureError(f"engagement.{name}.raw must be a string or null")
            if source is not None and not isinstance(source, str):
                raise OfflineCaptureError(f"engagement.{name}.source must be a string or null")
        else:
            if not isinstance(observed_value, int) or isinstance(observed_value, bool) or observed_value < 0:
                raise OfflineCaptureError(f"engagement.{name}.observed_value must be a nonnegative integer")
            if quality not in {"exact", "approximate"}:
                raise OfflineCaptureError(f"engagement.{name}.quality must be exact or approximate")
            raw = _required_string(metric.get("raw"), f"engagement.{name}.raw", nonempty=False)
            source = _required_string(metric.get("source"), f"engagement.{name}.source")
        normalized[name] = {
            "observed_value": observed_value,
            "raw": raw,
            "quality": quality,
            "source": source,
        }
    return normalized


def _synthetic_outcome(value: object) -> dict | None:
    if value is None:
        return None
    outcome = _required_mapping(value, "outcome")
    status = outcome.get("status")
    if status not in SYNTHETIC_TERMINAL_STATUSES:
        raise OfflineCaptureError("outcome.status is not supported")
    reason = outcome.get("reason")
    if reason is not None and not isinstance(reason, str):
        raise OfflineCaptureError("outcome.reason must be a string or null")
    return {"status": status, "reason": reason}


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
        if status not in {
            "identity_unverified",
            "blocked",
            "timeout",
            "http",
            "challenge",
            "login_wall",
        }:
            raise OfflineCaptureError(
                f"synthetic_outcomes[{index}].status is not supported"
            )
        if submitted_url in normalized_synthetic_outcomes:
            raise OfflineCaptureError("synthetic_outcomes must not repeat submitted_url")
        normalized = {"status": status}
        if status == "identity_unverified" and outcome.get("identity_reason") is not None:
            identity_reason = outcome["identity_reason"]
            if identity_reason not in _IDENTITY_DIAGNOSTIC_REASONS:
                raise OfflineCaptureError(
                    f"synthetic_outcomes[{index}].identity_reason is not supported"
                )
            normalized["identity_reason"] = identity_reason
        if status == "http":
            http_status = outcome.get("http_status")
            if (
                not isinstance(http_status, int)
                or isinstance(http_status, bool)
                or not 100 <= http_status <= 599
            ):
                raise OfflineCaptureError(
                    f"synthetic_outcomes[{index}].http_status must be an HTTP status"
                )
            normalized["http_status"] = http_status
        normalized_synthetic_outcomes[submitted_url] = normalized

    submitted_url = _fixture_post_url(capture.get("submitted_url"), "submitted_url")
    if submitted_url in normalized_synthetic_outcomes:
        raise OfflineCaptureError("synthetic_outcomes must not repeat observed_capture submitted_url")
    return {
        "submitted_url": submitted_url,
        "resolved_url": _fixture_post_url(capture.get("resolved_url"), "resolved_url"),
        "validated_identity": _validated_identity(capture.get("validated_identity")),
        "captured_at": _utc_rfc3339(capture.get("captured_at")),
        "candidate_text": _candidate_text(capture.get("candidate_text")),
        "engagement": _engagement(capture.get("engagement")),
        "synthetic_outcomes": normalized_synthetic_outcomes,
        "outcome": _synthetic_outcome(capture.get("outcome")),
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
        "status": capture["candidate_text"]["status"],
        "source": capture["candidate_text"]["source"],
    }
    synthetic_outcome = capture["outcome"]
    status = synthetic_outcome["status"] if synthetic_outcome else capture_status(text, counters)
    reason = synthetic_outcome["reason"] if synthetic_outcome else None
    return {
        "input_index": 0,
        "duplicate_of": None,
        "input_url": input_url,
        "resolved_url": capture["resolved_url"],
        "post_identity": capture["validated_identity"],
        "attempted_at": utc_now(),
        "collected_at": capture["captured_at"],
        "status": status,
        "reason": reason,
        "text": text,
        "counters": counters,
        "latest_updated": False,
    }


def build_synthetic_outcome(
    input_url: str, outcome: dict, *, attempt_timeout_seconds: int
) -> dict:
    """Build a complete offline item-error envelope after a synthetic attempt."""
    if attempt_timeout_seconds != 30:
        raise OfflineCaptureError("synthetic attempts require a 30-second timeout")
    status = outcome["status"]
    if status == "identity_unverified":
        result = empty_outcome(input_url, 0, "error", status)
        identity_reason = outcome.get("identity_reason")
        if identity_reason is not None:
            if identity_reason not in _IDENTITY_DIAGNOSTIC_REASONS:
                raise OfflineCaptureError("unsupported identity diagnostic reason")
            result["_event_identity_reason"] = identity_reason
    elif status in {"blocked", "challenge", "login_wall"}:
        result = empty_outcome(input_url, 0, "blocked", "blocked")
    elif status == "timeout":
        result = empty_outcome(input_url, 0, "timeout", "transport_timeout")
        result["_retryable"] = True
    elif status == "http":
        http_status = outcome["http_status"]
        if http_status in {401, 403, 429}:
            result = empty_outcome(input_url, 0, "blocked", "blocked")
        elif http_status in {404, 410}:
            result = empty_outcome(input_url, 0, "error", "post_unavailable")
        elif http_status in {408, 504}:
            result = empty_outcome(input_url, 0, "timeout", "transport_timeout")
            result["_retryable"] = True
        elif 500 <= http_status <= 503 or http_status >= 505:
            result = empty_outcome(input_url, 0, "error", "facebook_server_error")
        else:
            result = empty_outcome(input_url, 0, "error", "http_error")
        result["_event_http_status"] = http_status
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
