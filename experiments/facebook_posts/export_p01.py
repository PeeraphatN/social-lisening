"""Export the existing P01 result without making another network request."""

import csv
import json
from pathlib import Path


root = Path(__file__).resolve().parent / "runs"
source = json.loads((root / "p01-browser-inspection.json").read_text(encoding="utf-8"))
record = {key: source.get(key) for key in
          ("status", "publisher_metadata", "text", "preview_text", "published_at",
           "collected_at", "resolved_url", "manual_match")}
record.update(input_url="https://www.facebook.com/share/p/19TTvcsmZ8/",
              authenticated=False, method="anonymous_playwright",
              displayed_time_raw="15 ชั่วโมงที่แล้ว")
(root / "p01-post.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
(root / "p01-post.txt").write_text(record["text"], encoding="utf-8")
with (root / "p01-post.csv").open("w", encoding="utf-8-sig", newline="") as file:
    writer = csv.DictWriter(file, fieldnames=list(record))
    writer.writeheader()
    writer.writerow(record)
with (root / "p01-post.csv").open(encoding="utf-8-sig", newline="") as file:
    exported = list(csv.DictReader(file))
assert len(exported) == 1 and exported[0]["text"] == record["text"]
print(f"Exported 1 post, {len(record['text'])} characters; UTF-8 CSV checked")
