# Run manifests

Task 0.4 provides provenance infrastructure only. It does not process scientific
data, download artifacts, train models, probe CUDA, or orchestrate experiments.
Python 3.11+ and local Git are required; all implementation dependencies are in
the standard library. No command needs network access.

## Explicit creation and storage

```sh
PYTHONPATH=src python3 -m stability_label_curation runs create --kind infrastructure --seed 0
PYTHONPATH=src python3 -m stability_label_curation runs list --json
PYTHONPATH=src python3 -m stability_label_curation runs show <run_id> --json
PYTHONPATH=src python3 -m stability_label_curation runs validate <run_id>
```

Replace `<run_id>` with the ID printed by creation. `create` prints the ID and
absolute directory. It creates exactly one new run, plus missing ancestors:

```text
~/codex/runs/stability-label-curation/<run_id>/
├── manifest.json
├── logs/
├── interim/
├── processed/
├── checkpoints/
├── predictions/
├── metrics/
├── figures/
└── reports/
```

Storage is resolved exclusively through `stability_label_curation.paths`.
`CODEX_ROOT` and `CODEX_RUNS_ROOT` retain their existing behavior; a custom runs
root still contains the `stability-label-curation/` project directory. Run output
cannot be in the checkout. Data and runs storage must remain separate.
Imports, metadata construction, lookup, loading, listing, and validation create
no storage directories. Python itself may cache bytecode; use `python3 -B` or
`PYTHONDONTWRITEBYTECODE=1` when interpreter cache writes must also be suppressed.

Optional creation arguments are `--description TEXT`, `--run-id ID`,
`--config FILE`, and repeatable `--input FILE`. A configuration file may be in
the checkout or project data/runs storage; explicit input artifacts must be in
project data/runs storage. Paths are resolved from the invoking working directory
and recorded as absolute paths. Missing files, nonregular files, and paths or
symlinks escaping those boundaries fail. Files from other projects are rejected.
Configuration and inputs are hashed, without being copied or modified.

## IDs and safe publication

Generated IDs use `YYYYMMDDTHHMMSSZ-<24 lowercase hex characters>`: a UTC timestamp
plus 96 random bits. Custom IDs must contain 1–96 ASCII letters, digits, `_` or
`-`, starting with a letter/digit. Windows device names are also rejected.
Slashes, backslashes, dots, traversal, whitespace, control characters, absolute
paths, and other characters are forbidden.

An exclusive `mkdir` reserves each ID. Existing directories, files, and dangling
symlinks are never overwritten. Concurrent requests for the same ID have at most
one successful creator. Directory traversal uses no-follow file descriptors on
macOS/Linux, including while hashing inputs. Run and manifest symlinks are
rejected. A project directory aliased to another project is rejected even when
the path resolver previously resolved that alias. Explicitly configured root
aliases may be resolved by the existing path resolver before use.

Creation writes `.incomplete`, creates the output subdirectories, writes and
fsyncs `.manifest.pending`, then publishes `manifest.json` atomically using a
nonreplacing hard link. It removes only its own pending file and completion marker
after success. Interrupted or failed creation may leave the reserved directory.
Loading rejects a completion marker or missing manifest; listing reports such
directories as `invalid_or_incomplete`. Existing incomplete IDs cannot be reused.
There is no deletion, reset, recovery, or cleanup command. Publication requires
a filesystem supporting ordinary POSIX directory operations and hard links.

`list` inspects only the configured project's immediate run directories. It
skips symlinks and nondirectories and returns a JSON array of summaries. Invalid
directories are reported in that array; they are never accepted as completed
runs. `show` prints the validated manifest (JSON with or without `--json`).
`validate` checks schema and internal evidence consistency, including agreement
between the directory name and manifest ID. It does not rehash inputs, check
historical environment availability, or verify scientific claims. Missing
storage yields an empty list; missing/invalid runs fail with an actionable error.
CLI success is status 0; lookup, safety, provenance, or validation errors are 1.

## Schema version 1

JSON objects have exactly the documented fields; unknown/missing keys, duplicate
JSON keys, invalid types/checksums/timestamps, and unsupported versions are errors.

| Field | Evidence |
| --- | --- |
| `schema_version` | Integer `1` |
| `run_id`, `project_name` | Valid ID and `stability-label-curation` |
| `created_at_utc` | ISO 8601 UTC timestamp ending in `Z` |
| `run_kind`, `description` | Lowercase kind identifier; optional description, otherwise `null` |
| `git` | `repository_name`, full `commit_sha`, `branch` (`null` for detached HEAD), `working_tree_clean`, `git_dirty`, `working_tree_status` |
| `runtime_environment` | Observed `operating_system`, `os_version`, `cpu_architecture`, `python_version`, `python_executable`, `hostname`; `gpu: {"status": "not_collected"}` |
| `configuration` | `file` (`null` or `{path, sha256}`), `random_seed` (integer or `null`), actual creation `argv` |
| `data_provenance` | `data_source_manifest: {path, sha256}` and `input_artifacts: [{path, sha256}, ...]` |
| `external_repositories` | Initially `[]`; future entries require `repository_name`, full `commit_sha`, `branch` (nullable) |
| `reproducibility` | `status`, boolean `canonical`, `warnings`, and explicit `limitations` |

The registry path is always `configs/data_sources.toml`. Its SHA256 is calculated
from `git show <recorded commit>:configs/data_sources.toml`, so it identifies
the actual committed registry bytes even under `--allow-dirty`. An uncommitted
registry edit is captured in dirty Git status; its modified bytes are not
represented by this committed-registry checksum. If the edited file is also
explicitly selected with `--config`, that separate checksum covers working bytes.
Missing committed registry metadata fails; no placeholder SHA is substituted.

Explicit configuration/input SHA256 values are lowercase hex digests of actual
file bytes, read in 1 MiB chunks. Size/mtime/ctime changes during hashing cause
failure. No recursive dataset hashing occurs. No supplied inputs means `[]`;
no supplied seed or configuration means `null`. External commit hashes and GPU
specifications are never fabricated. The manifest records the creation command,
which is infrastructure evidence rather than a future training command.

## Git cleanliness and reproducibility limits

Canonical creation requires a committed HEAD and clean working tree, including
staged, unstaged, and nonignored untracked files. Git status is captured with
optional index writes disabled. Git commit/branch/status are checked again after
metadata capture to detect changes. Do not modify the checkout while creating a run.

`--allow-dirty` is an explicit development override. It records `git_dirty: true`,
the NUL-delimited porcelain status entries (including rename paths),
`status: "dirty_development"`, `canonical: false`, and a warning in both the
manifest and CLI stderr. Non-UTF-8 Git names are escaped for JSON evidence.
Clean creation records `status: "clean_committed"`, `canonical: true`, and no
dirty warnings. Dirty runs do not snapshot patches or untracked contents.

Every manifest states that evidence does not guarantee bitwise-identical reruns.
This minimal version does not capture package inventories, lockfiles, Git diffs,
input/configuration copies, GPU details, kernel determinism, or execution results.
Checksums identify bytes but do not preserve their availability. Inputs must
remain stable while hashing and be retained separately. Absolute evidence paths
must be mapped to equivalent project storage on another machine. Sudden power
loss and hostile simultaneous filesystem manipulation are outside the recovery
contract; no automatic recovery or deletion is attempted.

The implementation targets macOS and Linux/WSL2 using Linux Python and local
Linux paths on WSL2. macOS validation does not establish execution on WSL2, GPU,
CUDA, Windows Python, or every mounted filesystem.

## Integration for future authorized experiments

The APIs are `generate_run_id`, `validate_run_id`, `capture_git_provenance`,
`capture_runtime_environment`, `sha256_file`, `build_manifest`, `create_run`,
`lookup_run`, `load_manifest`, `validate_manifest`, and `list_runs` in
`stability_label_curation.run_manifest`. Functions accept the existing resolved
`StoragePaths` where applicable. `build_manifest` and `create_run` require an
explicit `kind` and `argv`; seed, description, configuration, inputs and dirty
override remain optional. `create_run` returns the reserved `Path` and always
constructs its own provenance rather than accepting an arbitrary manifest.

Future training scripts should resolve paths, explicitly create one canonical
run with the actual invocation/configuration/seed and selected input artifacts,
then write only to the appropriate subdirectories of that returned run. Pass the
actual training argv when calling the API directly. Do not silently create a new
run on import or during inspection, change recorded evidence after execution,
invent a seed, or reuse an existing ID. External repository commits and dependency
evidence should be added through a separately authorized schema/integration task.
These instructions do not authorize training or any Task 0.5 work.
