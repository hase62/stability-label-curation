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
source loader, identity wrapper, loss, RNG, IM transfer parameter selection,
prediction, checkpoint load/save/reload and reference gates. Input hashes also
pin the authentic BigMHC source and encoders. It also
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

## Completed execution evidence

Execution commit: `02a623496ea9fddca9c3531e5e684868e2cd4b35`. Both L and P completed once; A was reused from `task-2_17-abp-comparison/A`. No scientific retraining or new inference for A occurred.

Relevant tests: **151 passed, zero failures/skips**, in the existing GPU Python environment. The authentic CUDA synthetic gate passed exact unit-weight loss, gradients and AdamW updates, with identical A/L/P initialization, native encoded batches and training RNG. Full-cohort preflight passed before scientific optimization in the parent and each worker.

Both conditions retained the approved 70,069-positive/49-HLA population. For each of L/P:

| Weight invariant | Exact-calculation result (binary64 display) |
| --- | ---: |
| Downweighted positives | 35021 |
| Minimum | 0.7500571951498513 |
| Median | 1.0 |
| Mean | 0.9375002293705667 |
| Maximum | 1.0 |
| Positive-weight total | 65689.70357176624 |
| Reduction | 4379.296428233763 |
| Reduction fraction | 0.06249977062943332 |
| FP32 total | 65689.70356845856 |
| FP32 residual from exact total | -3.307679435238242e-06 |

Per-HLA rational and FP32 multisets match exactly between L/P. The 35,021 downweighted observations and all per-HLA aggregate values match Task 2.18. Original labels, negative unit weights and the batch-row denominator are unchanged. The FP32 residual satisfies the approved per-HLA tolerances without renormalization.

All 36 initial EL tensor hashes, EL and IM RNG boundaries, every ordered native source-row batch, optimizer defaults/parameter lists, and skip masks match reused A. The initial tensor digest is `93a6f9104639a93ae41c2b559baf0d2b3a2e433da911c7339d53660ae79d2715`; EL batch-list digest is `32a9e94677ef4e1b1f3e7863601155843b623da92e074f4e5802f6a0d7c2e886`, IM is `2d84f5d5d6b29ad5c1538c01f297e9a6fa9b2c0fd767d3414ecccef473a1215e`.

Each condition has 70,069 EL updates and 214 IM updates. EL optimized exposures: 70,069 positives and 1,121,104 negatives. IM samples all 3,428 observations in 215 batches, skipping the same 16-negative batch 48, and optimizes 955 positives/2,457 negatives. No original observation is excluded from eligibility.

Loss figures below retain full binary64 display precision from stored evidence. Row-weighted BCE is the sum of optimized batch losses times batch row counts divided by optimized row counts. The mean-step figure averages the full-precision step losses; native source-style epoch loss remains separately saved. EL losses are different weighted objectives across A/L/P and should not be read as directly comparable unweighted risk.

| Condition | EL row-weighted BCE | IM row-weighted BCE | IM mean-step BCE |
| --- | ---: | ---: | ---: |
| A | 0.07459771823145628 | 0.656963800769059 | 0.6594445233311609 |
| L | 0.06991785775758853 | 0.6606276532829437 | 0.662632337797468 |
| P | 0.07187570625464959 | 0.6615188367760895 | 0.6637087391915723 |

| Condition | Worker seconds | EL stage seconds | IM stage seconds | Sampled peak worker RSS bytes | Peak CUDA allocated bytes | Peak CUDA reserved bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| A | 1337.8465030550142 | 1267.1647243319894 | 2.0805709050036967 | 3605487616 | 1819815936 | 2015363072 |
| L | 1309.8427224739862 | 1256.2437260799925 | 2.006418342993129 | 3526057984 | 1819815936 | 2015363072 |
| P | 1320.8152864389995 | 1267.0203796979913 | 2.036727297003381 | 3606990848 | 1819815936 | 2015363072 |

A resources are historical Task 2.17 evidence; no A runtime was incurred here. L/P worker sequence and verification took 2637.9770309349988 seconds, within the existing 10,800-second budget. All workers exited 0 and remained within their 3,600-second/32-GiB limits. Stage RSS is the process high-water mark through stage completion; sampled worker RSS can miss a shorter peak. Exact stage RSS values are in the completion JSON.

L/P each saved 36 EL checkpoint tensors and four IM overlay tensors. EL reload and IM parent-plus-overlay reconstruction are bitwise identical, and all 383 development probabilities before/after reload are exactly equal (maximum absolute difference 0). Only the four approved IM condenser parameters changed. The launcher verified 60 worker-authenticated outputs per new condition (63 for historical A); the reduction in output-file count reflects reuse of source CSVs/provenance, not missing scientific evidence.

### Full-precision development metrics

AP means non-interpolated average precision with tied thresholds grouped. These are full-precision stored values, not the rounded display figures in the short narrative. All arms use the same 383 observations, 120 positive/263 negative.

| Condition | IM AP (primary) | IM AUROC | EL-proxy AP | EL-proxy AUROC |
| --- | ---: | ---: | ---: | ---: |
| A | 0.4761744527124684 | 0.6931242078580482 | 0.44803710957923926 | 0.6698035487959443 |
| L | 0.4667127124933836 | 0.6826045627376426 | 0.4363679737221111 | 0.658745247148289 |
| P | 0.46693727631116866 | 0.6890050697084917 | 0.44637198777346493 | 0.6680291508238276 |

| Contrast | IM AP | IM AUROC | EL-proxy AP | EL-proxy AUROC |
| --- | ---: | ---: | ---: | ---: |
| L-A | -0.009461740219084802 | -0.010519645120405596 | -0.011669135857128143 | -0.011058301647655311 |
| L-P | -0.00022456381778507284 | -0.006400506970849151 | -0.010004014051353816 | -0.009283903675538663 |
| P-A | -0.00923717640129973 | -0.004119138149556445 | -0.0016651218057743278 | -0.001774397972116648 |

The fixed one-sided L rule reduced primary IM AP versus A by about 0.009462 and versus P by about 0.000225 (rounded narrative figures). Both L and P were below A. Thus this one matched development run provides no predictive-utility benefit for L and no advantage of stability-specific assignment over the fixed permutation. The small L−P AP difference is descriptive; no equivalence or significance claim is justified. All secondary contrasts for L−A and L−P are also negative.

Descriptively, L IM AP (about 0.466713) exceeds the historical two-sided Task 2.17 B result (about 0.456615), but remains below the common A (about 0.476174). The current P (about 0.466937) is below historical two-sided P (about 0.475317). These are different weight distributions and totals, and do not identify which Task 2.17 operation caused its deterioration or establish a general weighting mechanism. No new Task 2.17 predictions were generated.

The result challenges predictive utility of this exact fixed one-sided intervention under this one-epoch, seed-42 development setting. It does not falsify the biological stability/repeat-detection hypothesis, establish false-positive EL labels, estimate label reliability, or measure repeat-detection probabilities. No repeat-detection opportunity panel is available. Teacher noise and allele-specific ranking quality remain limitations, and the post-Task-2.17 proposal and already viewed development cohort preclude an independent confirmatory interpretation.

### Deviations, engineering failure and retained artifacts

There were **no scientific protocol deviations, training failures or scientific retries**. One prelaunch engineering error occurred before run creation or optimizer updates: the new manifest input list included temporary `/tmp` CUDA/test reports, which the existing storage guard correctly rejected. Commit `02a6234` removed those reports from scientific inputs, retained them as output evidence with hashes in the compatibility receipt, and added a regression test. No scientific settings or training path changed. The failed prelaunch log and receipt are retained, and L/P each trained only once.

All new artifacts are under the resolved `task-2_19-low-stability-alp-gpu/` run. Key files:

- `reports/task2_19_completion.json`: full metrics, losses, resources, matching and scientific scope.
- `reports/alp_results.json`: all four endpoints and all three signed contrasts.
- `reports/baseline_A_reference.json` and `reports/baseline_compatibility.json`: immutable historical A binding and current compatibility proof.
- `reports/cuda_noop_equivalence.json`, `reports/input_preflight.json`, `logs/pretraining_tests.log`: actual passing gates.
- `reports/prelaunch_engineering_failure.json` and `logs/prelaunch_failure.log`: resolved pretraining error.
- `L/` and `P/`: separate manifests, configurations, stage receipts/logs, weight bindings, exposure fingerprints, loss trajectories, checkpoints, predictions and metrics.
- `reports/output_manifest.json`: launcher-authenticated artifact hashes; `reports/completion_artifacts.json` binds the subsequently written completion report to that manifest.

Existing Task 2.17 results/checkpoints remain in place and unchanged. No source dataset copies, downloads, checkpoint packages, extra conditions/seeds, hyperparameter search, sealed evaluation, merge or push occurred. The approved A/L/P experiment is complete; further scientific work requires a separate authorization.
