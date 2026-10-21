"""Focused tests for contract-fixed collection and serial batch rules."""

import unittest

from facebook_collector.model import (
    BatchValidationError,
    capture_status,
    run_serial,
)


def counter(value, quality):
    return {
        "value": value,
        "raw": None,
        "quality": quality,
        "source": "synthetic_target",
    }


class CaptureStatusTests(unittest.TestCase):
    def test_candidate_text_and_evidenced_counters_is_collected(self):
        status = capture_status(
            {"status": "candidate_text_unverified"},
            {
                "reaction": counter(12, "exact"),
                "comment": counter(3, "exact"),
                "share": counter(1, "approximate"),
            },
        )

        self.assertEqual(status, "collected")

    def test_null_missing_counter_makes_candidate_capture_partial(self):
        status = capture_status(
            {"status": "candidate_text_unverified"},
            {
                "reaction": counter(12, "exact"),
                "comment": counter(None, "missing"),
                "share": counter(0, "exact"),
            },
        )

        self.assertEqual(status, "partial")

    def test_evidenced_quality_with_null_value_is_not_collected(self):
        status = capture_status(
            {"status": "candidate_text_unverified"},
            {
                "reaction": counter(None, "exact"),
                "comment": counter(3, "exact"),
                "share": counter(0, "exact"),
            },
        )

        self.assertEqual(status, "partial")

    def test_foreign_counter_key_makes_candidate_capture_partial(self):
        status = capture_status(
            {"status": "candidate_text_unverified"},
            {
                "reaction": counter(12, "exact"),
                "comment": counter(3, "exact"),
                "shares": counter(1, "approximate"),
            },
        )

        self.assertEqual(status, "partial")


class SerialQueueTests(unittest.TestCase):
    def test_block_stops_later_attempts_and_preserves_earlier_outcomes(self):
        attempted = []

        def attempt(url):
            attempted.append(url)
            if url.endswith("blocked"):
                return {"input_url": url, "status": "blocked"}
            return {"input_url": url, "status": "collected"}

        outcomes, stop_reason = run_serial(
            ["https://synthetic/first", "https://synthetic/blocked", "https://synthetic/later"],
            attempt,
        )

        self.assertEqual(
            attempted,
            ["https://synthetic/first", "https://synthetic/blocked"],
        )
        self.assertEqual(
            [outcome["status"] for outcome in outcomes],
            ["collected", "blocked", "not_attempted"],
        )
        self.assertEqual(stop_reason, "blocked")
        self.assertEqual(
            outcomes[-1],
            {
                "input_index": 2,
                "duplicate_of": None,
                "input_url": "https://synthetic/later",
                "resolved_url": None,
                "post_identity": None,
                "attempted_at": None,
                "collected_at": None,
                "status": "not_attempted",
                "reason": "blocked",
                "text": {"value": None, "status": "missing", "source": None},
                "counters": {
                    name: {
                        "value": None,
                        "raw": None,
                        "quality": "missing",
                        "source": None,
                    }
                    for name in ("reaction", "comment", "share")
                },
                "latest_updated": False,
            },
        )

    def test_identity_unverified_continues_to_later_inputs(self):
        attempted = []

        def attempt(url):
            attempted.append(url)
            if url.endswith("unverified"):
                return {
                    "input_url": url,
                    "status": "error",
                    "reason": "identity_unverified",
                }
            return {"input_url": url, "status": "collected"}

        outcomes, stop_reason = run_serial(
            ["https://synthetic/unverified", "https://synthetic/later"],
            attempt,
        )

        self.assertEqual(
            attempted,
            ["https://synthetic/unverified", "https://synthetic/later"],
        )
        self.assertEqual(
            [outcome["status"] for outcome in outcomes],
            ["error", "collected"],
        )
        self.assertIsNone(stop_reason)

    def test_exact_duplicate_fetches_once_and_keeps_an_ordered_linked_outcome(self):
        attempted = []

        def attempt(url):
            attempted.append(url)
            return {
                "input_url": url,
                "status": "collected",
                "latest_updated": True,
            }

        url = "https://synthetic/same"
        outcomes, stop_reason = run_serial([url, url], attempt)

        self.assertEqual(attempted, [url])
        self.assertIsNone(stop_reason)
        self.assertEqual([outcome["input_index"] for outcome in outcomes], [0, 1])
        self.assertIsNone(outcomes[0]["duplicate_of"])
        self.assertEqual(outcomes[1]["duplicate_of"], 0)
        self.assertFalse(outcomes[1]["latest_updated"])

    def test_more_than_ten_unique_urls_rejects_before_any_attempt(self):
        attempted = []
        inputs = [f"https://synthetic/{index}" for index in range(11)]

        with self.assertRaises(BatchValidationError):
            run_serial(inputs, attempted.append)

        self.assertEqual(attempted, [])

if __name__ == "__main__":
    unittest.main()
