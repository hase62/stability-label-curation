# Task 2.14B matched A/B/P GPU experiment

This task explicitly authorizes one fresh A, one stability-weighted B and one
fixed within-HLA permuted P, using the approved Task 2.12 protocol and Task 2.13
adapter from GitHub main `0c3b5cf245c42803854c9139f4c4058cc36f7dbf`.
Original EL/IM labels, full eligible populations, seed 42, FP32, native sampling,
architecture, AdamW defaults, one epoch per stage and frozen development are fixed.
The earlier engineering-only configuration remains disabled.

`configs/bigmhc_abp_task2_14b.json` enables execution. The launcher creates all
artifacts below the project runs root's `task-2_14b-abp-gpu-experiment/`, with
separate A/B/P manifests and outputs. B/P configurations are saved outside Git
only after A succeeds, pinning its actual `matched_state.json` hash. Each worker
retains a maximum 3,600-second wall budget and the total launcher budget is
10,800 seconds. A failure stops execution without retry or automatic adjustment.

Minimal runner integration authenticates these nested arm manifests against
the canonical experiment manifest. The legacy unweighted path is preserved.
Task 2.13's reference comparison now canonicalizes optimizer-default sequences
through JSON so persisted list-valued AdamW betas match runtime tuples; changes
to their values still fail. No loss, sampler or optimizer equation changes.

Before training, run the full suite and the synthetic CUDA gate:

```bash
PYTHONPATH=src ~/codex/.venvs/bigmhc-gpu/bin/python -B -m unittest discover -s tests -v > /tmp/task2_14b-tests-preflight.log 2>&1
PYTHONPATH=src CUDA_VISIBLE_DEVICES=0 CUBLAS_WORKSPACE_CONFIG=:4096:8 \
  ~/codex/.venvs/bigmhc-gpu/bin/python -B -c \
  'import json; from stability_label_curation.el_stability_loss_adapter import synthetic_noop_evidence; print(json.dumps(synthetic_noop_evidence(device="cuda"),indent=2))' \
  > /tmp/task2_14b-cuda-noop.json
```

The gate uses synthetic observations and authentic pinned BigMHC code. CUDA
checks include two matched single-step AdamW updates, identical loss/gradients,
A/B/P initial tensors, source-ID propagation and unchanged native sampler RNG.
It never reads scientific training or development rows. Its source hashes must
match execution source bytes. CPU default checks retain zero optimizer steps.

Commit implementation before starting the exclusive launcher:

```bash
PYTHONPATH=src CUDA_VISIBLE_DEVICES=0 CUBLAS_WORKSPACE_CONFIG=:4096:8 \
  ~/codex/.venvs/bigmhc-gpu/bin/python -B -m stability_label_curation.bigmhc_abp_experiment \
  --noop-report /tmp/task2_14b-cuda-noop.json --test-log /tmp/task2_14b-tests-preflight.log
```

Before B, A must match authenticated Task 2.10 initial tensors, scientific
configuration, exposures, optimizer defaults and skip schedule. Historical
FP32 step-loss comparison uses rtol 1e-5/atol 1e-7; probability comparison uses
rtol 1e-5/atol 1e-6. These bounds are fixed before A outcomes. Larger differences
stop execution for investigation. The exact historical tensors need not be
reused. Across new A/B/P, initial tensors, RNG boundaries, every ordered batch
source-ID/label digest, optimizer defaults, steps and skips must match exactly.

Worker receipts authenticate datasets, lineage, checkpoints and predictions.
The launcher verifies receipt hashes, recomputes the same non-interpolated AP
and AUROC from saved 383-row probabilities, and exports all three prescribed
contrasts. Per-HLA metrics require five positives and five negatives; all rows
remain in global metrics. Compact sequence fingerprints retain batch boundaries;
per-batch fingerprints remain available in matched-state evidence.

This is one exploratory seed and one permutation on previously viewed development
data. Neither improved utility nor a null result establishes whether low-stability
EL positives are erroneous or reproducible. Sealed independent outcomes, extra
seeds, alternative strengths and correction methods are outside authorization.

## Workstation execution outcome: stopped before IM optimization

Execution code commit: `9f794b1bc953b7d7b007fb73bef2ab56a1687175`.
The sidecar and all 23 inputs verified. The final CUDA synthetic gate had exact
loss, gradients and AdamW updates; A/B/P synthetic initialization, source IDs,
encoded inputs and RNG states matched. The full suite ran 787 tests successfully
(778 passed; nine separate Teacher-environment fitting tests skipped), both before
execution and after the failure.

A completed 70,069 EL updates, then stopped while constructing the IM identity
wrapper: `Native source-row join/label/order mismatch`. No IM optimizer update
ran, and B/P did not start. The first and all 3,428 IM rows have a raw-hash schema
mismatch: original IM provenance hashes include `mhc,pep,tgt,rand`, whereas the
Task 2.13 wrapper reconstructs `mhc,pep,tgt`. Source IDs, source coordinates,
HLA, peptide and original labels otherwise agree. The synthetic IM fixture used
three-column hashes and therefore did not expose this integration blocker.
Training was stopped as required; no retry, adapter bypass or new evaluation ran.

All 36 A EL checkpoint files are byte-identical to Task 2.10. CPU-map strict
reload independently verified the same 36 tensor states. Every one of the
70,069 six-decimal logged losses matches Task 2.10. The mean computed from those
rounded log values is approximately 0.07459771805; the new full-precision mean
was not persisted. Worker elapsed time was 1,307.044 seconds and peak worker RSS
was 3,554,689,024 bytes (3.311 GiB). Separate EL/IM wall times, peak CUDA allocator
measurements and complete sampled source-ID sequences remained in memory when
the worker failed and are unavailable. No new development predictions or metrics
were saved; A/B/P AUROC/AP and their contrasts are therefore unavailable.

Preserved output includes the original failure receipt, full EL training log,
36-tensor EL checkpoint, manifests, source-row membership, initial identities,
CUDA gate and test logs. `reports/failure_diagnosis.json` and
`reports/final_artifact_verification.json` record the read-only investigation;
`reports/final_output_manifest.json` authenticates the preserved files. Source
inputs remain unchanged and sealed tests were not opened.

The next necessary step is a reviewed IM provenance fix, with a synthetic
four-column raw-source fixture and full-cohort identity binding for both stages
before GPU optimization. Only after separate authorization should the same
preregistered fresh A/B/P comparison restart. This incomplete execution provides
no evidence about predictive utility or biological repeat-detection reliability.

The read-only audit also found a prospective launcher blocker: Task 2.10's
`training_summary.json` exceeds the inherited evidence reader's 8 MiB bound used
by `compare_historical`. That gate would need a bounded full-report reader before
a retry. The current attempt stopped earlier at the IM raw-hash check; the
large-report gate was not reached. Neither blocker was bypassed or patched after
the stop.

## Task 2.14C: integration repair and preflight only

The executed Task 2.14B commit and its final `8e913f9` commit have identical
implementation, tests and configuration; the latter adds only the outcome above.
Task 2.14C branches from that completed commit. No scientific training resumes.

IM provenance now verifies the original parsed strings with the exact Task 2.5
serialization: UTF-8 `json.dumps([header, fields], ensure_ascii=False,
separators=(',', ':'))`, header order `mhc,pep,tgt,rand`. CSV quoting is parsed
before hashing. Historical ledgers omitted the flag, but retained its full hash:
the adapter recovers a literal binary flag only if exactly one complete four-field
hash matches. Explicit flags must match without numeric coercion. All 3,428
original rows recover `"0"`. New IM coordinate manifests retain `original_rand`;
native model inputs remain `mhc,pep,tgt`. Missing, modified, extra, duplicate or
misordered identities still fail. No historical ledger or hash is rewritten.

The historical Task 2.10 summary is 8,795,232 bytes. The historical comparison
requires its complete step-loss trajectory, so a compact summary is insufficient.
A dedicated internal-summary reader verifies the execution-receipt SHA256 and
enforces a 32 MiB bound, duplicate-key rejection and nonfinite-literal rejection.
This avoids a new streaming parser dependency; arbitrary evidence retains the
original 8 MiB reader limit. The same reader handles newly completed arm summaries.

`bigmhc_abp_preflight.validate` verifies both complete input stages through the
pinned native CSV reader and identity wrapper, Teacher binding, all three weight
assignments, population/class counts, sequence separation, exact receptor and
peptide encodings, source identities and historical reports/checkpoint lineage.
It reuses authenticated inputs, holds one native cohort at a time, and creates no
dataset copies. Both the matched launcher and each weighted worker call this gate
before EL optimization. Failures record their reason before training can begin.

The CLI supports `--preflight-only --preflight-report <new-report-path>` and
`--config <configuration-path>`. For example, from the repository with the pinned
GPU Python environment, `PYTHONPATH=src CUDA_VISIBLE_DEVICES=0 python -B -m
stability_label_curation.bigmhc_abp_experiment --preflight-only --preflight-report
<new-report-path>` runs all A/B/P input/configuration checks. Resolve the report
destination through `stability_label_curation.paths.resolve_paths().project_runs_dir`
and create its parent directories first. Preflight does not construct a model or
optimizer, batch/sample rows, write checkpoints, or score development observations.
B/P's future matched-A reference is explicitly unresolved and training-disabled
in the prospective configuration checks; the existing launcher must supply the
authenticated completed fresh A reference before B/P may train. No dummy hash or
old incomplete A reference substitutes for that gate. A separately authorized
fresh experiment must use a new `--run-id` with the original experiment ID plus a
suffix; existing run directories remain protected from reuse or overwrite.

Future workers publish separate stage-start, stage-completion, stage-failure and
checkpoint receipts. Full-precision losses, stage times, CUDA allocator peaks,
ordered sampled-batch hashes and model lineage are saved before starting the next
stage. These deterministic writes do not draw RNG values or alter training logic.
No missing Task 2.14B measurements or sampled-sequence evidence is reconstructed.

WSL2 acceptance: all 1,453,578 EL rows (70,069 positive), 3,428 IM rows and 70,069
Teacher-positive observations across 49 HLA groups bind successfully; A/B/P real
input and weight-invariant preflights pass. Guarded CLI execution prohibits model,
optimizer, training, scoring and checkpoint calls. The synthetic CUDA gate has
exact loss/gradient/AdamW equivalence (two synthetic optimizer steps only).
The targeted suite passes 51 tests; the complete suite runs 795 tests with 786
passed and nine separate Teacher-environment tests skipped. Evidence is under
`task-2_14c-preflight-integration-repair/` in project runs, outside Git.

All 59 Task 2.14B artifacts and all 64 Task 2.10 artifacts retain their original
hashes. A's 36 EL checkpoint files remain byte-identical to Task 2.10 and strict
CPU reload confirms equal tensors. That checkpoint is technically usable as an IM
initial state under separate authorization, with the same architecture/transfer
contract. Exact continuation of the original IM sampling/RNG boundary cannot be
proved: those states and Task 2.14B's sampled EL sequence were not persisted.
Tensor equality and rounded-loss equality do not prove matched sampling. The
current launcher implements fresh A/B/P runs, not checkpoint resumption; reuse
must not be represented as a fully audited fresh matched A/B/P comparison.
