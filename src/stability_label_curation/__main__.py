"""Standard-library storage CLI."""

import argparse
from collections.abc import Mapping, Sequence
import json
import sys

from .paths import check_storage, initialize_storage, resolve_paths
from .data_sources import load_manifest


def main(argv: Sequence[str] | None = None, *, env: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portable project storage")
    commands = parser.add_subparsers(dest="command", required=True)
    paths_parser = commands.add_parser("paths", help="Display resolved storage paths")
    paths_parser.add_argument("--json", action="store_true", help="Emit a JSON object")
    commands.add_parser("doctor", help="Read-only environment checks")
    commands.add_parser("init-storage", help="Create project data and runs directories")
    sources_parser = commands.add_parser("sources", help="Read-only source metadata registry")
    sources_parser.add_argument("--manifest", help="Override the repository TOML manifest")
    source_commands = sources_parser.add_subparsers(dest="source_command", required=True)
    for command in ("list", "validate", "show"):
        subparser = source_commands.add_parser(command)
        subparser.add_argument("--manifest", default=argparse.SUPPRESS,
                               help="Override the repository TOML manifest")
        if command != "validate":
            subparser.add_argument("--json", action="store_true")
        if command == "show":
            subparser.add_argument("source_id")
    args = parser.parse_args(argv)
    try:
        paths = resolve_paths(env)
        if args.command == "sources":
            registry = load_manifest(args.manifest, paths=paths)
            if args.source_command == "validate":
                print(f"OK: schema version {registry.schema_version}; {len(registry.sources)} sources validated (metadata only).")
            elif args.source_command == "show":
                source = registry.get(args.source_id)
                if args.json:
                    print(json.dumps(source.as_dict(), indent=2, sort_keys=True))
                else:
                    for name, value in source.as_dict().items():
                        if value is not None:
                            print(f"{name}: {value}")
            elif args.json:
                print(json.dumps(registry.as_dict(), indent=2, sort_keys=True))
            else:
                for source in registry.list_sources():
                    print(f"{source.source_id}: {source.research_role}; {source.measurement_type}; {source.provenance_status}")
            return 0
        if args.command == "paths":
            if args.json:
                print(json.dumps(paths.as_dict(), indent=2, sort_keys=True))
            else:
                for name, value in paths.as_dict().items():
                    print(f"{name}: {value}")
        elif args.command == "init-storage":
            for path in initialize_storage(paths):
                print(f"Storage ready: {path}")
        else:
            findings = check_storage(paths)
            for severity, message in findings:
                print(f"{severity}: {message}")
            if not findings:
                print("OK: configured directories exist and storage is accessible.")
            return int(any(severity == "ERROR" for severity, _ in findings))
    except (ValueError, OSError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
