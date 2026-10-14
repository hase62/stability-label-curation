"""Standard-library storage CLI."""

import argparse
import csv
from http.client import HTTPException
from collections.abc import Mapping, Sequence
import json
import sys
import zipfile

from .paths import check_storage, initialize_storage, resolve_paths
from .data_sources import load_manifest
from . import run_manifest
from . import netmhcstabpan_2016 as dtu2016
from . import dtu2016_source_audit as source_audit
from . import spearmint_overlap_audit as spearmint
from . import netmhcstab_historical_evidence as historical
from . import jappe_2020_sources as jappe
from . import jappe_2020_row_audit as jappe_rows
from . import jappe_2020_figure_audit as jappe_figures
from . import observation_registry as observations


def main(argv: Sequence[str] | None = None, *, env: Mapping[str, str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Portable project storage")
    commands = parser.add_subparsers(dest="command", required=True)
    paths_parser = commands.add_parser("paths", help="Display resolved storage paths")
    paths_parser.add_argument("--json", action="store_true", help="Emit a JSON object")
    commands.add_parser("doctor", help="Read-only environment checks")
    commands.add_parser("init-storage", help="Create project data and runs directories")
    dtu_parser = commands.add_parser("dtu2016", help="DTU 2016 raw acquisition and read-only inventory")
    dtu_commands = dtu_parser.add_subparsers(dest="dtu_command", required=True)
    fetch_parser = dtu_commands.add_parser("fetch", help="Acquire official raw bytes or identify existing artifact")
    fetch_parser.add_argument("--timeout", type=float, default=30, help="Finite connection/read timeout in seconds")
    fetch_parser.add_argument("--receipt", help="Explicit JSON receipt destination under project runs")
    inspect_parser = dtu_commands.add_parser("inspect", help="Offline, read-only structural inventory")
    inspect_parser.add_argument("--input", help="Local input override; never downloads")
    inspect_parser.add_argument("--json", action="store_true")
    inspect_parser.add_argument("--report", help="Explicit JSON report destination under project runs")
    audit_parser = dtu_commands.add_parser("audit", help="Offline checksum-gated source evidence and zero-value audit")
    audit_parser.add_argument("--json", action="store_true", help="Print complete JSON audit reports (row flags available through reports directory)")
    audit_parser.add_argument("--input", help="Explicit local input override; never downloads")
    audit_parser.add_argument("--expected-sha256", help="Explicit local-input identity; requires --input; default is pinned Task 1.1 hash")
    audit_parser.add_argument("--evidence", help="Offline evidence-register JSON override")
    audit_parser.add_argument("--reports-dir", help="Write complete reports and row flags to an existing project run reports directory")
    spearmint_parser = commands.add_parser("spearmint", help="Offline pinned Stage 2/DTU provenance and overlap audit")
    spearmint_commands = spearmint_parser.add_subparsers(dest="spearmint_command", required=True)
    overlap_parser = spearmint_commands.add_parser("audit")
    overlap_parser.add_argument("--json", action="store_true")
    overlap_parser.add_argument("--checkout", help="Read-only pinned external checkout override")
    for split in ("train", "val", "test"):
        overlap_parser.add_argument("--" + split, help="Explicit pinned split CSV path")
    overlap_parser.add_argument("--mapping", help="Explicit pinned allele/sequence reference CSV")
    overlap_parser.add_argument("--lock", help="External repository lockfile override for offline fixtures")
    overlap_parser.add_argument("--evidence", help="Stage 2 evidence JSON override")
    overlap_parser.add_argument("--dtu", help="Local DTU-format input override")
    overlap_parser.add_argument("--expected-dtu-sha256", help="Requires --dtu; independently pinned local fixture identity")
    overlap_parser.add_argument("--reports-dir", help="Explicit existing project run reports directory")
    historical_parser = commands.add_parser("historical", help="Offline historical NetMHCstab evidence audit")
    historical_commands = historical_parser.add_subparsers(dest="historical_command", required=True)
    historical_audit = historical_commands.add_parser("audit")
    historical_audit.add_argument("--json", action="store_true")
    historical_audit.add_argument("--evidence", help="Captured offline evidence register override")
    historical_audit.add_argument("--dtu", help="Local immutable DTU input override")
    historical_audit.add_argument("--expected-dtu-sha256", help="Requires --dtu; pinned fixture identity")
    historical_audit.add_argument("--secondary", help="Explicit pinned TLStab secondary score CSV override")
    historical_audit.add_argument("--reports-dir", help="Write reports into an existing project run")
    jappe_parser = commands.add_parser("jappe2020", help="Allowlisted publisher acquisition and offline workbook inventory")
    jappe_commands = jappe_parser.add_subparsers(dest="jappe_command", required=True)
    jappe_fetch = jappe_commands.add_parser("fetch")
    jappe_fetch.add_argument("--artifact", action="append", choices=jappe.ARTIFACT_IDS, help="Select authorized artifacts; defaults to all four")
    jappe_fetch.add_argument("--timeout", type=float, default=30)
    jappe_fetch.add_argument("--receipt", help="Explicit receipt JSON destination under project runs")
    jappe_inventory = jappe_commands.add_parser("inventory")
    jappe_inventory.add_argument("--json", action="store_true")
    jappe_inventory.add_argument("--file", action="append", default=[], metavar="ARTIFACT_ID=PATH", help="Explicit local artifact override, repeatable")
    jappe_inventory.add_argument("--reports-dir", help="Explicit existing project run reports directory")
    jappe_audit = jappe_commands.add_parser("audit", help="Offline checksum-gated field semantics and paired-context audit")
    jappe_audit.add_argument("--json", action="store_true")
    jappe_audit.add_argument("--file", action="append", default=[], metavar="ARTIFACT_ID=PATH")
    jappe_audit.add_argument("--expected-sha256", action="append", default=[], metavar="ARTIFACT_ID=SHA256", help="Explicit fixture identity; requires matching --file")
    jappe_audit.add_argument("--evidence", help="Captured offline row evidence register")
    jappe_audit.add_argument("--reports-dir", help="Explicit existing project run reports directory")
    figure_fetch = jappe_commands.add_parser("figure-fetch", help="Acquire only the 5 MiB-capped official Source Data workbook")
    figure_fetch.add_argument("--timeout", type=float, default=30)
    figure_fetch.add_argument("--receipt", help="Explicit acquisition receipt destination under project runs")
    figure_audit = jappe_commands.add_parser("figure-audit", help="Offline Source Data population audit using approved Task 1.6 evidence")
    figure_audit.add_argument("--json", action="store_true")
    figure_audit.add_argument("--source-data", help="Explicit local Source Data workbook")
    figure_audit.add_argument("--approved-ledger", help="Approved Task 1.6 ledger override")
    figure_audit.add_argument("--approved-context-report", help="Approved Task 1.6 context report override")
    figure_audit.add_argument("--expected-sha256", action="append", default=[], metavar="INPUT_ID=SHA256")
    figure_audit.add_argument("--evidence", help="Offline source evidence register")
    figure_audit.add_argument("--reports-dir", help="Explicit existing project run reports directory")
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
    registry_parser = commands.add_parser("registry", help="Offline canonical observation and derived-lineage registry")
    registry_commands = registry_parser.add_subparsers(dest="registry_command", required=True)
    for name in ("validate", "build"):
        registry_command = registry_commands.add_parser(name)
        registry_command.add_argument("--json", action="store_true")
        registry_command.add_argument("--lock", help="Portable pinned registry configuration; explicit fixture expectations")
        registry_command.add_argument("--input", action="append", default=[], metavar="INPUT_ID=PATH")
        if name == "build":
            registry_command.add_argument("--output-dir", required=True, help="Explicit existing project run reports directory")
    runs_parser = commands.add_parser("runs", help="Run provenance and explicit creation")
    run_commands = runs_parser.add_subparsers(dest="run_command", required=True)
    create_parser = run_commands.add_parser("create", help="Create one run from committed code")
    create_parser.add_argument("--kind", required=True)
    create_parser.add_argument("--seed", type=int)
    create_parser.add_argument("--description")
    create_parser.add_argument("--run-id")
    create_parser.add_argument("--allow-dirty", action="store_true")
    create_parser.add_argument("--config", help="Configuration in checkout or project data/runs")
    create_parser.add_argument("--input", action="append", default=[], help="Explicit project data/runs file; repeatable")
    for command in ("list", "show", "validate"):
        subparser = run_commands.add_parser(command)
        if command != "list":
            subparser.add_argument("run_id")
        if command != "validate":
            subparser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        paths = resolve_paths(env)
        if args.command == "registry":
            files = {}
            for item in args.input:
                key, separator, value = item.partition("=")
                if not separator or not value or key in files:
                    raise ValueError("--input requires a unique INPUT_ID=PATH")
                files[key] = value
            result = observations.build(paths=paths, files=files, lock_path=args.lock)
            if args.registry_command == "build":
                observations.write_registry(result, args.output_dir, paths=paths)
            document = result.reports if args.json else result.reports['registry_validation_summary.json']
            print(dtu2016.json_report(document), end="")
            return 0
        if args.command == "jappe2020":
            if args.jappe_command == "figure-fetch":
                document = jappe_figures.fetch(paths=paths, timeout=args.timeout)
                if args.receipt:
                    dtu2016.write_report(args.receipt, document, paths=paths)
                print(dtu2016.json_report(document), end="")
                return 0
            if args.jappe_command == "figure-audit":
                hashes = {}
                for item in args.expected_sha256:
                    key, separator, value = item.partition("=")
                    if not separator or not value or key in hashes:
                        raise ValueError("--expected-sha256 requires a unique INPUT_ID=SHA256")
                    hashes[key] = value
                result = jappe_figures.audit(paths=paths, source_path=args.source_data,
                    ledger_path=args.approved_ledger, context_report_path=args.approved_context_report,
                    expected_sha256=hashes, evidence_path=args.evidence)
                if args.reports_dir:
                    jappe_figures.write_reports(result, args.reports_dir, paths=paths)
                print(dtu2016.json_report(result.reports if args.json else result.reports['jappe_figure_population_reconciliation.json']), end="")
                return 0
            if args.jappe_command == "fetch":
                document = jappe.fetch(paths=paths, artifacts=args.artifact, timeout=args.timeout)
                if args.receipt:
                    dtu2016.write_report(args.receipt, document, paths=paths)
            else:
                files = {}
                for item in args.file:
                    identifier, separator, value = item.partition("=")
                    if not separator or not value or identifier in files:
                        raise ValueError("--file requires a unique ARTIFACT_ID=PATH")
                    files[identifier] = value
                if args.jappe_command == "audit":
                    hashes = {}
                    for item in args.expected_sha256:
                        identifier, separator, value = item.partition("=")
                        if not separator or not value or identifier in hashes:
                            raise ValueError("--expected-sha256 requires a unique ARTIFACT_ID=SHA256")
                        hashes[identifier] = value
                    result = jappe_rows.audit(paths=paths,files=files,expected_sha256=hashes,evidence_path=args.evidence)
                    if args.reports_dir:
                        jappe_rows.write_reports(result,args.reports_dir,paths=paths)
                    document = result.reports if args.json else result.reports['jappe_measurement_inventory.json']
                else:
                    document = jappe.inventory(paths=paths, files=files)
                    if args.reports_dir:
                        jappe.write_inventory(document, args.reports_dir, paths=paths)
            print(dtu2016.json_report(document), end="")
            return int(bool(document.get('errors')))
        if args.command == "historical":
            if args.expected_dtu_sha256 and not args.dtu:
                raise ValueError("--expected-dtu-sha256 requires --dtu")
            reports = historical.audit(paths=paths, evidence_path=args.evidence,
                dtu_path=args.dtu, expected_dtu_sha256=args.expected_dtu_sha256 or source_audit.TASK11_LOCAL_SHA256,
                secondary_path=args.secondary)
            if args.reports_dir:
                historical.write_reports(reports, args.reports_dir, paths=paths)
            print(dtu2016.json_report(reports if args.json else reports['conditional_row_overlap_summary.json']), end="")
            return 0
        if args.command == "spearmint":
            if args.expected_dtu_sha256 and not args.dtu:
                raise ValueError("--expected-dtu-sha256 requires explicit --dtu")
            result = spearmint.audit(paths=paths, checkout=args.checkout,
                files={s: getattr(args, s) for s in spearmint.SPLITS if getattr(args, s)},
                mapping=args.mapping, dtu_path=args.dtu,
                expected_dtu_sha256=args.expected_dtu_sha256 or source_audit.TASK11_LOCAL_SHA256,
                lock_path=args.lock, evidence_path=args.evidence)
            if args.reports_dir:
                spearmint.write_reports(result, args.reports_dir, paths=paths)
            document = result.reports if args.json else {k: v for k, v in result.summary().items() if k != "per_allele"}
            print(dtu2016.json_report(document), end="")
            return 0
        if args.command == "dtu2016":
            if args.dtu_command == "audit":
                if args.expected_sha256 and not args.input:
                    raise ValueError("--expected-sha256 requires an explicit --input")
                evidence = source_audit.load_evidence(args.evidence, paths=paths)
                result = source_audit.audit(args.input, paths=paths, evidence=evidence,
                    expected_sha256=args.expected_sha256 or source_audit.TASK11_LOCAL_SHA256)
                if args.reports_dir:
                    source_audit.write_audit(result, args.reports_dir, paths=paths)
                print(dtu2016.json_report(result.reports if args.json else result.summary()), end="")
                return 0
            if args.dtu_command == "fetch":
                document = dtu2016.fetch(paths=paths, timeout=args.timeout)
                destination = args.receipt
            else:
                source = load_manifest(paths=paths).get(dtu2016.SOURCE_ID)
                document = dtu2016.inventory(args.input or source.target_path(paths), source=source)
                destination = args.report
            if destination:
                dtu2016.write_report(destination, document, paths=paths)
            # JSON is the compact reproducible interface, also the default text form.
            print(dtu2016.json_report(document), end="")
            return 0
        if args.command == "runs":
            if args.run_command == "create":
                target = run_manifest.create_run(
                    paths=paths, run_id=args.run_id, kind=args.kind, seed=args.seed,
                    description=args.description, config=args.config, inputs=args.input,
                    allow_dirty=args.allow_dirty,
                    argv=list(sys.orig_argv) if argv is None else [sys.executable, "-m", "stability_label_curation", *argv],
                )
                manifest = run_manifest.load_manifest(target.name, paths=paths)
                for warning in manifest["reproducibility"]["warnings"]:
                    print(f"WARNING: {warning}", file=sys.stderr)
                print(f"Run created: {target.name}\nPath: {target}")
            elif args.run_command == "list":
                runs = run_manifest.list_runs(paths=paths)
                if args.json:
                    print(json.dumps(runs, indent=2, sort_keys=True))
                else:
                    for run in runs:
                        print(f"{run['run_id']}: {run['status']}; {run.get('reproducibility', {}).get('status', run.get('error', ''))}")
            else:
                manifest = run_manifest.load_manifest(args.run_id, paths=paths)
                if args.run_command == "validate":
                    print(f"OK: {args.run_id}; schema version {manifest['schema_version']}; "
                          f"{manifest['reproducibility']['status']} (schema/evidence consistency only).")
                else:
                    print(json.dumps(manifest, indent=2, sort_keys=True))
            return 0
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
    except (ValueError, OSError, RuntimeError, HTTPException, csv.Error, zipfile.BadZipFile) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
