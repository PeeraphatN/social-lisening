"""Contract-fixed collection status and serial batch rules."""

from copy import deepcopy


EVIDENCED_QUALITIES = {"exact", "approximate"}
COUNTER_NAMES = ("reaction", "comment", "share")
COUNTER_KEYS = set(COUNTER_NAMES)
MAX_UNIQUE_URLS = 10


class BatchValidationError(ValueError):
    """The invocation cannot safely start."""


def capture_status(text: dict, counters: dict) -> str:
    """Return the capture status for validated identity data."""
    metrics = list(counters.values())
    if (
        text.get("status") == "candidate_text_unverified"
        and set(counters) == COUNTER_KEYS
        and all(
            metric.get("quality") in EVIDENCED_QUALITIES
            and isinstance(metric.get("value"), int)
            and not isinstance(metric.get("value"), bool)
            and metric["value"] >= 0
            for metric in metrics
        )
    ):
        return "collected"
    return "partial"


def empty_outcome(input_url: str, input_index: int, status: str, reason: str) -> dict:
    """Build the complete null envelope used when no target capture exists."""
    return {
        "input_index": input_index,
        "duplicate_of": None,
        "input_url": input_url,
        "resolved_url": None,
        "post_identity": None,
        "attempted_at": None,
        "collected_at": None,
        "status": status,
        "reason": reason,
        "text": {"value": None, "status": "missing", "source": None},
        "counters": {
            name: {
                "value": None,
                "raw": None,
                "quality": "missing",
                "source": None,
            }
            for name in COUNTER_NAMES
        },
        "latest_updated": False,
    }


def run_serial(inputs: list[str], attempt) -> tuple[list[dict], str | None]:
    """Attempt unique inputs in order and stop only for approved safety failures."""
    if len(dict.fromkeys(inputs)) > MAX_UNIQUE_URLS:
        raise BatchValidationError("at most 10 unique URLs are allowed")

    outcomes = []
    first_indexes = {}
    stop_reason = None
    for index, input_url in enumerate(inputs):
        if input_url in first_indexes:
            duplicate = deepcopy(outcomes[first_indexes[input_url]])
            duplicate["input_index"] = index
            duplicate["duplicate_of"] = first_indexes[input_url]
            duplicate["latest_updated"] = False
            outcomes.append(duplicate)
            continue

        outcome = deepcopy(attempt(input_url))
        outcome["input_index"] = index
        outcome["duplicate_of"] = None
        outcomes.append(outcome)
        first_indexes[input_url] = index
        if outcome.get("status") == "blocked":
            stop_reason = "blocked"
        if stop_reason:
            outcomes.extend(
                empty_outcome(pending_url, pending_index, "not_attempted", stop_reason)
                for pending_index, pending_url in enumerate(inputs[index + 1 :], index + 1)
            )
            break
    return outcomes, stop_reason
