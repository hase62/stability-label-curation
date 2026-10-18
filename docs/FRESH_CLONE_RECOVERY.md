# Fresh-clone artifact recovery

Requires Python 3.11+ and an authorized checkout of this private repository. No
scientific or ML dependency is needed for artifact transport. This restores inputs;
it never launches training. The [audit](REPRODUCIBILITY_AUDIT.md) documents what is
still missing, especially trained-checkpoint backups and historical provenance.

From the repository root, choose a `codex` workspace root (the default is
`~/codex`). Archives are cached under its project `data/artifacts/cache/`, while
member destinations retain the original `data/` or `runs/` layout.

```sh
python3 scripts/restore_artifacts.py list
python3 scripts/restore_artifacts.py status gpu-inputs-23af9966 el-positive-scores-task2-13 --workspace-root "$HOME/codex"
python3 scripts/restore_artifacts.py dry-run gpu-inputs-23af9966 el-positive-scores-task2-13 --workspace-root "$HOME/codex"
```

For first recovery, obtain the authorized Dropbox URLs privately. Populate
`SLC_ARTIFACT_GPU_INPUTS_URL` and `SLC_ARTIFACT_EL_POSITIVE_SCORES_URL` in the process
environment using your private secret/locator mechanism. Do not commit the values,
print them to logs or pass them as command-line arguments. No credential is
embedded in the registry. Missing access fails with the required variable name.

```sh
python3 scripts/restore_artifacts.py fetch gpu-inputs-23af9966 el-positive-scores-task2-13 --workspace-root "$HOME/codex"
python3 scripts/restore_artifacts.py restore gpu-inputs-23af9966 el-positive-scores-task2-13 --workspace-root "$HOME/codex" --receipt "$HOME/codex/data/stability-label-curation/artifacts/receipts/gpu-input-restoration.json"
python3 scripts/restore_artifacts.py verify gpu-inputs-23af9966 el-positive-scores-task2-13 --workspace-root "$HOME/codex"
```

Use a new receipt filename on each requested receipt write; existing files are
never overwritten. `restore` can also download directly, so the separate `fetch`
is optional. Subsequent restores reuse verified destinations without network
access, even if locator variables have been removed. Wrong-hash collisions require
explicit investigation; the tool never replaces them. JSON stdout and exit codes
are suitable for automation. `--dry-run` applies to either mutation command.

The mapping interprets the archives' `codex/data/...` and `codex/runs/...` names
relative to `--workspace-root`; it does **not** extract a nested `codex` directory
inside that root. Restore 21 regular GPU-input files and two score-sidecar files.
These provide the existing runner's original training views, provenance ledgers,
frozen development cohort, pseudosequences, pinned implementation and positive
Teacher scores. Configuration comes from Git. Historical corrected views, sealed
evaluation files and previously trained weights are not part of these bundles.

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
Task 2.9/2.10 and Task 2.14B A EL checkpoint bytes locally; Dropbox publication and
external recovery remain pending. Existing weights must not be replaced by newly
trained surrogates.

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
