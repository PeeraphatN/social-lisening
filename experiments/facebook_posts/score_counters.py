"""Deterministic offline scoring of saved Facebook counter inspections.

Python: score_counters(inspections, manifest) -> JSON-compatible report.
CLI: python score_counters.py inspections.json references.json

Both inputs are JSON arrays. Inspection entries wrap an unchanged inspection
``result`` with ``sample_id``, ``session_id``, ``surface``, and ``observed_at``.
Reference entries require those four metadata fields plus ``metric`` (reaction,
comment, share), nonnegative integer ``value``, ``classification`` (exact or
approximate), and a nonempty ``evidence`` pointer. Observation times are ISO 8601
UTC. Evidence pointers are retained as strings and are never opened or fetched.

Exact comparisons require matching session, surface, and observation time.
Missing capture metadata prevents comparison. Counts require accepted metric
scope; compact raw notation always stays approximate. Readable means non-null,
so unverified is an independent coverage count that can overlap readable/null.
Zero is separate from positive exact counts. Error means use exact pairs only;
percentage_error is signed, and percentage means exclude reference zero.
"""

import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
import re


METRICS = ("reaction", "comment", "share")
ACCEPTED_SCOPES = ("target_scoped", "identity_scoped_fallback")
COMPACT = re.compile(r"\d(?:[\d,.]*)\s*(?:หมื่น|พัน|แสน|ล้าน|[kmb]\b)", re.IGNORECASE)


def _text(row, field):
    value = row.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a nonempty string")
    return value


def _utc(value):
    try:
        if not isinstance(value, str) or "T" not in value:
            raise ValueError
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.utcoffset() != timedelta(0):
            raise ValueError
        return parsed
    except ValueError:
        raise ValueError("observed_at must be an ISO 8601 UTC timestamp") from None


def _count(value):
    if type(value) is not int or value < 0:
        raise ValueError("counter value must be a nonnegative integer")


def validate_manifest(manifest):
    """Validate reference records; reject ambiguous duplicate sample/metric pairs."""
    if not isinstance(manifest, list):
        raise ValueError("manifest must be an array")
    seen = set()
    for row in manifest:
        if not isinstance(row, dict):
            raise ValueError("manifest entry must be an object")
        sample = _text(row, "sample_id")
        if row.get("metric") not in METRICS:
            raise ValueError("metric must be reaction, comment, or share")
        _count(row.get("value"))
        if row.get("classification") not in ("exact", "approximate"):
            raise ValueError("classification must be exact or approximate")
        for field in ("surface", "session_id", "evidence"):
            _text(row, field)
        _utc(row.get("observed_at"))
        key = (sample, row["metric"])
        if key in seen:
            raise ValueError(f"duplicate reference: {sample}/{row['metric']}")
        seen.add(key)


def _classification(result, metric):
    value = result.get(f"{metric}_count")
    scope = result.get(f"{metric}_scope_status")
    if value is not None:
        _count(value)
    if result.get(f"{metric}_classification") == "unverified":
        return "unverified"
    if value is None and scope == "missing":
        return "missing"
    if scope not in ACCEPTED_SCOPES:
        # No metric at all is missing; explicitly rejected evidence is unverified.
        return "unverified" if value is not None or f"{metric}_scope_status" in result else "missing"
    if value is None:
        return "missing"
    raw = result.get(f"{metric}_text_raw") or ""
    if not isinstance(raw, str):
        raise ValueError(f"{metric}_text_raw must be a string or null")
    if COMPACT.search(raw) or result.get(f"{metric}_classification") == "approximate":
        return "approximate"
    return "zero" if value == 0 else "exact"


def _same_capture(inspection, reference):
    return (all(inspection.get(field) == reference[field] for field in ("session_id", "surface"))
            and inspection.get("observed_at") is not None
            and _utc(inspection["observed_at"]) == _utc(reference["observed_at"]))


def score_counters(inspections, manifest):
    """Return stable per-sample errors and per-metric coverage/error aggregates."""
    validate_manifest(manifest)
    if not isinstance(inspections, list):
        raise ValueError("inspections must be an array")
    indexed = {}
    for item in inspections:
        if not isinstance(item, dict):
            raise ValueError("inspection entry must be an object")
        sample = _text(item, "sample_id")
        if sample in indexed:
            raise ValueError(f"duplicate inspection: {sample}")
        if not isinstance(item.get("result"), dict):
            raise ValueError("inspection result must be an object")
        if item.get("observed_at") is not None:
            _utc(item["observed_at"])
        indexed[sample] = item
    references = {(row["sample_id"], row["metric"]): row for row in manifest}
    samples = sorted(set(indexed) | {key[0] for key in references})
    rows = []
    for sample in samples:
        item = indexed.get(sample, {})
        result = item.get("result", {})
        for metric in METRICS:
            ref = references.get((sample, metric))
            classification = _classification(result, metric)
            ref_class = "missing" if ref is None else ref["classification"]
            if ref_class == "exact" and ref["value"] == 0:
                ref_class = "zero"
            row = {"sample_id": sample, "metric": metric,
                   "collector_value": result.get(f"{metric}_count"),
                   "collector_raw": result.get(f"{metric}_text_raw"),
                   "collector_classification": classification,
                   "reference_value": ref["value"] if ref else None,
                   "reference_classification": ref_class,
                   "reference_evidence": ref["evidence"] if ref else None,
                   "signed_error": None, "absolute_error": None,
                   "percentage_error": None, "absolute_percentage_error": None}
            if classification == "unverified":
                comparison = "unverified"
            elif classification == "missing":
                comparison = "missing_collector"
            elif ref is None:
                comparison = "missing_reference"
            elif not _same_capture(item, ref):
                comparison = "not_comparable"
            elif "approximate" in (classification, ref_class):
                comparison = "approximate"
            else:
                comparison = "exact_pair"
                signed = row["collector_value"] - ref["value"]
                row.update(signed_error=signed, absolute_error=abs(signed))
                if ref["value"] > 0:
                    percentage = signed / ref["value"] * 100
                    row.update(percentage_error=percentage, absolute_percentage_error=abs(percentage))
            row["comparison"] = comparison
            rows.append(row)

    summaries = {}
    for metric in METRICS:
        metric_rows = [row for row in rows if row["metric"] == metric]
        summary = {"total": len(metric_rows),
                   "readable": sum(row["collector_value"] is not None for row in metric_rows),
                   "null": sum(row["collector_value"] is None for row in metric_rows),
                   "missing_reference": sum(row["reference_classification"] == "missing" for row in metric_rows),
                   "comparable_exact": sum(row["comparison"] == "exact_pair" for row in metric_rows),
                   "percentage_pairs": sum(row["percentage_error"] is not None for row in metric_rows)}
        for classification in ("exact", "approximate", "zero", "missing", "unverified"):
            summary[classification] = sum(row["collector_classification"] == classification for row in metric_rows)
        for error in ("signed_error", "absolute_error", "percentage_error", "absolute_percentage_error"):
            values = [row[error] for row in metric_rows if row[error] is not None]
            summary[f"mean_{error}"] = sum(values) / len(values) if values else None
        summaries[metric] = summary
    return {"metrics": summaries, "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inspections", type=Path)
    parser.add_argument("manifest", type=Path)
    args = parser.parse_args()
    try:
        inspections = json.loads(args.inspections.read_text(encoding="utf-8"))
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = score_counters(inspections, manifest)
    except (ValueError, OSError) as error:
        parser.error(str(error))
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
