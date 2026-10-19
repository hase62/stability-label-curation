# Task 2.24 — Fully trained stability auxiliary comparison

Branch `task/2.24-fully-trained-stability-auxiliary` starts at the exact approved
Task 2.23 commit `db54ac57464b6ad18e1ce8a6fc23e6dea321cb59`.
Status: focused CUDA tests and data/sampling preflight passed; execution pending. S/P GPU training is
authorized once per arm; independent benchmark access and evaluation are not.

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

Execution evidence and final frozen model identities will be recorded below
after the authorized training and read-only completion verification.

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
