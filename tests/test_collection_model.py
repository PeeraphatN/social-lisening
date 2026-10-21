"""Focused tests for contract-fixed collection and latest rules."""

import unittest

from facebook_collector.model import (
    BatchValidationError,
    capture_status,
    run_serial,
    update_latest,
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


class LatestStoreTests(unittest.TestCase):
    def test_candidate_partial_replaces_every_latest_capture_field_including_null(self):
        identity = {"kind": "post", "post_id": "123", "owner_id": "456"}
        existing = {
            "post:456:123": {
                "post_identity": identity,
                "text": {"value": "old", "status": "candidate_text_unverified"},
                "counters": {"reaction": counter(5, "exact")},
                "collected_at": "2026-10-20T08:00:00Z",
            }
        }
        outcome = {
            "status": "partial",
            "post_identity": identity,
            "text": {"value": "new", "status": "candidate_text_unverified"},
            "counters": {
                "reaction": counter(None, "unverified"),
                "comment": counter(0, "exact"),
                "share": counter(2, "exact"),
            },
            "collected_at": "2026-10-20T08:00:12Z",
        }

        updated, latest_updated = update_latest(existing, outcome)

        self.assertTrue(latest_updated)
        self.assertEqual(list(updated.values()), [outcome])
        self.assertIsNone(list(updated.values())[0]["counters"]["reaction"]["value"])

    def test_preview_only_does_not_overwrite_latest(self):
        identity = {"kind": "post", "post_id": "123", "owner_id": "456"}
        existing = {
            "post:456:123": {
                "post_identity": identity,
                "text": {"value": "old", "status": "candidate_text_unverified"},
            }
        }
        outcome = {
            "status": "partial",
            "post_identity": identity,
            "text": {"value": "preview", "status": "preview_only"},
        }

        updated, latest_updated = update_latest(existing, outcome)

        self.assertFalse(latest_updated)
        self.assertEqual(updated, existing)

    def test_incomplete_latest_envelope_does_not_overwrite_latest(self):
        identity = {"kind": "post", "post_id": "123", "owner_id": "456"}
        existing = {
            "post:456:123": {
                "post_identity": identity,
                "text": {"value": "old", "status": "candidate_text_unverified"},
                "counters": {
                    "reaction": counter(5, "exact"),
                    "comment": counter(1, "exact"),
                    "share": counter(2, "exact"),
                },
                "collected_at": "2026-10-20T08:00:00Z",
            }
        }
        outcome = {
            "status": "partial",
            "post_identity": identity,
            "text": {"value": "new", "status": "candidate_text_unverified"},
            "counters": {
                "reaction": counter(None, "unverified"),
                "comment": counter(0, "exact"),
            },
        }

        updated, latest_updated = update_latest(existing, outcome)

        self.assertFalse(latest_updated)
        self.assertEqual(updated, existing)

    def test_new_latest_key_is_canonical_compact_sorted_identity_json(self):
        identity = {"kind": "group", "post_id": "2", "group_id": "1"}
        outcome = {
            "status": "collected",
            "post_identity": identity,
            "collected_at": "2026-10-21T10:00:00Z",
            "text": {"value": "new", "status": "candidate_text_unverified"},
            "counters": {
                "reaction": counter(1, "exact"),
                "comment": counter(2, "exact"),
                "share": counter(3, "exact"),
            },
            "duplicate_of": None,
        }

        updated, latest_updated = update_latest({}, outcome)

        self.assertTrue(latest_updated)
        self.assertEqual(
            list(updated),
            ['{"group_id":"1","kind":"group","post_id":"2"}'],
        )

    def test_duplicate_outcome_never_overwrites_latest(self):
        identity = {"kind": "photo", "photo_id": "1"}
        existing = {
            '{"kind":"photo","photo_id":"1"}': {
                "post_identity": identity,
                "text": {"value": "old", "status": "candidate_text_unverified"},
            }
        }
        duplicate = {
            "status": "collected",
            "post_identity": identity,
            "collected_at": "2026-10-21T10:00:00Z",
            "text": {"value": "duplicate", "status": "candidate_text_unverified"},
            "counters": {
                "reaction": counter(1, "exact"),
                "comment": counter(2, "exact"),
                "share": counter(3, "exact"),
            },
            "duplicate_of": 0,
        }

        updated, latest_updated = update_latest(existing, duplicate)

        self.assertFalse(latest_updated)
        self.assertEqual(updated, existing)

    def test_failure_outcomes_do_not_overwrite_latest(self):
        identity = {"kind": "post", "post_id": "123", "owner_id": "456"}
        existing = {
            "post:456:123": {
                "post_identity": identity,
                "text": {"value": "old", "status": "candidate_text_unverified"},
            }
        }

        for status in ("timeout", "error", "blocked"):
            with self.subTest(status=status):
                outcome = {"status": status, "post_identity": identity}
                updated, latest_updated = update_latest(existing, outcome)

                self.assertFalse(latest_updated)
                self.assertEqual(updated, existing)

        unvalidated = {"status": "error", "post_identity": None}
        updated, latest_updated = update_latest(existing, unvalidated)

        self.assertFalse(latest_updated)
        self.assertEqual(updated, existing)


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
