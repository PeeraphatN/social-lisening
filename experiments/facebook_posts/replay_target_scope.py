"""Replay saved P01-P10 HTML with scripts disabled and every request intercepted."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import types

from playwright.sync_api import sync_playwright

import probe_post


ROOT = Path(__file__).resolve().parent
METRICS = ("reaction", "comment", "share")
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT / ".playwright"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default=str(ROOT / "runs/counter-scope-final-20261018T212903Z"))
    parser.add_argument("--revision", help="Read probe_post.py from this local git revision")
    parser.add_argument("--output", type=Path, default=ROOT / "runs/target-scope-replay.json")
    args = parser.parse_args()
    probe = probe_post
    source = (ROOT / "probe_post.py").read_bytes()
    if args.revision:
        source = subprocess.check_output(
            ["git", "show", f"{args.revision}:experiments/facebook_posts/probe_post.py"], cwd=ROOT)
        probe = types.ModuleType("replay_probe")
        exec(compile(source, "replay_probe_post.py", "exec"), probe.__dict__)

    results = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(viewport={"width": 1280, "height": 1000},
                                      java_script_enabled=False, service_workers="block")
        try:
            for index in range(1, 11):
                sample = f"P{index:02}"
                prefix = f"{args.prefix}-{sample.lower()}"
                saved = json.loads(Path(f"{prefix}-inspection.json").read_text(encoding="utf-8"))
                content_bytes = Path(f"{prefix}-page.html").read_bytes()
                content = content_bytes.decode("utf-8")
                page = context.new_page()
                # No route.continue_: no navigation or resource reaches Facebook.
                page.route("**/*", lambda route: route.fulfill(
                    status=200, content_type="text/html; charset=utf-8", body=content)
                    if route.request.is_navigation_request() else route.abort())
                page.goto(saved["resolved_url"], wait_until="domcontentloaded")
                metrics = probe.inspect_browser_metrics(page, saved["input_url"], include_snapshot=True)
                snapshot = metrics.pop("snapshot")
                post = probe.extract_post(snapshot["html"], rendered_messages=snapshot["messages"],
                                          body_scope_status=metrics["body_scope_status"])
                expected = {metric: saved[f"{metric}_count"] for metric in METRICS}
                mismatches = [metric for metric in METRICS if metrics[f"{metric}_count"] != expected[metric]]
                results.append(dict(sample_id=sample, **metrics, status=post["status"],
                                    expected_counts=expected, mismatches=mismatches,
                                    html_sha256=hashlib.sha256(content_bytes).hexdigest(),
                                    containers=snapshot["containers"]))
                print(sample, [metrics[f"{metric}_count"] for metric in METRICS],
                      metrics["body_scope_status"], post["status"], flush=True)
                page.close()
        finally:
            browser.close()
    coverage = sum(row[f"{metric}_count"] is not None for row in results for metric in METRICS)
    mismatches = sum(len(row["mismatches"]) for row in results)
    report = dict(revision=args.revision or "working_tree", probe_sha256=hashlib.sha256(source).hexdigest(),
                  coverage=coverage, mismatches=mismatches, results=results)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Coverage {coverage}/30; mismatches against saved counts: {mismatches}; report: {args.output}")
    return int(coverage != 30 or mismatches != 0)


if __name__ == "__main__":
    raise SystemExit(main())
