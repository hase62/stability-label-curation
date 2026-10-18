# Windows BigMHC checkpoint backup (Task 2.16W)

Artifact ID: `bigmhc-windows-checkpoints-task2-16w`. Publication to Dropbox and
external recovery are **pending**. No remote URL is stored in Git. Upload the
existing archive manually; connecting its eventual locator does not change its
bytes, manifest or hashes.

The single archive is written to the configured project data directory:
`~/codex/data/stability-label-curation/artifacts/packages/stability-label-curation-bigmHC-windows-checkpoints.tar.gz`
with adjacent `.manifest.json` and `.tar.gz.receipt.json` files. The Git-managed
artifact registry records its exact size, SHA256, member hashes and restoration
mapping. The archive also contains its own manifest. The manifest lists the
payload members; its own digest is recorded separately in the registry to avoid
a circular hash. Archive and sidecars stay outside Git.

The completed archive is **666,954,318 bytes** (636.06 MiB), SHA256
`4787ea9b3fea2a42f4b32a15a9b38d3c8453fa6d6187bd48100b4014bb0a4909`.
It has 106 stored members: 80 checkpoint files, 25 provenance JSON files and the
package manifest; 36 additional checkpoint destinations are aliases. The coverage
auditor excludes packages marked publication pending from external-backup counts.

## Contents and historical identities

| Run | Logical checkpoint files | Stored unique checkpoint files |
|---|---:|---:|
| Task 2.9 EL + IM overlay | 36 + 4 | 40 |
| Task 2.10 EL + IM overlay | 36 + 4 | 40 |
| Task 2.14B A completed EL | 36 | 0 (aliases of Task 2.10 EL) |

All 36 files immediately under
`task-2_14b-abp-gpu-experiment/A/checkpoints/el/` are aliases of the identically
named files under `task-2_10-full-eligible-baseline-a/checkpoints/el/`.
Every alias has its own historical destination, SHA256, size and canonical
`source_archive_path` in the registry and package manifest. Only the canonical
member appears in the archive. Restore materializes independently writable
regular files at both paths; it never creates tar hardlinks or symlinks.

Both IM overlays remain at `checkpoints/el/im/` with their EL parent at `..`.
The archive preserves 25 essential JSON records: original run manifests, stored
training configurations, environment, checkpoint lineage, execution/output
receipts, sampling/training summaries and Task 2.14B failure/identity evidence.
Their historical absolute paths are retained as evidence only. Restore resolves
the portable `area` and `relative_path` mapping through project storage settings.
The archive excludes training CSVs, score datasets, prediction files, sealed data,
credentials and private Dropbox locators.

## Packaging and verification

From the authorized checkout:

```sh
python3 -B scripts/package_checkpoints.py --dry-run
python3 -B scripts/package_checkpoints.py
```

The command authenticates the retained Task 2.15W inventory and selects files
from the Task 2.9/2.10 execution manifests and Task 2.14B final output manifest.
Its Git-managed selection plan pins the existing evidence in
`configs/bigmhc_windows_checkpoint_package.json`. It checks the recorded
Task 2.14B duplicate verification, hashes each unique source stream while adding
it to the archive, and automatically hashes/registers the completed archive.
There is no staging copy of the checkpoint tree and no repeated alias hashing.
Existing archives, receipts and original checkpoints are never overwritten.
A successful second invocation stops because the artifact is already registered;
it does not rebuild another package.

Regression tests use tiny opaque fixtures, including alias restoration, long
filenames, corruption, destination collisions, missing locators and symlinks:

```sh
PYTHONPATH=src python3 -B -m unittest discover -s tests -p 'test_checkpoint_package.py' -v
PYTHONPATH=src python3 -B -m unittest discover -s tests -p 'test_artifact_restore.py' -v
PYTHONPATH=src python3 -B -m unittest discover -s tests -p 'test_reproducibility_audit.py' -v
```

Executed on WSL2 with Python 3.13.5: 15 packaging tests, 27 restore tests and
10 coverage-audit tests passed (52 total, no failures or skips). Packaging
authenticated all 80 unique checkpoint streams and the 25 provenance files.
The real checkpoint tree was not restored into a second audit copy. No model
deserialization, GPU training, predictions or dataset downloads were performed.

The existing bounded transport accepts archives up to 2 GiB, allowing the one
combined package. Every download still has the exact registered byte count and
SHA256 bound. No real checkpoint is restored into a second tree for testing.

## Recovery after manual upload

Supply the authorized direct-download Dropbox URL privately through the process
environment variable `SLC_ARTIFACT_BIGMHC_WINDOWS_CHECKPOINTS_URL`. Do not put its
value in Git, logs or command-line arguments. No registry edit or repackaging is
needed. With that variable set, the existing restore CLI can recover all 116
checkpoint destinations and the included provenance records:

```sh
python3 -B scripts/restore_artifacts.py dry-run bigmhc-windows-checkpoints-task2-16w --workspace-root "$HOME/codex"
python3 -B scripts/restore_artifacts.py restore bigmhc-windows-checkpoints-task2-16w --workspace-root "$HOME/codex"
python3 -B scripts/restore_artifacts.py verify bigmhc-windows-checkpoints-task2-16w --workspace-root "$HOME/codex"
```

Use a different workspace root when recovering to a different machine/layout.
The CLI verifies the entire archive before publishing files, verifies every
restored member/alias, rejects wrong-hash collisions and reuses correct existing
destinations. Archive tar entries remain regular files only. Recovery needs
Python 3.11+ and this repository; it never loads models or starts training.

Exact saved checkpoint recovery is covered. Task 2.14B did not produce an A IM
overlay or B/P checkpoints. Its per-batch sampling fingerprints and RNG boundary
were not persisted before failure; interrupted optimizer/RNG resumption is not
established. These are retained historical limitations, not missing model bytes.
Dropbox upload/download and external restoration have not been verified in this
task. Stop after packaging; no training, predictions, merge or push is authorized.
