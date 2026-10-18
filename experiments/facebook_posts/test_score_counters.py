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

    def test_compact_intervals_distinguish_compatible_values_and_boundaries(self):
        # 1.2K rounds to [1150, 1250); the upper tie belongs to 1.3K.
        for value, expected in ((1149, "incompatible"), (1150, "compatible"),
                                (1200, "compatible"), (1249, "compatible"),
                                (1250, "incompatible"), (5000, "incompatible")):
            with self.subTest(value=value):
                report = score_counters([inspection(value=value, reaction_text_raw="1.2K")],
                                        [reference(value=value)])
                row = report["rows"][0]
                self.assertEqual(row["comparison"], "approximate")
                self.assertEqual(row["interval_compatibility"], expected)
                self.assertEqual(row["collector_interval"], {"lower": 1150, "upper": 1250})
                for error in ("signed_error", "absolute_error", "percentage_error", "absolute_percentage_error"):
                    self.assertIsNone(row[error])
                    self.assertIsNone(report["metrics"]["reaction"][f"mean_{error}"])

    def test_exact_reference_must_fit_collector_interval_too(self):
        for value, expected in ((1150, "compatible"), (1249, "compatible"), (1250, "incompatible")):
            with self.subTest(value=value):
                report = score_counters([inspection(value=1200, reaction_text_raw="1.2K")],
                                        [reference(value=value)])
                self.assertEqual(report["rows"][0]["interval_compatibility"], expected)

    def test_supported_compact_units_precision_and_metric_labels(self):
        cases = (("1K", 500, 1500), ("1.20k reactions", 1195, 1205),
                 ("All reactions 1.2M", 1150000, 1250000),
                 ("1.2 พัน", 1150, 1250), ("1.3 หมื่น", 12500, 13500),
                 ("2.5 แสน", 245000, 255000), ("1.2 ล้าน", 1150000, 1250000),
                 ("0K", 0, 500), ("1,234.5K", 1234450, 1234550),
                 ("1.2345K", 1235, 1235))
        for raw, lower, upper in cases:
            with self.subTest(raw=raw):
                report = score_counters([inspection(value=lower, reaction_text_raw=raw)],
                                        [reference(value=lower)])
                row = report["rows"][0]
                self.assertEqual(row["collector_interval"], {"lower": lower, "upper": upper})
                self.assertEqual(row["interval_compatibility"],
                                 "compatible" if lower < upper else "incompatible")
        for metric, raw in (("comment", "comments 1.2K"), ("comment", "ความคิดเห็น 1.2 พัน รายการ"),
                            ("share", "แชร์ 1.2 พัน ครั้ง"), ("share", "1.2M shares")):
            with self.subTest(metric=metric, raw=raw):
                value = 1200000 if "M" in raw else 1200
                item = inspection(**{f"{metric}_count": value, f"{metric}_text_raw": raw,
                                     f"{metric}_scope_status": "target_scoped"})
                report = score_counters([item], [reference(metric=metric, value=value)])
                row = next(row for row in report["rows"] if row["metric"] == metric)
                self.assertEqual(row["interval_compatibility"], "compatible")

    def test_approximate_reference_raw_is_optional_but_never_inferred(self):
        for value, expected in ((1150, "compatible"), (1249, "compatible"), (1250, "incompatible")):
            with self.subTest(value=value):
                report = score_counters([inspection(value=value)],
                                        [reference(value=1200, classification="approximate", text_raw="1.2K")])
                row = report["rows"][0]
                self.assertEqual(row["interval_compatibility"], expected)
                self.assertEqual(row["reference_interval"], {"lower": 1150, "upper": 1250})
                self.assertIsNone(row["signed_error"])
        for fields in ({}, {"reaction_classification": "approximate"}):
            report = score_counters([inspection(**fields)], [reference(classification="approximate")])
            self.assertEqual(report["rows"][0]["interval_compatibility"], "unavailable")

    def test_two_approximate_operands_use_interval_overlap(self):
        for raw, value, expected in (("1.2K", 1200, "compatible"),
                                     ("1.5K", 1500, "compatible"),
                                     ("2K", 2000, "incompatible"),
                                     ("1.2K", 5000, "incompatible")):
            with self.subTest(raw=raw, value=value):
                report = score_counters([inspection(value=1000, reaction_text_raw="1K")],
                                        [reference(value=value, classification="approximate", text_raw=raw)])
                self.assertEqual(report["rows"][0]["interval_compatibility"], expected)

    def test_malformed_or_unsupported_raw_is_rejected_without_guessing(self):
        for raw in ("1.2B", "1.2KK", "1,2K", "1..2K", "-1.2K", "+1.2K", "1e3K",
                    "1.2K+", "about 1.2K", "1.2K 3 shares", "1.2K comments", "๑.๒ พัน", "1.2K!", "1.2"):
            with self.subTest(raw=raw):
                report = score_counters([inspection(value=1200, reaction_text_raw=raw)], [reference(value=1200)])
                row = report["rows"][0]
                self.assertEqual(row["comparison"], "unverified")
                self.assertIsNone(row["interval_compatibility"])
                self.assertEqual(report["metrics"]["reaction"]["comparable_exact"], 0)
                with self.assertRaises(ValueError):
                    validate_manifest([reference(value=1200, classification="approximate", text_raw=raw)])

    def test_interval_scoring_obeys_missing_unverified_and_capture_gates(self):
        cases = ((inspection(value=None, reaction_text_raw="1.2K"), reference(), "missing_collector"),
                 (inspection(value=1200, reaction_text_raw="1.2K"), None, "missing_reference"),
                 (inspection(value=1200, reaction_text_raw="1.2K", reaction_scope_status="conflicting"),
                  reference(value=1200), "unverified"))
        cases += tuple((inspection(value=1200, reaction_text_raw="1.2K"), reference(value=1200, **fields),
                        "not_comparable") for fields in ({"session_id": "other"}, {"surface": "mobile"},
                                                         {"observed_at": "2026-10-19T03:00:01Z"}))
        for item, ref, comparison in cases:
            with self.subTest(comparison=comparison):
                report = score_counters([item], [ref] if ref else [])
                row = report["rows"][0]
                self.assertEqual(row["comparison"], comparison)
                self.assertIsNone(row["interval_compatibility"])

    def test_approximate_pairs_do_not_change_mixed_exact_aggregates(self):
        report = score_counters([inspection("exact", 12), inspection("approx", 1200, reaction_text_raw="1.2K")],
                                [reference("exact", 10), reference("approx", 5000)])
        summary = report["metrics"]["reaction"]
        self.assertEqual((summary["comparable_exact"], summary["percentage_pairs"]), (1, 1))
        self.assertEqual(summary["mean_signed_error"], 2)
        self.assertEqual(summary["mean_absolute_error"], 2)
        self.assertEqual(summary["mean_percentage_error"], 20)
        self.assertEqual(summary["mean_absolute_percentage_error"], 20)

    def test_interval_report_replays_without_mutation_and_serializes(self):
        items = [inspection("compact", 1200, reaction_text_raw="1.2K"), inspection("exact", 5000)]
        refs = [reference("compact", 1249), reference("exact", 1200, classification="approximate", text_raw="1.2K")]
        original = copy.deepcopy((items, refs))
        report = score_counters(items, refs)
        self.assertEqual(report, score_counters(list(reversed(items)), list(reversed(refs))))
        self.assertEqual(report, json.loads(json.dumps(report)))
        self.assertEqual((items, refs), original)

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
