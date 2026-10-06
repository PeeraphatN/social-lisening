"""Run the five reviewed public-post samples three times, without logging in."""

import csv
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from probe_post import validate_url


def compare_post(result, reference):
    if result.get("http_status") in (403, 429):
        return "blocked"
    if result.get("status") != "candidate_text_unverified" or not result.get("text"):
        return "text_unavailable"
    if " ".join(result["text"].split()) != " ".join(reference["text"].split()):
        return "text_changed"
    # ponytail: confirmation for these five known authors, not a general author extractor.
    if reference["publisher"] not in result.get("body_preview", "").split(result["text"][:40])[0]:
        return "publisher_not_confirmed"
    return "match"


def main():
    root = Path(__file__).resolve().parent
    references = json.loads((root / "runs" / "references.json").read_text(encoding="utf-8"))
    assert [ref["sample_id"] for ref in references] == [f"P{i:02}" for i in range(1, 6)]
    for ref in references:
        assert hashlib.sha256(ref["text"].encode("utf-8")).hexdigest() == ref["review"]["text_sha256"]
        validate_url(ref.get("fetch_url", ref["input_url"]))
    session_id = datetime.now(timezone.utc).strftime("repeat-%Y%m%dT%H%M%SZ")
    output = root / "runs" / session_id
    output.mkdir()
    (output / "references.json").write_text(json.dumps(references, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"session_id": session_id, "status": "running", "rounds_planned": 3,
               "interval_seconds": 600, "sample_count": 5, "rounds": []}
    latest = {}

    def save():
        (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        rows = [item for round_result in summary["rounds"] for item in round_result["samples"]]
        if rows:
            with (output / "checks.csv").open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
        if latest:
            with (output / "posts.csv").open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.DictWriter(file, fieldnames=list(next(iter(latest.values()))))
                writer.writeheader()
                writer.writerows(latest.values())

    save()
    print(json.dumps({"session_id": session_id, "status": "started"}), flush=True)
    stop = False
    for number in range(1, 4):
        round_result = {"round": number, "started_at": datetime.now(timezone.utc).isoformat(), "samples": []}
        summary["rounds"].append(round_result)
        for ref in references:
            run_id = f"{session_id}-r{number}-{ref['sample_id'].lower()}"
            row = {"round": number, "sample_id": ref["sample_id"], "status": "not_attempted",
                   "characters": 0, "http_status": None, "collected_at": None,
                   "raw_hash_matches": False, "error_reason": None, "run_id": run_id}
            if not stop:
                try:
                    execution = subprocess.run([sys.executable, str(root / "inspect_browser.py"),
                                                ref.get("fetch_url", ref["input_url"]), "--run-id", run_id],
                                               capture_output=True, text=True, timeout=60)
                    if execution.returncode:
                        raise RuntimeError(execution.stderr[-1000:])
                    result = json.loads((root / "runs" / f"{run_id}-inspection.json").read_text(encoding="utf-8"))
                    row.update(status=compare_post(result, ref), characters=len(result.get("text") or ""),
                               http_status=result.get("http_status"), collected_at=result.get("collected_at"),
                               raw_hash_matches=hashlib.sha256((result.get("text") or "").encode("utf-8")).hexdigest() == ref["review"]["text_sha256"])
                    if row["status"] == "match":
                        latest[ref["sample_id"]] = {"sample_id": ref["sample_id"], "publisher": ref["publisher"],
                                                   "text": result["text"], "input_url": ref["input_url"],
                                                   "fetch_url": result["resolved_url"], "collected_at": result["collected_at"],
                                                   "matched_round": number, "status": "reference_match"}
                    stop = row["status"] == "blocked"
                except (subprocess.TimeoutExpired, RuntimeError, OSError, json.JSONDecodeError) as error:
                    row.update(status="request_failed", error_reason=str(error))
            round_result["samples"].append(row)
            save()
            print(json.dumps({"round": number, "sample": ref["sample_id"], "status": row["status"]}), flush=True)
        statuses = {row["sample_id"]: row["status"] for row in round_result["samples"]}
        round_result.update(finished_at=datetime.now(timezone.utc).isoformat(),
                            matches=sum(status == "match" for status in statuses.values()))
        round_result["passed"] = round_result["matches"] >= 4 and all(statuses[sample] == "match" for sample in ("P02", "P05"))
        save()
        print(json.dumps({"round": number, "matches": round_result["matches"], "passed": round_result["passed"]}), flush=True)
        if stop:
            break
        if number < 3:
            summary["next_round_at"] = datetime.fromtimestamp(time.time() + 600, timezone.utc).isoformat()
            save()
            print(json.dumps({"waiting_seconds": 600, "next_round": number + 1}), flush=True)
            time.sleep(600)
    summary.update(status="stopped_after_block" if stop else "complete",
                   passed=len(summary["rounds"]) == 3 and all(item["passed"] for item in summary["rounds"]),
                   finished_at=datetime.now(timezone.utc).isoformat())
    summary.pop("next_round_at", None)
    save()
    print(json.dumps({"status": summary["status"], "passed": summary["passed"], "output": str(output)}), flush=True)


if __name__ == "__main__":
    main()
