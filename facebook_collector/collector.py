"""Synchronous public collection service."""

from datetime import datetime, timezone
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from facebook_collector.model import BatchValidationError, empty_outcome, run_serial, validate_batch
from facebook_collector.offline import (
    OfflineCaptureError,
    build_outcome,
    build_synthetic_outcome,
    load_offline_capture,
    offline_enabled,
)
from facebook_collector.storage import write_run
from facebook_collector.url_validation import UrlRejected, validate_public_url


class CollectionUnavailable(RuntimeError):
    """The requested path needs a collector slice that is not implemented yet."""


def _launch_browser():
    """Start one private synchronous Chromium browser for this invocation."""
    # Official API: https://playwright.dev/python/docs/library
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as error:
        raise CollectionUnavailable(
            "live collection requires Playwright; install playwright with: python -m pip install -r requirements.txt"
        ) from error

    runtime = sync_playwright().start()
    try:
        return runtime.chromium.launch(headless=True), runtime
    except Exception:
        runtime.stop()
        raise


def collect_posts(urls, output_dir, *, log=False) -> dict:
    """Collect an ordered batch and return the same document written to results.json."""
    if isinstance(urls, (str, bytes)):
        raise BatchValidationError("urls must be a collection of URL strings")
    inputs = list(urls)
    if not inputs:
        raise BatchValidationError("at least one URL is required")
    validate_batch(inputs)
    events = []
    offline_capture = None
    if offline_enabled():
        offline_capture = load_offline_capture(
            Path(os.environ["FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE"])
        )
    browser = runtime = None

    def collect_one(input_url: str, *, attempt_timeout_seconds: int) -> dict:
        nonlocal browser, runtime
        if offline_capture is not None:
            if input_url == offline_capture["submitted_url"]:
                return build_outcome(input_url, offline_capture)
            synthetic_outcome = offline_capture["synthetic_outcomes"].get(input_url)
            if synthetic_outcome is not None:
                return build_synthetic_outcome(
                    input_url,
                    synthetic_outcome,
                    attempt_timeout_seconds=attempt_timeout_seconds,
                )
        try:
            validate_public_url(input_url)
        except UrlRejected as error:
            return empty_outcome(input_url, 0, "invalid_input", error.reason)
        if offline_capture is not None:
            raise OfflineCaptureError("input URL does not match offline capture")
        if browser is None:
            browser, runtime = _launch_browser()
        from facebook_collector.playwright_adapter import collect_live_one

        return collect_live_one(
            input_url,
            attempt_timeout_seconds=attempt_timeout_seconds,
            browser=browser,
        )

    def record_event(event: str, outcome: dict, attempt: int | None, input_index: int) -> None:
        record = {
            "event_version": "1",
            "time": utc_now(),
            "feature": "facebook_post_collector",
            "event": event,
            "status": "stopped" if event == "stopped" else outcome.get("status"),
            "reason": "blocked" if event == "stopped" else outcome.get("reason"),
            "input_index": input_index,
        }
        family = _url_family(outcome.get("input_url"))
        if family is not None:
            record["url_family"] = family
        if attempt is not None:
            record["attempt"] = attempt
        if outcome.get("_event_http_status") is not None:
            record["http_status"] = outcome["_event_http_status"]
        events.append(record)

    try:
        outcomes, stop_reason = run_serial(
            inputs, collect_one, event_sink=record_event if log else None
        )
        run_status = "stopped" if stop_reason else "completed"
        return write_run(
            Path(output_dir), outcomes, run_status, stop_reason, events=events if log else None
        )
    finally:
        if browser is not None:
            browser.close()
        if runtime is not None:
            runtime.stop()


def utc_now() -> str:
    """Return a canonical UTC timestamp for a structured event."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _url_family(input_url: object) -> str | None:
    """Classify only the approved URL family, including the offline post fixture seam."""
    if not isinstance(input_url, str):
        return None
    try:
        return validate_public_url(input_url)["family"]
    except UrlRejected:
        try:
            path = urlsplit(input_url).path
        except ValueError:
            return None
        if re.fullmatch(r"/[0-9]+/posts/[0-9]+/?", path):
            return "post"
        return None
