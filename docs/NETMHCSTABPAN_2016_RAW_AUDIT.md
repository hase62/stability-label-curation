# NetMHCstabpan 2016 raw acquisition and inventory (Task 1.1)

This workflow acquires one original artifact and inventories its structure. It
creates no training table, transformations, row labels, filtering, or models.
All original bytes, values, and ordering remain in the external raw file.

## Source and published expectations

The authoritative configuration is `configs/data_sources.toml`, source ID
`netmhcstabpan_2016`. No registry correction was required for Task 1.1.

- [Official DTU supplementary landing page](https://services.healthtech.dtu.dk/suppl/immunology/NetMHCstabpan-1.0/)
- [Original Stability.txt](https://services.healthtech.dtu.dk/suppl/immunology/NetMHCstabpan-1.0/Stability.txt)
- [Rasmussen et al., Journal of Immunology, 2016](https://doi.org/10.4049/jimmunol.1600582)
- [Open author manuscript](https://pmc.ncbi.nlm.nih.gov/articles/PMC4976001/)

DTU identifies three columns, `HLA Pep Thalf`. The publication reports 28,166
observations and 75 HLA molecules; these are expectations, separate from local
inventory counts. `Thalf` is pMHC-I kinetic half-life in hours, separate from Tm.
The reported external observation of 28,167 lines including the header must be
checked locally, rather than accepted as a local result.

The paper describes a separate training augmentation of 1,000 random natural
9-mers per allele selected for predicted affinity weaker than 20,000 nM, with
artificial half-life zero. Its description does not establish which, if any,
downloadable rows are augmentation. A zero does not establish synthetic origin;
a positive number does not independently establish an experimental measurement.
The registry remains `row_audit_required`. Task 1.1 supplies structural evidence,
not a row-level scientific classification or immunogenicity labels.

## Storage and commands

Run from the source checkout using Python 3.11+. The paths module resolves
storage and its existing environment overrides. The registered target is
`netmhcstabpan_2016/Stability.txt` beneath project data, defaulting to
`~/codex/data/stability-label-curation/netmhcstabpan_2016/Stability.txt`.
Never redirect the dataset into the checkout.

```sh
PYTHONPATH=src python3 -B -m stability_label_curation paths --json
PYTHONPATH=src python3 -B -m stability_label_curation dtu2016 fetch
PYTHONPATH=src python3 -B -m stability_label_curation dtu2016 inspect --json
```

Only `fetch` opens the network. It prints a JSON receipt. Preserve that output
when doing the real acquisition; existing-file reuse cannot reconstruct original
retrieval metadata. Existing bytes are hashed and retained, with no network
comparison against the current DTU artifact. Different bytes require separate
authorization to replace. There is no force/overwrite option.

Offline inspection accepts any explicitly supplied regular, non-symlink file:

```sh
PYTHONPATH=src python3 -B -m stability_label_curation dtu2016 inspect \
  --input "$HOME/codex/data/stability-label-curation/netmhcstabpan_2016/Stability.txt" --json
```

Inspect prints deterministic JSON and performs no writes. Use `-B` to suppress
Python's own bytecode caching. Only an explicit `--report PATH` writes a report;
its parent must already exist under project runs. `fetch --receipt PATH` has the
same report safety rules. Neither report option overwrites existing files.

## Byte-level receipt and safeguards

Acquisition uses certificate-verifying HTTPS and rejects insecure or non-DTU
redirects, credentials, and unexpected content encoding. A positive finite
`--timeout` (default 30 seconds) sets the socket connection/read-operation
timeout; it is not a deadline for the complete download. Response reads are
bounded to 1 MiB. A unique partial file is fsynced before atomic nonreplacing
hard-link publication. Failures remove only that invocation's partial file.
Parent directories and files are opened with no-follow descriptors; traversal,
project directory aliases, and symlink escapes are rejected. No credentials or
sensitive request headers are recorded. The local filesystem must support POSIX
no-follow directory descriptors and ordinary hard links.

The receipt includes source ID, official and resolved URLs, UTC completion time,
status, server Content-Length/ETag/Last-Modified, filename, acquisition versus
reuse, local size and SHA256, validation scope, and limitations. For reuse,
unknown original HTTP metadata and retrieval time are explicitly null. A local
checksum verifies byte identity only. The registry has no publisher reference
checksum; no local hash is promoted into that registry field. HTTP metadata is
server-reported evidence, not independent verification. HTTP 200 does not certify
scientific validity; inventory validation is a separate operation.

## Inventory semantics

The file is hashed without normalization and read with physical source line
numbers starting at 1. LF, CRLF, and CR line endings and whitespace delimiters
are supported. The first line is compared to the registered column names. An
unrecognized first line is also inspected as data, avoiding silent row loss.
Empty files and mismatched headers are flagged. Surrogate-escaped undecodable
bytes remain traceable and are reported as unexpected field characters.

`parse_record` returns immutable original allele/peptide/half-life strings, raw
line including its ending, source line number, exact Decimal value where valid,
and numeric issue. `iter_records` provides offline traceability, raising for
incorrect column counts; `inventory` flags those rows and continues. No fields
are normalized. Structurally parsed observations include three-column rows with
invalid numbers. Malformed lines include incorrect column counts and invalid,
missing-token, or non-finite numeric values; the latter overlap parsed counts.
Two-column lines additionally count as missing half-life. Blank lines are counted
separately. Scientific eligibility is never inferred from these counts.

The report contains size/hash, line/header evidence, observations and allele
counts, locus A/B/C/other observation counts, counts per original allele and
peptide length, 9-mer fraction, exact zero/positive/negative counts, missing and
non-numeric/non-finite counts, finite minimum/maximum as decimal strings, and
published-versus-observed comparisons. Unexpected identifiers are those outside
the documented human `HLA-[ABC]*NN:NN` syntax (two to four numeric fields of two
or three digits and an optional expression suffix). This is syntax recognition,
not an allele-database validation. Peptide characters outside uppercase
`ACDEFGHIKLMNPQRSTVWY` are flagged with line numbers; none are replaced.

Duplicate categories use all three-column records, including numeric anomalies:

- **Repeated key:** original `(HLA, peptide)` occurs on multiple source lines.
  Report counts distinct repeated keys and lists all associated line numbers.
- **Exact duplicate record:** all three original field strings match. Report
  group count and excess occurrences beyond the first. Whitespace differences
  do not change field identity; half-life text `1` and `1.00` differs.
- **Identical raw line:** data line text, excluding its line ending, matches.
  This separate count distinguishes textual equality from field equality.
- **Conflicting repeat:** a repeated key has multiple different valid Decimal
  half-lives; `1` and `1.00` are numerically equal. Invalid values remain flagged
  and do not create a numeric conflict by themselves.
- **Cross-allele peptide:** an original peptide string occurs under multiple
  different original HLA strings. Report distinct peptides and their alleles.

Repeated measurements are not assumed to be accidental file duplication. No
records are deduplicated, averaged, filtered, or relabeled. A structural pass
still does not prove experimental measurement status.

## Canonical run after committing implementation

The existing `runs create --help` supports `--input` (repeatable), `--config`,
`--kind`, `--description`, and `--run-id`. It can explicitly hash the raw input;
no run schema change or fabricated input record is needed. One canonical run
can associate that hash with reports written beneath its `reports` directory.
The manifest records creation, not execution completion or report checksums;
a separate association report can record those checksums without editing it.

For a normal macOS terminal, after committing and confirming a clean checkout,
the following captures the first acquisition receipt before creating a run.
Paths are resolved through the project API, including configured overrides.
Do not run again after an already successful canonical execution.

```sh
PYTHONPATH=src python3 -B - <<'PY'
import sys
from stability_label_curation.paths import resolve_paths
from stability_label_curation import netmhcstabpan_2016 as dtu
from stability_label_curation import run_manifest as runs

paths = resolve_paths()
runs.capture_git_provenance(paths.repository_root)  # Require clean committed code first.
receipt = dtu.fetch(paths=paths)
print(dtu.json_report(receipt), end='', flush=True)  # Preserve in terminal even if run creation fails.
raw = receipt['raw_path']
report = dtu.inventory(raw)
if report['sha256'] != receipt['local_sha256']:
    raise ValueError('Raw bytes changed between acquisition and inventory')
run = runs.create_run(paths=paths, kind='data_acquisition_inventory',
    description='Task 1.1: original DTU 2016 bytes and structural inventory',
    inputs=[raw], argv=list(sys.orig_argv))
dtu.write_report(run / 'reports' / 'acquisition_receipt.json', receipt, paths=paths)
dtu.write_report(run / 'reports' / 'source_inventory.json', report, paths=paths)
association = {'source_id': dtu.SOURCE_ID, 'run_id': run.name,
    'raw_sha256': receipt['local_sha256'],
    'reports': {name: dtu.sha256_file(run / 'reports' / name)
                for name in ('acquisition_receipt.json', 'source_inventory.json')}}
dtu.write_report(run / 'reports' / 'artifact_association.json', association, paths=paths)
print(f'Run: {run.name}\nManifest: {run / "manifest.json"}')
runs.load_manifest(run.name, paths=paths)
PY
```

Run this only with authorized network/storage access. Sandbox failure is a
pending real acquisition, never evidence that the expected rows were inspected.
Do not change sandbox settings, install networking workarounds, or substitute
synthetic test success for a real inventory.

## Validation and Task 1.2 boundary

```sh
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
```

Tests use only small temporary synthetic fixtures and mocked HTTP responses.
They cover preservation, Decimal validation, distributions/repeats, checksums,
read-only offline behavior, deterministic reports, download failures, atomic
non-overwrite, symlink/traversal safeguards, and existing CLI functionality.
macOS validation does not establish WSL2/GPU execution.

Task 1.2 must investigate row-level assay and provenance evidence, zero-value
interpretation, synthetic augmentation membership if any, repeated measurements,
any length/count contradictions, assay conditions/censoring, license scope, and
potential historical overlap. These questions remain unresolved here. Task 1.1
authorizes no subsequent data acquisition, row exclusion, label assignment,
transformation, training, or evaluation.
