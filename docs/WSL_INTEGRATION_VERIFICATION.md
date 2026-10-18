# Task 2.15W: WSL integration and recovery verification

The integration branch `task/2.15w-wsl-artifact-integration` starts from approved
Mac main `e74b720b3d08d5a4ab27ea0d21d37724fabe1c3c` and merges Windows Task 2.14C
`6ea646b9e5e2787e2c8b5ff69fb4e427c8c0af29` with both parents preserved in merge
`0c1c727c2719dd6391edbdd47f6ecdde59f189e7`. The separate worktree is
`stability-label-curation-integrated` under the configured repository root.
Original worktrees, main, labels, configurations and existing outputs are preserved.
The approved A/B/P implementation and Mac artifact registry/restorer are unchanged.

Evidence is outside Git in project runs, `task-2_15w-wsl-artifact-integration/`.
Its manifest records the integration merge and the 220 existing file identities
captured before verification. No scientific training, A/B/P experiment, sealed
evaluation access, checkpoint deserialization, backup upload or push is performed.

## Executed WSL2 checks

- Integrated suite: 830 tests run, 821 passed, nine separate Teacher-environment
  tests skipped; zero failures/errors.
- Existing synthetic CUDA no-op: exact A/legacy loss, gradients and AdamW updates;
  maximum gradient difference zero; two synthetic optimizer steps only.
- Guarded `--preflight-only`: A/B/P passed, binding 1,453,578 EL rows (70,069
  positive), 3,428 IM rows with original four-column hashes, and 70,069 Teacher
  positives across 49 HLA groups. Zero model/optimizer constructions, optimizer
  steps, checkpoint writes or development scoring in preflight.
- `scripts/restore_artifacts.py verify` with the canonical workspace root verified
  all 23 destination files, totaling 215,263,518 bytes. Canonical `restore` reused
  those destinations without writes to existing files.
- Disposable dry-run created no directories. A separate wrong-hash fixture was
  rejected before acquisition and preserved. Adversarial archive tests ran as
  part of the integrated suite.

## Package recovery status

All transport uses the configured workspace and its `data/artifacts` cache,
never a Downloads directory. Private locator values are omitted from evidence.
The disposable workspace is under project
`data/artifacts/audits/task-2_15w/disposable-workspace`; it is retained for review.

| Package | Canonical files | Clean disposable recovery |
|---|---:|---|
| `gpu-inputs-23af9966` | 21 verified | Pending approved private locator |
| `el-positive-scores-task2-13` | 2 verified | Downloaded, restored and verified |

The score archive is 7,279,294 bytes, SHA256
`c4465d7ac048d278546c63057516b56a0ab28dfc96e63f47d705a48a11adff2e`.
Both member hashes and the complete archive verified. A second invocation without
locator variables reused destinations offline with zero download bytes. Its
authenticated cache was also retained beneath canonical project storage.

The GPU archive is not cached locally and `SLC_ARTIFACT_GPU_INPUTS_URL` is unset.
The disposable CLI fails with that exact missing-locator prerequisite. Verifying
its existing 21 destination files does not prove archive recovery. Complete the
remaining clean restore/verify and offline reuse after an approved private locator
is provided; do not reconstruct or substitute an archive and claim it was the
authenticated Dropbox package. Full two-package recovery readiness remains open.

## Windows checkpoint backup gaps

Inventory hashes opaque checkpoint bytes and metadata; it does not load models.
All observed checkpoint files lack coverage by an authenticated external-backup
definition in the Git-managed registry. Unregistered private backups are unknown.

| Run | EL files | IM overlay files | Registered external backup files |
|---|---:|---:|---:|
| Task 2.9 | 36 | 4 | 0 |
| Task 2.10 | 36 | 4 | 0 |
| Task 2.14B | 36 | 0 | 0 |

Total: 116 physical files, 80 distinct hashes, 1,071,815,738 bytes. Task 2.14C
created no model checkpoints. Task 2.14B's 36 EL files have matching local copies
in Task 2.10; local duplication is not external backup coverage. All 58 entries
in the retained Task 2.14B final output manifest verify.

`reports/windows_checkpoint_backup_inventory.json` records file hashes/sizes,
available manifests, configurations, environment and lineage receipts,
initial-state/sampling evidence and prediction-file hashes. The historical loss
of Task 2.14B's sampling fingerprints/RNG boundary remains unresolved; no evidence
is fabricated and no checkpoint resumption is attempted.

The combined code has no observed training-input integration blocker. A future
experiment still requires separate authorization, a fresh run ID, and the
existing authenticated fresh-A reference gate before B/P. Recovery verification
is incomplete until the GPU package locator is supplied; checkpoint external
backup coverage remains a separate gap requiring approved backup publication.
