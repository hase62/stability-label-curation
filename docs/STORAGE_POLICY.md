# Storage contract

The portable layout is `~/codex/data/`, `~/codex/repos/`, and `~/codex/runs/`.
Each contains a project directory named `stability-label-curation`.

| Location | Contract |
| --- | --- |
| `data/stability-label-curation/` | Large external inputs and public model weights; eventually recoverable through version-controlled download instructions. |
| `repos/stability-label-curation/` | Git-managed source, small configuration, documentation, and tests. |
| `runs/stability-label-curation/` | Derived data, checkpoints, predictions, logs, metrics, and reproducible outputs; eventually regenerable from code, configuration, seeds, and downloaded inputs. |

Never store large datasets, weights, checkpoints, or derived experiment outputs in the repository. Download instructions and run reproducibility records will be added in later authorized tasks; this foundation creates no datasets or experiment files.

## Resolution and overrides

| Variable | Default |
| --- | --- |
| `CODEX_ROOT` | `Path.home() / "codex"` |
| `CODEX_DATA_ROOT` | `CODEX_ROOT / "data"` |
| `CODEX_REPOS_ROOT` | `CODEX_ROOT / "repos"` |
| `CODEX_RUNS_ROOT` | `CODEX_ROOT / "runs"` |

Explicit overrides take precedence independently, including when `CODEX_ROOT` is also set.
An unset variable uses its default; an empty or relative override is an error.
Paths expand `~`, normalize `..`, and resolve existing symlinks. Use absolute paths
or `~/...`; overrides are never interpreted relative to the shell's working directory.
Other environment-variable references embedded in values are not expanded by the resolver.

The current repository root is derived from the package's location in this source
checkout, independently of `CODEX_REPOS_ROOT`. Run the CLI from the source checkout
with `PYTHONPATH=src`; relocating the checkout needs no source edits. A copied or
installed package does not discover a separate Git checkout automatically.

The typed `resolve_paths(env=None, *, home=None, repository_root=None)` API accepts
an injected environment mapping and test locations. It returns immutable `StoragePaths`.
Imports and resolution perform no writes or directory creation. Data/runs roots and
project targets inside the repository are rejected, including symlink destinations.
Project data/runs must be separate, non-nested directories and must not contain the repository.

## Commands

From the checkout, using Python 3.11 or later:

```sh
PYTHONPATH=src python3 -m stability_label_curation paths
PYTHONPATH=src python3 -m stability_label_curation paths --json
PYTHONPATH=src python3 -m stability_label_curation doctor
PYTHONPATH=src python3 -m stability_label_curation init-storage
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

An override example, suitable for either environment:

```sh
export CODEX_ROOT="$HOME/research-storage"
export CODEX_RUNS_ROOT="$HOME/compute-runs"
PYTHONPATH=src python3 -m stability_label_curation paths --json
```

`paths --json` emits an object with the four roots, `repository_root`,
`project_data_dir`, and `project_runs_dir`. Invalid configuration exits with status 1.
`doctor` checks only configured paths and necessary parent paths, without writing or
inventorying siblings. Missing storage or limited write/search access produces warnings;
invalid configurations, missing checkout, and file/directory conflicts produce errors.
Warnings exit with status 0; errors exit with status 1. Permission checks are advisory:
filesystem ACLs, mounts, or concurrent changes can still make initialization fail.

`init-storage` creates only project data/runs directories and missing ancestors.
It does not create a separate repos root unless that root is a necessary ancestor
of an explicitly configured target. Existing directories are retained, making repeats
idempotent. It creates no data files, changes no existing permissions, scans no
sibling projects, and provides no deletion/cleanup operation. Normal filesystem
permissions and umask apply to new directories. Configuration must remain stable
during initialization; this is a local research utility, not a defense against concurrent
hostile symlink replacement.

## Platforms

macOS is the primary development/analysis environment. Linux/WSL2 is the compute
environment, with two RTX 4090 GPUs reserved for later training work. Python's
`Path.home()` uses the local user's home on each system. On WSL2, run with Linux
Python and Linux paths (including `/mnt/...` for explicitly selected Windows mounts);
Windows drive syntax is not an absolute path to Linux Python. GitHub can synchronize
code; local inputs and outputs stay outside Git and are not synchronized by this CLI.

This implementation uses the Python standard library and POSIX-compatible paths
on macOS and Linux/WSL2. macOS execution alone does not empirically validate WSL2.

Artifact transport uses the existing resolver and a controlled project-data cache; see [fresh-clone recovery](FRESH_CLONE_RECOVERY.md). Restoration preserves original data/run paths and never launches regeneration or training automatically.
