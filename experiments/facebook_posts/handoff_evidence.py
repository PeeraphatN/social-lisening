"""Export or import a selected Facebook evidence bundle."""

import argparse
import json

from evidence_bundle import export_bundle, import_bundle


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    export = commands.add_parser("export")
    export.add_argument("--root", required=True)
    export.add_argument("--output", required=True)
    export.add_argument("--source-commit", required=True)
    export.add_argument("--source-session")
    export.add_argument("files", nargs="+")

    incoming = commands.add_parser("import")
    incoming.add_argument("--bundle", required=True)
    incoming.add_argument("--destination", required=True)
    incoming.add_argument("--expected-source-commit")

    args = parser.parse_args()
    if args.command == "export":
        result = export_bundle(args.root, args.output, args.source_commit,
                               args.files, source_session=args.source_session)
    else:
        result = import_bundle(args.bundle, args.destination, args.expected_source_commit)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
