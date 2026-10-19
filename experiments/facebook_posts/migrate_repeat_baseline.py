"""Convert a local legacy references.json into the tracked hash-only baseline."""

import argparse
import json
from pathlib import Path

from repeat_baseline import migrate_legacy


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("legacy", type=Path, help="legacy references.json containing reviewed text")
    parser.add_argument("output", type=Path, help="new hash-only baseline path")
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"output already exists: {args.output}")
    legacy = json.loads(args.legacy.read_text(encoding="utf-8"))
    baseline = migrate_legacy(legacy)
    args.output.write_text(json.dumps({"schema_version": 1, "samples": baseline["samples"]},
                                      ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
