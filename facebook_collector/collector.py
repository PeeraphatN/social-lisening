"""Synchronous public collection service."""

import os
from pathlib import Path

from facebook_collector.model import BatchValidationError, empty_outcome, run_serial
from facebook_collector.offline import build_outcome, load_offline_capture, offline_enabled
from facebook_collector.storage import write_run
from facebook_collector.url_validation import UrlRejected, validate_public_url


class CollectionUnavailable(RuntimeError):
    """The requested path needs a collector slice that is not implemented yet."""


def collect_posts(urls, output_dir, *, log=False) -> dict:
    """Collect an ordered batch and return the same document written to results.json."""
    if isinstance(urls, (str, bytes)):
        raise BatchValidationError("urls must be a collection of URL strings")
    inputs = list(urls)
    if not inputs:
        raise BatchValidationError("at least one URL is required")
    if log:
        raise CollectionUnavailable("structured logging is not implemented yet")
    offline_capture = None
    if offline_enabled():
        if len(inputs) != 1:
            raise BatchValidationError("offline mode accepts exactly one URL")
        offline_capture = load_offline_capture(
            Path(os.environ["FACEBOOK_COLLECTOR_OFFLINE_CAPTURE_FILE"])
        )

    def collect_one(input_url: str) -> dict:
        if offline_capture is not None:
            return build_outcome(input_url, offline_capture)
        try:
            validate_public_url(input_url)
        except UrlRejected as error:
            return empty_outcome(input_url, 0, "invalid_input", error.reason)
        raise CollectionUnavailable("live collection is not implemented yet")

    outcomes, stop_reason = run_serial(inputs, collect_one)
    run_status = "stopped" if stop_reason else "completed"
    return write_run(Path(output_dir), outcomes, run_status, stop_reason)
