"""Inspect one public post in an anonymous browser; do not log in."""

import argparse
import csv
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

from probe_post import extract_post, extract_social_metrics, validate_url


root = Path(__file__).resolve().parent
os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(root / ".playwright")
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("url", nargs="?", type=validate_url,
                    default="https://www.facebook.com/share/p/19TTvcsmZ8/")
parser.add_argument("--run-id", default="p01-browser")
args = parser.parse_args()
if not args.run_id.replace("-", "").replace("_", "").isalnum():
    parser.error("run-id must contain only letters, digits, hyphens or underscores")
url = args.url
output = root / "runs"
output.mkdir(exist_ok=True)

started = time.monotonic()
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 1000})
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
        validate_url(page.url)
        try:
            page.locator('[data-ad-rendering-role="story_message"]').first.wait_for(timeout=15000)
        except PlaywrightTimeout:
            pass
        body_text = page.locator("body").inner_text()
        result = extract_post(page.content())
        result.update(
            collected_at=datetime.now(timezone.utc).isoformat(),
            method="anonymous_browser_inspection",
            authenticated=False,
            resolved_url=page.url,
            http_status=response.status if response else None,
            dom_message_count=page.locator('[data-ad-rendering-role="story_message"]').count(),
            dom_messages=page.locator('[data-ad-rendering-role="story_message"]').all_inner_texts(),
            body_preview=body_text[:1800],
            duration_seconds=round(time.monotonic() - started, 3),
            text_sha256=hashlib.sha256((result.get("text") or "").encode("utf-8")).hexdigest() if result.get("text") else None,
        )
        result.update(extract_social_metrics(body_text))
        page.screenshot(path=str(output / f"{args.run_id}.png"))
        (output / f"{args.run_id}-inspection.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        record = {key: result.get(key) for key in
                  ("status", "publisher_metadata", "text", "preview_text",
                   "published_at", "collected_at", "resolved_url", "manual_match",
                   "duration_seconds", "text_sha256", "reaction_count", "comment_count",
                   "share_count", "reaction_text_raw", "comment_text_raw", "share_text_raw")}
        record.update(input_url=url, authenticated=False, method="anonymous_playwright")
        with (output / f"{args.run_id}.csv").open("w", encoding="utf-8-sig", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(record))
            writer.writeheader()
            writer.writerow(record)
        if record["text"]:
            (output / f"{args.run_id}.txt").write_text(record["text"], encoding="utf-8")
        print(json.dumps({key: result[key] for key in
                          ("status", "http_status", "dom_message_count")},
                         ensure_ascii=True))
    finally:
        browser.close()
