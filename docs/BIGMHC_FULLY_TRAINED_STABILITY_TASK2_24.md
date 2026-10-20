# Task 2.24 — Fully trained stability auxiliary comparison

Branch `task/2.24-fully-trained-stability-auxiliary` starts at the exact approved
Task 2.23 commit `db54ac57464b6ad18e1ce8a6fc23e6dea321cb59`.
Status: **completed and frozen on Z790 WSL2 / RTX 4090**, 2026-10-20.
S/P each trained once; independent benchmark access and evaluation remain unauthorized.

The [configuration](../configs/bigmhc_fully_trained_auxiliary_task2_24.json)
freezes ten EL epochs followed by twenty original full-IM epochs for S/P.
A reuses Task 2.23's EL-10 / IM-20 final complete checkpoint on 3,428 original
IM observations. It is never retrained or scored in this task. Its previous
686-row validation subset is now fitting data for all final models and is
never treated as held out.

The shared [Task 2.20 auxiliary loop](../src/stability_label_curation/bigmhc_stability_auxiliary.py)
supports a persistent native AdamW optimizer across EL epochs. IM delegates
to the existing Task 2.23/native runner with a fresh optimizer and seed 42,
updating exactly the four native transfer parameters. Original labels,
native mean BCE, sampler, learning rate and CUDA FP32 architecture are retained.
The forward hook at `condenser.att` supplies the original 414-dimensional
representation to an isolated-seed-22042 linear 414-to-1 head (415 parameters).
S/P have identical initial backbones and heads. EL adds exactly 0.1 times
positive-anchor squared rank error; the auxiliary head never enters IM.

The existing Task 2.23 manifest is reused in place, with no regenerated split
or input copy: 1,308,196 training rows (63,053 positive / 1,245,143 negative),
145,371 validation rows excluded, and the original 11 exclusions retained.
Only the 63,053 training-positive source identities bind existing Teacher
scores. Within-HLA tie-aware exact midranks are computed **only within those
training positives**, then rounded once to FP32. This differs deliberately
from Task 2.21's full-70,069-positive rank reference population. It is a fixed
pre-execution data-separation requirement, not a fitted hyperparameter.
P permutes those exact ranks within the training HLA groups using the approved
source-ID-sorted independent deterministic stream, preserving exact and FP32
per-HLA multisets. IM and excluded/validation observations fit no ranks.

The [runner](../src/stability_label_curation/bigmhc_fully_trained_auxiliary.py)
authenticates A's final checkpoint, EL parent, original configuration and
training receipts. Focused gates check original BCE/gradient semantics,
head/backbone gradient flow, isolated RNG, target binding/permutation,
10/20-epoch optimizer persistence, native transfer/head exclusion and exact
reload. Before scientific updates, all ten EL and twenty full-IM ordered
sampling schedules and CPU sampler RNG states must match A. During scientific
training, every ordered batch and every full Python/NumPy/CPU/CUDA RNG boundary
must match A; any significant discrepancy stops execution without retries or
configuration relaxation. No new developmental epoch selection is performed.

Artifacts resolve through `stability_label_curation.paths` to project runs /
`task-2_24-fully-trained-stability-auxiliary/`. Stage and epoch receipts include
native BCE/auxiliary MSE, optimizer steps, ordered exposure hashes, RNG,
checkpoint lineage, reload probes on sixteen fitting observations, runtime
and GPU/host memory. Sixteen-row probes are engineering checks without
performance metrics or selection. Existing Task 2.23 artifacts are preserved.

The [locked independent evaluation protocol](BIGMHC_INDEPENDENT_ASP_EVALUATION_PROTOCOL.md)
fixes a single future A/S/P comparison with primary globally EL/IM-unseen AP,
secondary AUROC/P@10/P@20 and distinct IM-novel/EL-exposed analyses, identity-only
eligibility, tie rules, class balance and paired cluster uncertainty analysis.
No benchmark payload, outcome, prediction or score is accessed here.

Execution evidence and frozen model identities follow below. The independent
benchmark remains sealed.

## Completed preflight

The existing Z790 WSL2 / RTX 4090 environment passed **15 focused tests, zero
failures/errors/skips**, including an authentic small-width ten-EL/twenty-IM
schedule, disabled-auxiliary bitwise native equivalence, active S/P RNG and
batch matching, persistent AdamW, original BCE gradients, auxiliary gradient
flow and strict plain-backbone transfer. Full-width production initialization
matches all 36 A backbone tensors exactly; S/P head weight and bias match, with
scientific RNG unchanged. Runtime packages/device match Task 2.23 exactly.

All ten EL and twenty full-IM native ordered sampling schedules and CPU sampler
RNG boundaries matched A before scientific updates. CUDA forward RNG boundaries
are additionally checked during every scientific epoch. A's final sorted file
map SHA256 is `b92308ab3e35d02530867053ada7e29ee18076bf653df26458f5c3728a2be3a0`;
its final checkpoint, EL-10 parent, training receipts and shared settings passed
authentication. **Reuse A exactly; no material incompatibility found.**

Training-only Teacher ranks span `1/7928` to `12705/12706`, with total
`63053/2`. Every HLA has exact mean `1/2`. P changes 62,991 assignments and
retains 62 fixed/tied assignments, with identical per-HLA exact and FP32
multisets. All 63,053 scored training positives bind source coordinates,
original HLA/peptide/label and raw-row hashes without fallback. The ordered
training-manifest binding SHA256 is
`e8c54a96e82a4add61790a7cbcfad993b33b252a2fc95331746fdd521f3ee12a`.

An initial successful preparation pass exposed a receipt issue: live logs would
change after inclusion in the immutable artifact manifest. Before scientific
training, log authentication was moved to post-stage closure and finite-head
gradient receipts were added. The original tests/preflight/logs are preserved
as `*_preparation_01.*`; corrected focused tests and complete preflight passed.
No scientific optimizer update, target/setting revision or historical A fit
occurred during either preparation pass.

## Completed scientific execution

Execution commit: `78acffaeec105489a00f22780c374624ef5dc61f`. S and P each completed exactly ten EL epochs and twenty full-IM epochs, once each, with no scientific retry or model selection. A was reused in place without training or inference. All original Task 2.23 inputs, checkpoints and results remain unchanged.

Actual runtime: Python 3.13.5, PyTorch 2.13.0+cu130 / CUDA 13.0, NumPy 2.5.4, pandas 3.0.6; deterministic CUDA FP32, AMP/TF32 disabled, seed 42, native AdamW lr 5e-5, betas (0.9, 0.999), eps 1e-8, weight decay 0.01. No scheduler, external pretrained weights, new dependencies or downloads were introduced.

All 36 initial backbone tensors and full pre-EL RNG match A/S/P. The two initial head tensors match S/P exactly: weight SHA256 `d9d2c0b81c6da6dcec5ea5c1154cb1c81de175f390210d3e682fdddced20d600`, bias SHA256 `48539d64608e203ca5706652f5d8944c5d01f48ba09464affa961a98303b5b1c`. Head construction and per-HLA permutation consume no scientific RNG. All ten EL and twenty IM ordered batch lists, native negative-batch skip masks, optimizer defaults and Python/NumPy/Torch CPU/CUDA RNG boundaries match A/S/P exactly. Every optimizer state counter continues across its fit; IM begins with the original fresh-seed/fresh-optimizer semantics from its own arm’s EL-10 parent.

The first production native BCE is exactly equal to A in both S and P before auxiliary gradients change learned parameters. The focused authentic CUDA tests establish isolated auxiliary gradient flow into the head, attention projection, anchor branch and pMHC LSTM. Scientific fits check finite head gradients on **every EL update**, 630,530 per arm, and retain first-update head gradient norms in every epoch receipt. All 36 backbone tensors and both head tensors changed during each EL fit. Only the four native transfer tensors changed during IM.

## All ten EL epochs

These are sampled training diagnostics. BCE retains the native batch mean over all 17 actual rows; auxiliary MSE is one unscaled positive-anchor error. Total objective is calculated per update in FP32 as BCE + 0.1 × MSE. Tables display rounded values; full-precision per-update histories and epoch means remain in `reports/{S,P}_EL_epoch_XX.json` and `reports/{S,P}_EL_learning_curve.json`. A values below are existing Task 2.23 training receipts, without rescoring.

| Epoch | A BCE | S BCE | S auxiliary MSE | S total | P BCE | P auxiliary MSE | P total | Updates per arm |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.076768066628 | 0.077222383093 | 0.076644997372 | 0.084886882928 | 0.077674419912 | 0.097824608005 | 0.087456880845 | 63,053 |
| 2 | 0.059370350075 | 0.059167452639 | 0.057667366655 | 0.064934189377 | 0.059483324156 | 0.090721310913 | 0.068555455374 | 63,053 |
| 3 | 0.055513445561 | 0.055415593271 | 0.052890582431 | 0.060704651568 | 0.055784242854 | 0.091124986696 | 0.064896741656 | 63,053 |
| 4 | 0.053528972599 | 0.053322282317 | 0.050625941295 | 0.058384876517 | 0.053739390694 | 0.091612388679 | 0.062900629709 | 63,053 |
| 5 | 0.051916599715 | 0.051914840114 | 0.049628857223 | 0.056877725904 | 0.052362933038 | 0.091693826751 | 0.061532315857 | 63,053 |
| 6 | 0.050997286914 | 0.051019895757 | 0.048486806307 | 0.055868576451 | 0.051535610316 | 0.092466064590 | 0.060782216913 | 63,053 |
| 7 | 0.050312227644 | 0.050108912324 | 0.048091120724 | 0.054918024451 | 0.051010080599 | 0.092518328326 | 0.060261913564 | 63,053 |
| 8 | 0.049627475298 | 0.049407566526 | 0.047284493160 | 0.054136015914 | 0.050074841269 | 0.092819999341 | 0.059356841349 | 63,053 |
| 9 | 0.049189606828 | 0.048979856269 | 0.047302923007 | 0.053710148631 | 0.049533252820 | 0.093079044082 | 0.058841157361 | 63,053 |
| 10 | 0.048550949675 | 0.047996789226 | 0.047143875806 | 0.052711176883 | 0.048924528274 | 0.092979114472 | 0.058222439852 | 63,053 |

Each EL epoch consumes **1,071,901 sampled rows**: 63,053 positive anchors and 1,008,848 negative exposures. This matches native A sampling from the complete 1,308,196-row training pool; it does not claim every eligible negative is exposed each epoch. Each S/P fit therefore has **630,530 EL optimizer steps**, 630,530 positive and 10,088,480 negative exposures across ten epochs. All ordered exposure fingerprints match A. Eligibility in the future protocol conservatively excludes every EL training-pool sequence, including negatives never sampled.

## All twenty full-IM epochs

All models fit the complete 3,428-row original IM pool, with 955 positives and 2,473 negatives. Values below are update-row-weighted training BCE, not held-out performance. The original source-style epoch BCE, which includes skipped batches in its 215-batch denominator, and complete per-update traces are retained separately in every IM epoch receipt. There is no 383-row or 686-row developmental evaluation, AP/AUROC computation, or selection in Task 2.24.

| Epoch | A BCE (existing) | S BCE | P BCE | Updates per arm | Native skipped batches |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.726482873575 | 0.704154863796 | 0.699005012006 | 214 | 1 |
| 2 | 0.604699632539 | 0.585174265424 | 0.577315066355 | 214 | 1 |
| 3 | 0.561568322374 | 0.545823807193 | 0.544296295913 | 214 | 1 |
| 4 | 0.537034195321 | 0.523040902691 | 0.528617512804 | 215 | 0 |
| 5 | 0.522178870864 | 0.514849126130 | 0.516913726769 | 215 | 0 |
| 6 | 0.510252686416 | 0.505752842214 | 0.504637936076 | 214 | 1 |
| 7 | 0.499814460408 | 0.497225004497 | 0.494332022261 | 215 | 0 |
| 8 | 0.489892558224 | 0.487005720035 | 0.486146731226 | 214 | 1 |
| 9 | 0.483265263953 | 0.481111499098 | 0.483354444451 | 214 | 1 |
| 10 | 0.476226499280 | 0.475530403733 | 0.473224856126 | 213 | 2 |
| 11 | 0.465688042736 | 0.467304423224 | 0.469720125338 | 214 | 1 |
| 12 | 0.458961309828 | 0.460514947860 | 0.461979770829 | 213 | 2 |
| 13 | 0.455804876538 | 0.452915379129 | 0.457318258453 | 214 | 1 |
| 14 | 0.448681439622 | 0.451573326124 | 0.453674408144 | 211 | 4 |
| 15 | 0.442017068652 | 0.440843179106 | 0.442410983346 | 214 | 1 |
| 16 | 0.434019545319 | 0.433345657225 | 0.440931014020 | 214 | 1 |
| 17 | 0.430696964476 | 0.429439109437 | 0.434146989720 | 211 | 4 |
| 18 | 0.421282998737 | 0.420830844575 | 0.422306989275 | 214 | 1 |
| 19 | 0.417230133719 | 0.418293343323 | 0.422951967084 | 213 | 2 |
| 20 | 0.408369345996 | 0.410023801108 | 0.411237963448 | 213 | 2 |

Each arm executes **4,273 IM optimizer steps** from 4,300 sampled batches, with the same 27 native all-negative skips. Across twenty epochs the sampler covers 68,560 row instances; optimization consumes 68,188, including 19,100 positive and 49,088 negative exposures. The complete S/P experiment executes **1,269,606 scientific optimizer steps**. No A updates are included.

## Checkpoint lineage and reload

All four new EL/IM stage checkpoints are complete, self-contained authentic 36-tensor BigMHC checkpoints. IM reloads its own strict plain EL backbone with native ordered state keys and excludes the auxiliary head/hook. The separate two-tensor head files reload identically. All four complete backbone checkpoints pass exact tensor reload and exactly identical CUDA predictions on fixed sixteen-row fitting-data probes: maximum absolute difference **0.0**. These probes have no evaluation or selection role.

| Arm | Stage | Checkpoint under this run | Canonical file-map SHA256 |
| --- | --- | --- | --- |
| S | EL | `checkpoints/S_EL_epoch_10/` | `48550b057e2ccd1fef2f0ad8a181f34de074da8400bfb8cc74ca67a8f038c089` |
| S | IM | `checkpoints/S_IM_epoch_20/` | `9d5a5012d38b0f7f7203c35769a5a29e35572ced3b8f708a525c03a99996862a` |
| P | EL | `checkpoints/P_EL_epoch_10/` | `3d36692a4514154790a478a783ec665b9cf8d421d4a1268bbdd5917a4a3811c1` |
| P | IM | `checkpoints/P_IM_epoch_20/` | `01014a37c3a4101f90d7765e48420a463a7094169a8c0163fc5994dc4a0c903b` |

A remains exactly the referenced Task 2.23 `checkpoints/final_all_IM/`, with EL-10 parent, IM-20 full fit and canonical map SHA256 `b92308ab3e35d02530867053ada7e29ee18076bf653df26458f5c3728a2be3a0`. The 686 former internal-validation rows are part of its fitting pool and that of S/P; none is scored as held out here. Individual tensor/file hashes, auxiliary head identities and explicit EL parents are in `reports/{S,P}_{EL,IM}_checkpoint.json`; the authoritative model freeze is `reports/frozen_models.json`.

## Runtime and resources

Scientific workflow elapsed after input/binding setup: **22960.621 seconds (6.378 hours)**. Peak process host RSS: **3,347,750,912 bytes**. Stage synchronized training-loop times are sums of recorded epoch times; stage wall times also include checkpoint/reload/evidence work. Host high-water RSS is process cumulative, not an independently reset per-stage peak.

| Stage | Epochs | Wall seconds | Training-loop seconds | Peak GPU allocated bytes | Peak GPU reserved bytes | Host RSS high-water bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| S EL | 10 | 11453.445 | 11449.919 | 1,963,749,376 | 2,275,409,920 | 3,335,958,528 |
| S IM | 20 | 41.375 | 39.224 | 1,283,546,624 | 2,275,409,920 | 3,335,958,528 |
| P EL | 10 | 11413.507 | 11410.013 | 1,962,165,760 | 2,275,409,920 | 3,347,750,912 |
| P IM | 20 | 42.919 | 40.701 | 1,283,546,624 | 2,275,409,920 | 3,347,750,912 |

766 valid nvidia-smi snapshots at approximately 30-second intervals, 0 failed. GPU utilization mean/max **68.74/74%**; system VRAM maximum **3206 MiB**; power mean/max **236.45/244.93 W**; temperature maximum **61 °C**. System snapshots include display/other device use and differ from Torch allocator peaks. These are actual WSL2/RTX 4090 measurements.

## Final verification, frozen protocol and stop

The [read-only completion verifier](../scripts/verify_bigmhc_fully_trained_auxiliary.py) passed: **297 authenticated scientific artifacts**, every saved BCE/auxiliary-MSE history recomputed from update receipts, all ten/twenty optimizer and RNG continuities, A/S/P ordered sampling/skip/default matches, per-HLA target invariants, initial state identities, final checkpoint files and transfer/reload receipts verified. It performs no model inference or benchmark scoring. Closed logs and resources are separately authenticated in `reports/finalization_manifest.json`; verification is in `reports/completion_verification.json`.

Important run reports: `baseline_compatibility.json`, `cohort_binding.json`, `target_permutation.json`, `initialization.json`, `sampler_preflight.json`, `focused_tests.json`, `preflight.json`, all stage/epoch/learning-curve/checkpoint receipts, `frozen_models.json`, `completion.json`, `output_manifest.json`, `completion_verification.json`, `resource_summary.json`, and `finalization_manifest.json`, all under this run’s `reports/`. Logs include focused tests, both preparation attempts, scientific stdout and GPU telemetry.

**A/S/P models and the complete independent evaluation protocol are frozen.** Protocol SHA256: `cb386443d768fb168366299ae7125aeec7115dda4e81da2dce62d90b4b99d250`. The [locked protocol](BIGMHC_INDEPENDENT_ASP_EVALUATION_PROTOCOL.md) fixes globally EL/IM-unseen AP as primary, IM-novel exposure strata as secondary, AUROC/P@10/P@20, S−A/S−P/P−A, common eligible rows, identity-only exclusions, score ties, class balance and paired cluster bootstrap uncertainty. Benchmark eligibility counts, exclusions and HLA distribution remain unknown here; they must be reported in the future authorized identity review without relaxing the frozen rules.

**No scientific deviations or training failures occurred.** The preparation-only log-manifest correction described above did not change scientific settings. Training-only ranks differ from Task 2.21 exactly as prespecified. No coefficient/head/epoch search, label changes, A retraining, new developmental evaluation, downloads, persistent input copies, backup archives, merge or push occurred. **Sealed independent benchmark payloads, outcomes, predictions and scores were never accessed.** Work stops after S/P training, verification and protocol preparation.

The training loss histories do not establish independent predictive benefit. Prior one-epoch auxiliary experiments gave no convincing stability-specific improvement; Task 2.23’s stronger developmental baseline motivates this new frozen comparison. It does not test EL repeat-detection probability, and Teacher-predicted kinetic stability is not verified EL-label correctness or measured stability. Measured kinetic half-life and thermal melting temperature remain separate. Even a positive future independent comparison would require uncertainty analysis and external replication before broad generalization.
