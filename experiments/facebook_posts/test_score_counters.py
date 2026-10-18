"""Synthetic offline contracts for the counter accuracy report."""

import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from score_counters import score_counters, validate_manifest


TIME = "2026-10-19T03:00:00Z"


def inspection(sample="P01", value=10, **fields):
    result = {"reaction_count": value, "reaction_text_raw": str(value),
              "reaction_scope_status": "target_scoped"}
    result.update(fields)
    return {"sample_id": sample, "session_id": "synthetic-session",
            "surface": "desktop_web", "observed_at": TIME, "result": result}


def reference(sample="P01", value=10, **fields):
    row = {"sample_id": sample, "metric": "reaction", "value": value,
           "classification": "exact", "surface": "desktop_web",
           "observed_at": TIME, "evidence": "synthetic:P01/reaction",
           "session_id": "synthetic-session"}
    row.update(fields)
    return row


class CounterScoringTests(unittest.TestCase):
    def test_exact_pairs_report_direction_magnitude_and_coverage(self):
        report = score_counters([inspection("match"), inspection("high", 12),
                                 inspection("low", 8)],
                                [reference("match"), reference("high"), reference("low")])
        rows = {row["sample_id"]: row for row in report["rows"] if row["metric"] == "reaction"}
        for sample, signed in (("match", 0), ("high", 2), ("low", -2)):
            with self.subTest(sample=sample):
                self.assertEqual(rows[sample]["comparison"], "exact_pair")
                self.assertEqual(rows[sample]["signed_error"], signed)
                self.assertEqual(rows[sample]["absolute_error"], abs(signed))
                self.assertEqual(rows[sample]["percentage_error"], signed * 10)
        summary = report["metrics"]["reaction"]
        self.assertEqual((summary["total"], summary["readable"], summary["null"],
                          summary["unverified"], summary["comparable_exact"]), (3, 3, 0, 0, 3))
        self.assertEqual(summary["mean_signed_error"], 0)
        self.assertAlmostEqual(summary["mean_absolute_error"], 4 / 3)
        self.assertAlmostEqual(summary["mean_absolute_percentage_error"], 40 / 3)
        self.assertEqual(report["metrics"]["comment"]["null"], 3)

    def test_reference_zero_has_absolute_error_without_percentage(self):
        report = score_counters([inspection("zero", 0), inspection("over", 3)],
                                [reference("zero", 0), reference("over", 0)])
        rows = [row for row in report["rows"] if row["metric"] == "reaction"]
        self.assertEqual([row["absolute_error"] for row in rows], [3, 0])
        self.assertTrue(all(row["percentage_error"] is None for row in rows))
        self.assertTrue(all(row["reference_classification"] == "zero" for row in rows))
        summary = report["metrics"]["reaction"]
        self.assertEqual(summary["zero"], 1)
        self.assertEqual(summary["mean_absolute_error"], 1.5)
        self.assertEqual(summary["percentage_pairs"], 0)
        self.assertIsNone(summary["mean_absolute_percentage_error"])

    def test_compact_notation_and_approximate_references_are_excluded(self):
        for raw in ("1.1K", "1.1k reactions", "1.3 หมื่น", "1.2 พัน", "2.5 แสน", "1.2 ล้าน"):
            with self.subTest(raw=raw):
                report = score_counters([inspection(value=1100, reaction_text_raw=raw)], [reference(value=1100)])
                row = next(row for row in report["rows"] if row["metric"] == "reaction")
                self.assertEqual(row["collector_classification"], "approximate")
                self.assertEqual(row["collector_raw"], raw)
                self.assertIsNone(row["absolute_error"])
                self.assertEqual(report["metrics"]["reaction"]["approximate"], 1)
                self.assertEqual(report["metrics"]["reaction"]["comparable_exact"], 0)
        report = score_counters([inspection()], [reference(classification="approximate")])
        row = next(row for row in report["rows"] if row["metric"] == "reaction")
        self.assertEqual(row["reference_classification"], "approximate")
        self.assertEqual(row["comparison"], "approximate")
        self.assertIsNone(row["signed_error"])

    def test_missing_collector_reference_and_entire_inspection_never_become_zero(self):
        report = score_counters([inspection("missing-value", None), inspection("missing-ref")],
                                [reference("missing-value"), reference("missing-inspection")])
        rows = {row["sample_id"]: row for row in report["rows"] if row["metric"] == "reaction"}
        self.assertEqual(rows["missing-ref"]["comparison"], "missing_reference")
        for sample in ("missing-value", "missing-inspection"):
            self.assertEqual(rows[sample]["collector_classification"], "missing")
            self.assertEqual(rows[sample]["comparison"], "missing_collector")
        self.assertTrue(all(row["absolute_error"] is None for row in rows.values()))
        summary = report["metrics"]["reaction"]
        self.assertEqual((summary["total"], summary["readable"], summary["null"],
                          summary["missing_reference"]), (3, 1, 2, 1))
        self.assertIsNone(summary["mean_absolute_error"])

    def test_conflict_and_unproven_scope_are_unverified_even_when_non_null(self):
        for scope in ("conflicting", "ambiguous", "unverified", None, "unknown"):
            for value in (None, 10):
                with self.subTest(scope=scope, value=value):
                    report = score_counters([inspection(value=value, reaction_scope_status=scope)], [reference()])
                    row = next(row for row in report["rows"] if row["metric"] == "reaction")
                    self.assertEqual(row["collector_classification"], "unverified")
                    self.assertIsNone(row["absolute_error"])
                    self.assertEqual(report["metrics"]["reaction"]["unverified"], 1)

    def test_identity_scoped_fallback_is_comparable(self):
        report = score_counters([inspection(reaction_scope_status="identity_scoped_fallback")], [reference()])
        self.assertEqual(report["metrics"]["reaction"]["comparable_exact"], 1)

    def test_explicit_missing_scope_stays_missing(self):
        report = score_counters([inspection(value=None, reaction_scope_status="missing")], [reference()])
        self.assertEqual(report["metrics"]["reaction"]["missing"], 1)
        self.assertEqual(report["metrics"]["reaction"]["unverified"], 0)

    def test_unverified_classification_cannot_enter_exact_errors(self):
        report = score_counters([inspection(reaction_classification="unverified")], [reference()])
        self.assertEqual(report["metrics"]["reaction"]["unverified"], 1)
        self.assertIsNone(report["metrics"]["reaction"]["mean_absolute_error"])

    def test_different_session_surface_or_time_is_not_comparable(self):
        for fields in ({"session_id": "different"}, {"surface": "mobile_app"},
                       {"observed_at": "2026-10-19T03:00:01Z"}):
            with self.subTest(fields=fields):
                report = score_counters([inspection()], [reference(**fields)])
                row = next(row for row in report["rows"] if row["metric"] == "reaction")
                self.assertEqual(row["comparison"], "not_comparable")
                self.assertIsNone(row["absolute_error"])
        item = inspection()
        del item["session_id"]
        report = score_counters([item], [reference()])
        self.assertEqual(report["metrics"]["reaction"]["comparable_exact"], 0)

    def test_all_three_metrics_and_deterministic_replay_without_input_mutation(self):
        item = inspection(comment_count=4, comment_text_raw="4", comment_scope_status="target_scoped",
                          share_count=2, share_text_raw="2", share_scope_status="target_scoped")
        refs = [reference(), reference(value=4, metric="comment"), reference(value=2, metric="share")]
        original = copy.deepcopy((item, refs))
        first = score_counters([item], refs)
        self.assertEqual(first, score_counters([item], list(reversed(refs))))
        self.assertEqual((item, refs), original)
        self.assertTrue(all(summary["comparable_exact"] == 1 for summary in first["metrics"].values()))

    def test_invalid_collector_counts_and_duplicate_samples_are_rejected(self):
        for value in (-1, True, 1.5, "10"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                score_counters([inspection(value=value)], [])
        with self.assertRaises(ValueError):
            score_counters([inspection(), inspection()], [])

    def test_empty_inputs_have_no_fabricated_errors(self):
        report = score_counters([], [])
        self.assertEqual(report["rows"], [])
        self.assertEqual(report["metrics"]["reaction"]["total"], 0)
        self.assertIsNone(report["metrics"]["reaction"]["mean_absolute_error"])


class ManifestTests(unittest.TestCase):
    def test_required_reference_fields_and_duplicate_pairs(self):
        row = reference()
        validate_manifest([row])
        for field in row:
            broken = dict(row)
            del broken[field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_manifest([broken])
        with self.assertRaises(ValueError):
            validate_manifest([row, row])

    def test_invalid_types_classification_and_utc_time(self):
        invalid = {"sample_id": ("", None), "metric": ("likes",),
                   "value": (-1, True, 1.1, "1", None),
                   "classification": ("zero", "missing", "unverified", "EXACT"),
                   "surface": ("", None), "session_id": ("", None),
                   "evidence": ("", None, {}),
                   "observed_at": ("yesterday", "2026-10-19", "2026-10-19T03:00:00",
                                   "2026-10-19T03:00:00+07:00")}
        for field, values in invalid.items():
            for value in values:
                with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                    validate_manifest([reference(**{field: value})])

    def test_equivalent_utc_iso_timestamps_compare(self):
        report = score_counters([inspection()], [reference(observed_at="2026-10-19T03:00:00+00:00")])
        self.assertEqual(report["metrics"]["reaction"]["comparable_exact"], 1)

    def test_cli_replays_local_json_and_rejects_invalid_manifest(self):
        script = Path(__file__).with_name("score_counters.py")
        with tempfile.TemporaryDirectory() as directory:
            results_path = Path(directory) / "inspections.json"
            refs_path = Path(directory) / "references.json"
            results_path.write_text(json.dumps([inspection()]), encoding="utf-8")
            refs_path.write_text(json.dumps([reference()]), encoding="utf-8")
            args = [sys.executable, str(script), str(results_path), str(refs_path)]
            first = subprocess.run(args, capture_output=True, text=True, check=True)
            second = subprocess.run(args, capture_output=True, text=True, check=True)
            self.assertEqual(first.stdout, second.stdout)
            self.assertEqual(json.loads(first.stdout)["metrics"]["reaction"]["comparable_exact"], 1)
            refs_path.write_text('[{"metric": "reaction"}]', encoding="utf-8")
            failed = subprocess.run(args, capture_output=True, text=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("sample_id", failed.stderr)


if __name__ == "__main__":
    unittest.main()
