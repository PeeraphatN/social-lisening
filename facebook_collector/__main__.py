"""Command-line entry point for the Facebook post collector."""

import argparse
from pathlib import Path
import sys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="facebook_collector")
    commands = parser.add_subparsers(dest="command", required=True)
    collect = commands.add_parser("collect")
    input_mode = collect.add_mutually_exclusive_group(required=True)
    input_mode.add_argument("--url", action="append")
    input_mode.add_argument("--input-file")
    collect.add_argument("--output-dir", required=True)
    collect.add_argument("--log", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    from facebook_collector.offline import offline_enabled

    if offline_enabled() and (arguments.input_file or len(arguments.url) != 1):
        print("offline mode accepts exactly one --url", file=sys.stderr)
        return 2
    if arguments.input_file:
        try:
            lines = Path(arguments.input_file).read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeError):
            print("collection failed: cannot read input file", file=sys.stderr)
            return 1
        inputs = [line for line in lines if line.strip()]
    else:
        inputs = arguments.url

    from facebook_collector import CollectionUnavailable, collect_posts
    from facebook_collector.model import BatchValidationError
    from facebook_collector.offline import OfflineCaptureError

    try:
        collect_posts(inputs, Path(arguments.output_dir), log=arguments.log)
    except BatchValidationError as error:
        print(str(error), file=sys.stderr)
        return 2
    except OfflineCaptureError as error:
        print(f"offline collection failed: {error}", file=sys.stderr)
        return 1
    except CollectionUnavailable as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, TypeError, ValueError):
        print("collection failed: cannot write trustworthy output", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
