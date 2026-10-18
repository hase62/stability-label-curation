# Fresh-clone artifact recovery

Requires Python 3.11+ and an authorized checkout of this private repository. No
scientific or ML dependency is needed for artifact transport. This restores inputs;
it never launches training. The [audit](REPRODUCIBILITY_AUDIT.md) documents what is
still missing, especially the frozen Teacher backup and some historical provenance.

From the repository root, choose a `codex` workspace root (the default is
`~/codex`). Archives are cached under its project `data/artifacts/cache/`, while
member destinations retain the original `data/` or `runs/` layout.

```sh
python3 scripts/restore_artifacts.py list
python3 scripts/restore_artifacts.py status gpu-inputs-23af9966 el-positive-scores-task2-13 bigmhc-windows-checkpoints --workspace-root "$HOME/codex"
python3 scripts/restore_artifacts.py dry-run gpu-inputs-23af9966 el-positive-scores-task2-13 bigmhc-windows-checkpoints --workspace-root "$HOME/codex"
```

The three owner-approved Dropbox retrieval locations are persistent in the
registry. Repository visibility was confirmed private for Task 2.16R. Authorized
collaborators need no URL prompts, environment variables, manual downloads or
separate verification command. From a fresh clone, recover all three packages:

```sh
python3 -B scripts/restore_artifacts.py restore gpu-inputs-23af9966 el-positive-scores-task2-13 bigmhc-windows-checkpoints --workspace-root "$HOME/codex"
```

The short checkpoint ID is an alias for the unchanged Task 2.16W ID
`bigmhc-windows-checkpoints-task2-16w`; both refer to the same archive and mapping.
Repeated names/aliases are processed once. The checkpoint archive is 666,954,318
bytes and restores 80 unique checkpoint files into 116 historical checkpoint
locations, plus the packaged provenance. Its real external restoration remains
to be verified on Z790; this Mac task does not download the archive.

`restore` automatically authenticates archive SHA256, allowed members and all
restored-file hashes. Correct existing destinations are left untouched. A verified
archive in `data/artifacts/cache/` or the original `data/artifacts/packages/`
location is reused without copying the archive or downloading it again. Only
missing archives needed for incomplete restoration are downloaded into the cache;
wrong-hash collisions fail closed. No existing scientific file is overwritten.

The registry contains restricted access-bearing links. Do not publish the
repository, its registry or its Git history without removing/revoking that access
information. CLI output and receipts omit URLs and access keys. Private Git access
and functioning shared links remain prerequisites; expired/revoked links require
an authorized registry update. No URL values belong in logs or reports.

JSON stdout and exit codes support automation. `--dry-run` creates no files. An
optional `--receipt` must use a new filename under controlled artifact/run storage.
`fetch`, `status`, `verify`, and legacy environment-based custom registries remain
available, but no additional manual step is required for the command above.

The mapping interprets the archives' `codex/data/...` and `codex/runs/...` names
relative to `--workspace-root`; it does **not** extract a nested `codex` directory
inside that root. Restore 21 regular GPU-input files and two score-sidecar files.
The first two bundles provide the existing runner's original training views,
provenance ledgers, frozen development cohort, pseudosequences, pinned implementation and positive
Teacher scores. Configuration comes from Git. Historical corrected views and sealed
evaluation files are excluded. The third bundle contains only the approved saved
Windows checkpoints and provenance described in [checkpoint recovery](BIGMHC_CHECKPOINT_RECOVERY.md).

Other registered public sources can be fetched individually, for example:

```sh
python3 scripts/restore_artifacts.py restore dtu-2016-raw --workspace-root "$HOME/codex"
```

Their original scientific provenance is in `configs/data_sources.toml` and the
source audit documents. `--all` selects all registered sources, including the
whole opaque BigMHC archive: it is unnecessary for the current GPU handoff.
Transporting that archive does not authorize inspecting its sealed members.
Registry dependencies are descriptive; select each artifact explicitly.

For historical recomputation, consult
`configs/artifact_reconstruction_plan.json`: use the exact producing commit,
configuration, seed, authenticated input list, environment and generation command
for that group. Create a **new** run; preserve old runs. Parent provenance hashes
may require exact legacy recovery or separately approved versioned rebinding.
Never run a training recipe automatically to recover a missing checkpoint.
There is currently no authenticated remote locator for the frozen Teacher.
The [Windows checkpoint package](BIGMHC_CHECKPOINT_RECOVERY.md) covers the existing
Task 2.9/2.10 and Task 2.14B A EL checkpoint bytes through the registered Dropbox
locator. External checkpoint restoration is pending Z790 verification. Existing
weights must not be replaced by newly trained surrogates.

After Windows Task 2.14C has finished, the following checks require no GPU job:

```sh
python3 scripts/restore_artifacts.py verify gpu-inputs-23af9966 el-positive-scores-task2-13 --workspace-root "$HOME/codex"
PYTHONPATH=src python3 -B -m unittest discover -s tests -p test_artifact_restore.py -v
PYTHONPATH=src python3 -B -m unittest discover -s tests -p test_reproducibility_audit.py -v
```

Also check the existing runner's source/parent-provenance contract, without running
training:

```sh
CODEX_ROOT="$HOME/codex" PYTHONPATH=src python3 -B -m stability_label_curation bigmhc-worker verify-inputs --config configs/el_stability_weight_adapter_v1.json --json
```

This authenticated 23 inputs totaling 215,263,518 bytes in the Mac clean-root test.
Then collect the Windows run/checkpoint metadata listed in the audit. Do not copy
Mac virtual environments to WSL2, start training, inspect sealed outcomes or
change active Windows work as part of recovery verification.
