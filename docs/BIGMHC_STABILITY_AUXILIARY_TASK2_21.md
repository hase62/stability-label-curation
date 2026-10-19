# Task 2.21 — Z790 stability auxiliary A/S/P execution

Execution is authorized by Task 2.21, starting at main
`8f827b47920c2ae56f0098f4ae6170a7ad322692`, on branch
`task/2.21-stability-auxiliary-gpu`. The fixed scientific protocol remains
[Task 2.20](BIGMHC_STABILITY_AUXILIARY_PROTOCOL.md) and the canonical
`configs/bigmhc_stability_auxiliary_task2_20.json` is unchanged.

The only runner change is the output run ID, now
`task-2_21-stability-auxiliary-gpu`. Follow the protocol's Z790 commands with
preflight directory `task-2_21-z790-preflight`; use its explicit authorized
configuration copy. No inputs are copied or downloaded. S/P each run once;
historical A is referenced in place if all gates pass. No sealed outcomes
are accessed.

## Pretraining evidence

Actual platform: Z790 WSL2, NVIDIA GeForce RTX 4090, existing Python 3.13.5,
PyTorch 2.13.0+cu130 / CUDA 13.0. The protocol's eight related unittest
modules passed 163 tests without failures or skips. The current authentic
synthetic CUDA gate passed all 12 tests without skips. Evidence is in resolved
project runs / `task-2_21-z790-preflight`, under `logs/relevant_tests.log`,
`logs/synthetic_cuda_gate.log`, and `reports/synthetic_cuda_gate.json`.

The strict 17-row historical-A CUDA compatibility gate passed: native and
historical unit-weight BCE both equal `0.6862132549285889`; all gradient and
post-AdamW tensors are exactly equal, with maximum absolute differences 0.
Therefore historical A reuse is selected, subject to the unchanged full-cohort,
artifact, runtime, initialization, sampling and RNG gates. No tolerance changed.

S/P use native BCE plus 0.1 times positive-anchor squared rank error, the
isolated seed-22042 414-to-1 head, and the original native training schedule.
The launcher required a clean committed source tree before scientific work.
Execution used commit `ca1bd9629079f7f0ad286731f3ed4773c3d14d8d`.

## Completed execution and evidence

Status: completed. S and P each trained exactly once, with one EL epoch and
one IM epoch. A was reused from `task-2_17-abp-comparison/A`, authenticated
against Task 2.17 commit `02313b20da218dbcacdbb2cbee5f5d435b258a18` and
the protocol's pinned matched-state SHA256. No new A training or inference
was performed. Full-cohort input/provenance and historical-artifact preflight
passed, and runtime package versions/device matched A exactly.

All new scientific artifacts are in resolved project runs /
`task-2_21-stability-auxiliary-gpu/`. Important evidence files are:

- `reports/input_preflight.json`, `reports/baseline_compatibility.json` and
  `reports/synthetic_cuda_gate.json`.
- `reports/target_permutation.json` and `reports/configuration_S.json` /
  `reports/configuration_P.json`.
- `S/` and `P/`: independent checkpoints, predictions, complete batch loss
  trajectories, initial tensor identities, RNG boundaries, ordered sampled
  source fingerprints, stage start/completion evidence and resource receipts.
- `reports/verification_S.json`, `reports/verification_P.json`,
  `reports/asp_results.json` and `reports/output_manifest.json`.
- `reports/task2_21_completion_verification.json`: final saved-artifact
  conformance checks, including all three arms' authenticated training reports,
  prediction identities, recomputed development metrics and fixed contrasts.
  This verification performed no additional training or model inference.

The eight related unittest modules passed 163 tests; the authentic CUDA suite
passed 12 tests. Both had zero failures and zero skips. The final completion
verification passed. All original worker-output hashes and the launcher's output
manifest were verified; the completion receipt is an additional immutable report
and binds that original manifest's hash. Historical artifacts were read in place.

Result SHA256 (`reports/asp_results.json`):
`374c932645dcd45d27652b13e6cfcee1a91a97c16430759809081c28fa44f227`.
Original output-manifest SHA256:
`0dd345962615a49a17ffd09910f85dd6f07666263ae1261286dff4414f8e0779`.

## Initialization, sampling, targets and transfer

All 36 initial backbone tensors match A/S/P exactly. S/P head weight and bias
also match exactly. Head construction uses isolated CPU seed 22042; CUDA tests
confirmed unchanged Python, NumPy, Torch CPU/CUDA RNG and backbone parameters
across construction. Scientific EL and IM RNG boundaries equal historical A.

The exact ordered source-ID/original-label batch sequences, shared AdamW
defaults, backbone parameter order, step counts and skip masks match A/S/P.
S/P append the same 415 head parameters to the original optimizer group.
AdamW retains lr 5e-5, betas (0.9, 0.999), eps 1e-8, weight decay 0.01 and
all other original runtime defaults. CUDA FP32 and deterministic execution
were used with AMP and TF32 disabled.

Common ordered-batch-list digests:

- EL: `32a9e94677ef4e1b1f3e7863601155843b623da92e074f4e5802f6a0d7c2e886`.
- IM: `2d84f5d5d6b29ad5c1538c01f297e9a6fa9b2c0fd767d3414ecccef473a1215e`.

The complete original populations remain 1,453,578 EL and 3,428 IM observations.
Native EL sampling produced 70,069 batches/updates of 17 rows each, consuming
1,191,173 sampled observations: 70,069 positive and 1,121,104 negative exposures.
Native IM produced 215 batches and 214 updates; the same all-negative batch 48
(16 rows) was skipped in every arm. IM optimization consumed 3,412 rows
(955 positive / 2,457 negative); sampling still covered all 3,428 rows.

All 70,069 positive Teacher targets across 49 HLAs were bound. S/P identity sets,
counts, exact-rational and FP32 per-HLA multisets match. Every exact per-HLA
mean is 1/2. P changed 70,007 source-to-target assignments and retained 62
fixed/tied assignments, without redraw. Negatives and IM have no targets.

IM used only the strict plain BigMHC reload of each arm's own EL checkpoint,
updating exactly `condenser.att.weight`, `condenser.att.bias`,
`condenser.out.weight`, `condenser.out.bias`. The head and hook were excluded.

## Optimizer losses and gradient evidence

The following are arithmetic means over actual optimizer updates. Auxiliary
MSE is unscaled; total EL objective is native BCE plus 0.1 times MSE, calculated
in FP32 per update. A's EL total is its authenticated historical BCE.

| Arm | EL mean BCE | EL mean auxiliary MSE | EL mean total objective | IM mean update BCE |
| --- | --- | --- | --- | --- |
| A (historical) | 0.07459771823145628 | — | 0.07459771823145628 | 0.6594445233311609 |
| S | 0.07554319403488106 | 0.07486246047796724 | 0.08302944017943183 | 0.6365847921817103 |
| P | 0.07593205745331155 | 0.09673633936615411 | 0.08560569153676664 | 0.6486417708970676 |

Native IM source-style epoch losses (including the skipped batch in the
denominator) were A `0.6563773395017137`, S `0.6336239326831904`,
P `0.6456248324277786`. IM row-weighted BCE was A `0.656963800769059`,
S `0.6339946823131297`, P `0.6462374263883056`. Full per-update trajectories
are retained; no checkpoint was selected using these losses or development data.

The authentic CUDA test separately backpropagated auxiliary MSE and verified
nonzero gradients in the head, `condenser.att`, anchor branch and pMHC LSTM.
Scientific training checked finite head gradients on every update. Both head
weight/bias and backbone states changed in each scientific EL run. These are
gradient-path and update checks; scientific component gradient norms were not
separately logged. S's lower auxiliary loss does not alone establish predictive
utility or accurate biological kinetic-stability estimation.

## Checkpoint reloads and resources

Each S/P arm saved 36 authentic EL tensor files, a four-file immediate-parent
IM overlay and a separate tensor-only auxiliary-head checkpoint. All three
checkpoint reloads were strictly identical to their saved states. Only the
four authorized backbone tensors changed during IM. All 383 EL-proxy and 383 IM
probabilities per arm were exactly identical after checkpoint reload inference:
maximum absolute difference 0. The existing CUDA comparison tolerances remained
unchanged; actual agreement was exact. A's saved evidence was authenticated
without rescoring it. Saved prediction identities match across all arms, and
metrics recomputed from saved probabilities agree exactly.

Stage times below are synchronized wall times on the RTX 4090, not CUDA kernel
profiler times. Worker times include loading, inference, saves and verification.
A timings are historical and are not new Task 2.21 compute.

| Arm | EL seconds | IM seconds | Whole worker seconds | Peak monitored worker RSS bytes |
| --- | --- | --- | --- | --- |
| A (historical) | 1267.1647243319894 | 2.0805709050036967 | 1337.8465030550142 | 3605487616 |
| S | 1283.9001316369977 | 2.053780774003826 | 1297.795949329011 | 2361577472 |
| P | 1282.9320164970122 | 2.427092904021265 | 1297.0307069900155 | 2367954944 |

Both new workers exited 0 without a budget blocker, within 3,600 seconds and
32 GiB RSS each. S/P EL peak GPU allocated memory was 1,819,857,920 bytes;
IM peak allocated memory was 1,060,154,880 bytes. Peak reserved GPU memory was
2,015,363,072 bytes in both stages for both arms. Per-stage host high-water
RSS and all original resource receipts are retained in the run.

## Frozen-development results

Exactly 383 original IM development observations (120 positive / 263 negative,
31 HLAs) were evaluated. AP is non-interpolated average precision with tied
scores grouped. Values below preserve the saved Python float round-trip
precision. No sealed independent evaluation outcomes were accessed.

| Arm | IM AP (primary) | IM AUROC | EL-proxy AP | EL-proxy AUROC |
| --- | --- | --- | --- | --- |
| A | 0.4761744527124684 | 0.6931242078580482 | 0.44803710957923926 | 0.6698035487959443 |
| S | 0.4766054149963631 | 0.6961977186311787 | 0.45464123382745497 | 0.6712927756653992 |
| P | 0.4616911010219029 | 0.6923003802281369 | 0.45302366952864437 | 0.6717997465145754 |

| Contrast | IM AP | IM AUROC | EL-proxy AP | EL-proxy AUROC |
| --- | --- | --- | --- | --- |
| S−A | 0.00043096228389472024 | 0.003073510773130561 | 0.006604124248215715 | 0.0014892268694549626 |
| S−P | 0.014914313974460192 | 0.00389733840304185 | 0.0016175642988106032 | -0.0005069708491761693 |
| P−A | -0.014483351690565471 | -0.000823827629911289 | 0.004986559949405112 | 0.001996197718631132 |

## Deviations, interpretation and stop

There were no scientific protocol deviations, retries, additional training runs,
coefficient changes, new seeds, downloads, data copies or checkpoint selection.
The user-authorized execution differences from the preparation instructions were
the Task 2.21 output/preflight directory names and the explicit authorized
configuration copy. The canonical scientific configuration was not changed.

S essentially matched A on the primary endpoint: IM AP increased by only
0.00043096228389472024. S exceeded P by 0.014914313974460192, but most of
that gap reflects P's 0.014483351690565471 decline relative to A. This result
does not establish a robust predictive benefit from stability supervision.
The real target assignments performed better than the permuted assignments on
IM AP in this run; a useful stability-specific effect remains possible, with
substantial uncertainty from one seed and one permutation. Generic auxiliary
regularization did not improve primary IM AP in P. Both S and P improved
EL-proxy AP, so that secondary improvement cannot be attributed solely to
stability-specific supervision; a generic auxiliary effect could contribute.

This is the third exploratory comparison on an already viewed, modest
development cohort. No inferential significance or external generalization is
established. Teacher-derived within-HLA ranks are estimates of kinetic
stability, distinct from measured kinetic half-life and thermal melting
temperature. The result does not establish EL-label errors or repeat-detection
reliability, and the near-null primary gain does not falsify the kinetic-stability
hypothesis. Teacher noise, HLA-specific rank quality and adaptive development
reuse remain limitations.

The approved A/S/P experiment is complete. No subsequent experiments, broad
audits, backups, merge or push were performed.
