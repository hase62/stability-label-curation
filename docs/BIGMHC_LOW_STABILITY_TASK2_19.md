# Task 2.19 approved low-stability A/L/P execution

Base: local `task/2.18-low-stability-positive-design`, commit
`a7a41ea179233088cfae1d8d91826ef9527ce6d0`. Branch:
`task/2.19-low-stability-alp-gpu`. GitHub main has not yet received Task 2.18;
the user's corrected starting-point instruction explicitly selects this local
base. No merge or push is part of Task 2.19.

The [approved protocol](EL_LOW_STABILITY_POSITIVE_PROTOCOL.md) is unchanged.
Task 2.19 explicitly authorizes engineering, synthetic checks, one seed-42 L
and one P with one EL and one IM epoch, using authentic BigMHC CUDA FP32 on
Z790/RTX 4090. No extra condition, seed, tuning, download or sealed evaluation.

## Implementation and baseline compatibility

`configs/bigmhc_low_stability_task2_19.json` inherits the Task 2.17 scientific
settings and all 23 existing input bindings. Protocol version
`el_low_stability_positive_v1` selects A/L/P; the historical version still
selects A/B/P with its original two-sided P. L clips the existing exact rational
Task 2.12 positive weights at 1. P uses that L multiset and the unchanged
source-ID-sorted, local deterministic per-HLA Fisher–Yates stream. Every
negative weight remains 1. There is no renormalization or new rank definition.
FP32 residuals are checked against the reduced rational totals rather than n.

The existing fail-fast preflight validates full EL/IM input and raw-row provenance,
Teacher sidecar, exact per-HLA L/P rational and FP32 multisets, and all Task 2.18
aggregate/per-HLA weight estimates. It compares original source-row cohort
fingerprints with Task 2.17 A before model construction or optimizer creation.

The baseline reuse exception is restricted to Task 2.17 A's fixed commit,
matched-state hash and scientific configuration identity. The compatibility
module checks unchanged ASTs of the training/optimizer loop, seeding, native
source modules, encoders/identity wrapper, loss, RNG, IM transfer parameter
selection, prediction, checkpoint load/save/reload and reference gates. It also
checks the complete worker against the historical worker plus exactly six
reviewed metadata/I/O substitutions. Those substitutions reuse existing source
CSVs/provenance and add a receipt-bound cross-commit check; they do not change
model construction or stage execution. No complete source dataset is copied.

Reused A's historical receipt, configuration, all worker-authenticated outputs,
36 initial tensor identities, checkpoint/overlay lineage and saved development
prediction/metric consistency are verified. The current authentic synthetic
CUDA gate covers A/L/P initialization, native encoded batches, training RNG
isolation, and exact native versus unit-weight loss/gradients/AdamW updates.
No scientific A training or new A development inference is needed.

A parent compatibility receipt binds the current execution commit, reviewed
source identities, passing tests and CUDA equivalence to the historical A.
Workers may differ from that A only in their recorded code commit and approved
weight assignment; runtime versions, configuration identity, initialization,
RNG boundaries, every sampled batch fingerprint, skip masks, optimizer defaults,
updated parameter lists and step counts remain mandatory checks. Historical
strict code-commit matching remains in force for old A/B/P configurations.

L/P use the same existing `bigmhc_baseline_runner.train_epoch` implementation.
Batch loss remains `mean(weight * unreduced_BCE)` over native 17-row EL batches;
IM uses original unweighted mean BCE and the native all-negative skip. Check
sample fingerprints before optimizer updates and verify complete stage schedules
against reused A. Expected counts are 70,069 EL and 214 IM optimizer steps.

## Validation and invocation

Relevant unittest coverage includes both weighting-design modules, the loss
adapter, baseline runner, GPU worker, original experiment gates and new low-only
compatibility/rejection tests. No broad source/artifact audit is run. Synthetic
CUDA checks do not consume scientific rows or produce development predictions.

After committing a clean implementation and retaining the passing test log and
current CUDA report, invoke the existing experiment entry point in the existing
GPU Python environment:

```sh
PYTHONPATH=src CUDA_VISIBLE_DEVICES=0 CUBLAS_WORKSPACE_CONFIG=:4096:8 \
  <existing-gpu-python> -B -m stability_label_curation.bigmhc_abp_experiment \
  --run-id task-2_19-low-stability-alp-gpu \
  --noop-report <current-cuda-report> --test-log <passing-relevant-tests-log>
```

The fixed destination is
`resolve_paths().project_runs_dir / 'task-2_19-low-stability-alp-gpu'`; existing
destinations are rejected. The launcher records A as an external reference,
then runs L and P exactly once each. Each worker has the existing 3,600-second
budget and 32-GiB RSS limit; the enclosing budget remains 10,800 seconds. Failures
or meaningful mismatches stop execution without selecting a new rule or retry.

Stage-start/completion, checkpoint and reload receipts persist before proceeding.
Each arm retains configuration, weight-assignment digests, sample fingerprints,
loss trajectories, checkpoints, predictions, metrics and runtime/memory reports.
The launcher verifies saved artifacts, records all four metrics and L−A, L−P,
P−A, and emits the parent output hash manifest. A checkpoints are referenced
in place. Numerical outcomes and actual resource evidence are recorded below
only after execution completes.

## Interpretation boundary

This proposal follows observed Task 2.17 development results and remains
exploratory. Primary: non-interpolated IM AP on the same 383 observations
(120 positive/263 negative). Secondary: IM AUROC and EL-proxy AP/AUROC. Report
full precision and all three fixed contrasts; comparisons with Task 2.17 are
descriptive. No score-dependent choice, checkpoint selection or tuning.

EL detection, predicted pMHC kinetic stability, repeat detection and T-cell
immunogenicity are distinct. A positive predictive result cannot establish label
error or estimate label reliability/repeat-detection probability. A negative
result cannot falsify the biological kinetic-stability hypothesis. Teacher noise,
allele-dependent ranking quality, reduced positive contribution, one seed/one
permutation, and the previously viewed small development cohort limit inference.
