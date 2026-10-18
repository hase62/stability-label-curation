# Task 2.20 — Stability auxiliary supervision for authentic BigMHC

Status: protocol and implementation preparation only. No scientific training,
new development inference, sealed-test inspection, package installation, artifact
upload or new input acquisition is authorized by this task. The shipped
configuration disables training. Future execution requires separate authorization.

Base: fetched `origin/main` at `7f6325783c205be61f4ff68a134b2682dd35316b`.
Branch: `task/2.20-stability-auxiliary-supervision`. The unfinished Task 2.8
checkout and all existing worktrees, runs and checkpoints are preserved.

## Scientific question and fixed design

Task 2.17 B−A IM AP was −0.019560 and B−P was −0.018702. Task 2.19
L−A was −0.009462 and L−P was −0.000225. Neither weighting rule improved
IM prediction on the frozen 383-observation development cohort. This third
exploratory evaluation asks whether Teacher-derived, HLA-relative kinetic
stability can inform a shared representation while the original EL objective
continues to predict the original labels.

| Arm | EL objective | IM stage |
| --- | --- | --- |
| A | Authentic original-label BCE; reuse authenticated Task 2.17 A | Existing original transfer |
| S | Same BCE + 0.1 × positive-anchor stability MSE | Own EL parent, original transfer |
| P | Same architecture, BCE, coefficient and target distributions; HLA-local permuted ranks | Own EL parent, original transfer |

There is no label flipping, observation exclusion, BCE reweighting, target
renormalization, absolute half-life threshold, new seed, coefficient selection,
architecture search or selection using development results. The coefficient
0.1 is a fixed exploratory design choice, without biological calibration.

## Target definition and binding

For each HLA h, let n_h be its number of scored original EL-positive source
observations, s_i its existing Teacher-predicted kinetic half-life, b_i the
number of those scores strictly below s_i and t_i the number equal to s_i,
including itself. Define

\[
r_i = (b_i+t_i/2)/n_h.
\]

This is the existing percentile midrank, with numeric-text ties retained by
Decimal comparison. Implementation obtains it exactly from the existing rank
utility's rational weight, `r = 2*w - 3/2`, where `w = 3/4 + r/2`. This algebra
reuses the rank convention; the resulting ranks are regression targets and
are never used as BCE weights. Exact rational values are rounded once to FP32
for training. Larger r denotes higher estimated within-HLA kinetic stability.
All-tied and singleton groups have target 1/2. Every per-HLA mean is 1/2.

Only the existing Task 2.13 score sidecar and manifest are consumed: 70,069
positive observations across 49 human HLA-I alleles. The configuration pins
both existing hashes, the frozen EL view, raw source archive and Teacher model
`a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99`.
The existing authenticated identity wrapper retains original source member,
row index, raw-row hash, prepared index, HLA, peptide and original label through
native sampling. Missing, extra, duplicate or mismatched positive bindings fail
without fallback. Negatives have no auxiliary target. IM data never fit ranks.

P permutes ranks among source identities separately within each HLA. Sort
identities lexicographically and use explicit Fisher–Yates with a local
`random.Random` seeded by the integer SHA256 of UTF-8 bytes
the NUL-separated fields `hla_relative_stability_auxiliary_v1`, `targets`,
`42`, and the canonical HLA string. The exact implementation uses
`f'{VERSION}\0targets\0{42}\0{hla}'.encode()`.
This independent stream consumes no Python, NumPy, Torch CPU or CUDA training
RNG. Existing sidecar Python version pin 3.13.5 is retained. Exact rational and
FP32 per-HLA multisets, identity sets, counts and means must match S/P; assignment
digests are recorded separately. Fixed points and unchanged ties are allowed;
there is no redraw to make a more favorable permutation.

## Authentic representation and auxiliary architecture

Pinned BigMHC source commit:
`199e890fa69a63646730bcecea0a520e08ca4f02`. Inspection of
`BigMHC.Condenser.forward` establishes that `condenser.att` outputs a fused
414-dimensional peptide–HLA attention projection. It precedes the original
multiplication by `condenser.out.weight`, HLA mask, sum and output bias.

A temporary forward hook captures this projection from the single authentic
EL forward pass, retaining its autograd graph. A separate unbounded affine
head predicts `r_hat = a^T z + c`. It contains **414 weights + 1 bias = 415
trainable parameters**. No hidden layer, activation or head dropout is added.
The authentic classification forward, backbone source and tensor namespace
remain intact. MSE gradients reach the head, attention projection, anchor
branch and pMHC LSTM. The head does not become a BigMHC submodule.

The head is initialized on CPU using its own fixed seed 22042 inside
`torch.random.fork_rng(devices=[])`, seeding only the CPU default generator and
restoring it afterward. CUDA generators are never reseeded by head creation.
Copying the head to the chosen device consumes no random draws. S/P retain
identical seed-42 backbones, head initial tensors and native training RNG.

## Loss, optimization and transfer

For native EL batch B with exactly one first-position positive anchor p(B),
classification logits l_j and unchanged labels y_j:

\[
L_{EL}(B)=|B|^{-1}\sum_{j\in B}\mathrm{BCEWithLogits}(l_j,y_j),
\qquad
L_{aux}(B)=(\hat r_{p(B)}-r_{p(B)})^2,
\]
\[
L_{total}(B)=L_{EL}(B)+0.1 L_{aux}(B).
\]

The auxiliary term is one squared error, without division by the batch size.
The BCE denominator remains all native batch rows, including negatives. Native
full-population batches contain 17 rows at configured batch size 16. Unexpected
anchor placement/counts fail. Head prediction is unbounded; only targets are
ranks in [0,1].

The existing native `makebats(shuffle=True, negfrac=0.99)` and shuffled
`DataLoader(batch_size=None, num_workers=0, persistent_workers=False)` are
retained. AdamW receives original backbone parameters in their original order,
followed by head parameters in the same group. All shared hyperparameters and
scheduling remain original: lr 5e−5 and the runtime's original AdamW defaults,
checked against A; no new scheduler. FP32 and deterministic execution, with
AMP and TF32 disabled, remain mandatory.

The independent head checkpoint contains only its weight/bias and has its own
hash, initial/trained tensor identities, target-assignment evidence and trained
EL parent identity. Original BigMHC save/load produces the same 36 EL tensor
files, then a strict plain BigMHC reload becomes the IM parent. No auxiliary
head, hook or loss reaches IM. The unchanged IM epoch updates only
`condenser.att.weight`, `condenser.att.bias`, `condenser.out.weight`,
`condenser.out.bias`, saving the original four-file immediate-parent overlay.
Auxiliary and EL/IM checkpoints undergo strict tensor reload checks; all 383
saved EL-proxy/IM probabilities are checked against checkpoint reload inference.

## Comparability and baseline reuse gates

Keep 1,453,578 original EL observations (70,069 positives / 1,383,509 negatives),
3,428 original IM observations (955 positives / 2,473 negatives), seed 42,
one EL epoch and one IM epoch, and the same frozen 383-row development cohort
(120 positives / 263 negatives across 31 HLAs).

A is the existing `task-2_17-abp-comparison/A` from commit
`02313b20da218dbcacdbb2cbee5f5d435b258a18`. Its matched-state SHA256 is
`bfcbdc71c98c732650214c7592e396e526094596329bd0e5aa016aa9823c5cb2`.
Scientific configuration identity remains
`fcc1d7b396d7ac4cecf47b2d123f8ec549074b3defb63fee0ffd79dfa4c416c1`.
Changing this task's source commit alone does not require A retraining.

The existing baseline/weighted runner and compatibility module remain unchanged.
A dedicated auxiliary EL loop uses the same schedule/optimizer steps and
original BCE, with the head and auxiliary term added. IM uses the existing
`train_epoch` directly. Before future scientific execution, existing read-only
full-cohort preflight and historical-A authentication must pass; this includes
unchanged baseline scientific ASTs and the reviewed historical worker I/O
differences. No scientific input CSV/provenance is copied.

A current authentic synthetic CUDA gate must prove native BCE and
auxiliary-disabled loss/gradient/AdamW equivalence, and separately establish
exact numerical compatibility with historical unit-weight A on 17-row batches. The
complete auxiliary-disabled synthetic EL epoch must match native final tensors,
BCE history and RNG. Active S/P must match native ordered sampled batches and
RNG boundaries. The gate binds implementation, canonical configuration and
test source hashes, rejects skips, and is followed by runtime identity gates.

Before each scientific EL update compare its ordered source-ID/original-label
batch fingerprint to A. Before EL/IM compare Python/NumPy/Torch CPU/CUDA RNG
boundaries. Check all 36 initial backbone tensors, S/P initial head tensors,
shared optimizer defaults/parameter order, full stage batch schedules, skip
masks and step counts. Expected EL steps: 70,069; IM: 214 updates from 215
batches, with the same all-negative batch skipped. IM retains original loss
and sampling. Runtime package versions and device must match A. Failures stop
without automatic retries or A retraining. Each new worker is bounded at
3,600 seconds and 32 GiB RSS and runs in its own process.

## Evaluation and interpretation

Primary endpoint: IM non-interpolated average precision, with tied score
thresholds grouped. Secondary endpoints: IM AUROC and EL-proxy AP/AUROC.
Report full-precision **S−A, S−P, P−A** for all four metrics. Reuse A's saved
frozen-development probabilities/metrics after authentication; do not rescore A
or inspect sealed independent test outcomes.

Stage receipts distinguish BCE, positive-anchor MSE and total objective; they
retain trajectories, shared/auxiliary optimizer registration, ordered sampling
fingerprints, initialization/RNG identities, checkpoint lineage, runtime and
memory evidence. Final reporting verifies saved probabilities/metrics and
artifact hashes. Historical runs are referenced in place.

This is a third exploratory evaluation on an already viewed development cohort,
following Tasks 2.17 and 2.19. No coefficient/head/training tuning or checkpoint
selection is permitted. Improvement could indicate predictive utility of this
Teacher-derived auxiliary signal. It would not establish EL-label errors,
EL repeat-detection reliability or a biological causal mechanism. Teacher
predictions estimate kinetic stability, not ground-truth EL detection
probabilities. Thermal melting temperature remains a separate measurement.
Teacher noise, HLA-specific rank quality, one seed/permutation, the modest
cohort and adaptive reuse of development outcomes limit inference. A negative
result would not falsify the kinetic-stability hypothesis.

## Planned Z790 / WSL2 / RTX 4090 commands

These commands are **future instructions**, not executed in Task 2.20.
Use the existing GPU environment and existing storage; install/download nothing.
First review and commit the implementation, then run synthetic gates. All
paths to scientific inputs/outputs are resolved by `stability_label_curation.paths`.
The established Z790 interpreter is `~/codex/.venvs/bigmhc-gpu/bin/python`.

```sh
cd ~/codex/repos/stability-label-curation
SLC_GPU_PYTHON=~/codex/.venvs/bigmhc-gpu/bin/python
export PYTHONPATH=src:tests
export CUDA_VISIBLE_DEVICES=0
export CUBLAS_WORKSPACE_CONFIG=:4096:8
SLC_PREP="$($SLC_GPU_PYTHON -B -c 'from stability_label_curation.paths import resolve_paths; print(resolve_paths().project_runs_dir / "task-2_20-z790-preflight")')"
"$SLC_GPU_PYTHON" -B - "$SLC_PREP" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
p.mkdir(exist_ok=False)
(p / 'reports').mkdir()
(p / 'logs').mkdir()
PY
set -o noclobber
"$SLC_GPU_PYTHON" -B -m unittest \
  test_bigmhc_stability_auxiliary test_bigmhc_low_stability \
  test_bigmhc_abp_experiment test_bigmhc_baseline_runner \
  test_bigmhc_gpu_worker test_el_stability_loss_adapter \
  test_el_positive_weighting_design test_el_low_stability_design -v \
  > "$SLC_PREP/logs/relevant_tests.log" 2>&1
"$SLC_GPU_PYTHON" -B -m stability_label_curation.bigmhc_auxiliary_experiment \
  synthetic --device cuda --report "$SLC_PREP/reports/synthetic_cuda_gate.json"
```

The canonical configuration is
`configs/bigmhc_stability_auxiliary_task2_20.json`, with
`auxiliary.training_authorized=false`. **Only after separate authorization for
one scientific S/P run**, create its explicit authorized copy and execute:

```sh
"$SLC_GPU_PYTHON" -B - "$SLC_PREP" <<'PY'
from pathlib import Path
import sys
from stability_label_curation.paths import resolve_paths
from stability_label_curation import bigmhc_auxiliary_experiment as experiment
from stability_label_curation import bigmhc_baseline_runner as runner
paths = resolve_paths()
c = experiment.load_config(paths.repository_root / experiment.CONFIG, paths)
c['auxiliary']['training_authorized'] = True
runner.raw.write_report(Path(sys.argv[1]) / 'reports/authorized_configuration.json', c, paths=paths)
PY
"$SLC_GPU_PYTHON" -B -m stability_label_curation.bigmhc_auxiliary_experiment \
  run --config "$SLC_PREP/reports/authorized_configuration.json" \
  --gate-report "$SLC_PREP/reports/synthetic_cuda_gate.json" \
  --test-log "$SLC_PREP/logs/relevant_tests.log"
```

The fixed new destination is resolved project runs /
`task-2_20-stability-auxiliary/`, containing S/P and a referenced A.
Existing destinations and evidence files are rejected; runs are never
replaced. `reports/asp_results.json` will contain all fixed contrasts.
A CPU gate cannot authorize CUDA execution. If the CUDA gate, runtime identity,
input/cohort binding or historical evidence fails, retain the failure and resolve
it before any separately authorized scientific run. Do not silently change
settings or force A retraining.

## Actual Mac preparation evidence

Existing environment: Python 3.13.5, PyTorch 2.14.1, macOS CPU. No package was
installed. Focused tests execute pinned authentic BigMHC with hidden width 4
and its original 36-tensor structure, native encoders/sampler and synthetic
observations only. Production configuration retains authentic hidden width 1024
and two layers. The shared output and 415-parameter head widths are identical
in both settings.

The twelve focused checks include exact native/auxiliary-disabled BCE values,
gradients and AdamW updates; complete disabled
EL-epoch final tensor/RNG equivalence; active S/P native 17-row batching and
RNG matching; head/backbone gradient flow; target ties/binding/permutation;
and original IM four-parameter updates/parent overlay excluding the head.
The focused and related historical suites total **163 tests passed, zero failures
or skips** in the final validation log.

Reading only the existing score sidecar confirmed **70,069 positives / 49 HLAs**,
matching per-HLA exact-rational and FP32 multisets. P changes **70,007** target
assignments and retains 62 fixed/tied assignments. Target minimum is `1/8742`,
maximum `14175/14176`, total `70069/2`; each HLA mean is exactly `1/2`.
No development model inference or scientific optimizer update was performed.

Validation evidence is under resolved `CODEX_RUNS_ROOT=/private/tmp/task220-validation-runs`,
project run `task-2_20-mac-preparation`: `logs/relevant_tests_preparation.log`,
`reports/synthetic_cpu_gate_preparation.json` and `reports/teacher_target_binding.json`.
These are small validation outputs; scientific inputs stayed in existing project
storage. CUDA/WSL2 and full-size scientific training remain unexecuted. There is no architecture integration blocker.

**Historical A numerical compatibility is unresolved for GPU reuse.** A focused
17-row synthetic CPU probe found equal loss `0.6878083348274231` for native
mean BCE and historical A's `mean(unit_weight * unreduced_BCE)`, but differences
in 29 gradient tensors (maximum absolute difference `9.313225746154785e-10`)
and 14 post-AdamW tensors (maximum `7.450580596923828e-09`). Moving the mean
reduction across the BCE autograd kernel is not bitwise neutral on this CPU.
The exact native/auxiliary-disabled comparisons pass; native BCE is retained.
The diagnostic records these differences without introducing a tolerance for A
reuse. This prevents claiming historical A bitwise equivalence from Mac evidence.

The future CUDA diagnostic repeats that 17-row comparison and rejects reuse if
loss, gradients or AdamW tensors differ. If it fails, scientific S/P execution
stops before run creation. Resolve baseline numerical compatibility through
review; no A retraining, alternate reduction, tolerance relaxation or scientific
redesign is authorized here. This is an engineering limitation to A reuse,
separate from the accessible architecture. No CUDA/WSL2 compatibility is claimed.
