# Task 2.31 EL-only positive upweighting execution specification

Frozen before W/P training and before new W/P validation scores. Task 2.31's
explicit authorization supersedes historical preparation-only/IM instructions.
Use the exact Task 2.23 manifest, source populations, initialization, 10 epochs,
seed 42, native EL sampler, CUDA FP32 and AdamW lr5e-5/defaults. No new A fit,
IM payloads/transfer, auxiliary heads, Teacher fitting or independent benchmarks.
A's EL epoch-10 checkpoint and saved validation predictions must authenticate;
reuse predictions only after identity, runtime, unchanged inference-pathway
and same-batch checkpoint probe equality checks. Otherwise stop before training
and implement the authorized one-time full A scoring path, without model changes.

Score sidecar: original recovered Teacher hash, authenticated source/peptide/HLA
bindings. Subset to 63,053 **training** positives before ranking. Preserve exact
Decimal ties and rational mid-distribution ranks `(below+tied/2)/n` from the
existing Task 2.12/2.13 implementation. W is `max(1, old_two_sided_weight)`,
equivalent to `1+0.5*max(0,r-.5)`. P uses the historical source-ID ordered,
SHA256-domain-separated per-HLA Fisher-Yates stream with seed 42. All original
labels/observations persist; negatives have weight 1. Exact rational and FP32
per-HLA weight multisets and masses must match. Convert weights once to FP32.

Use the existing weighted batch-row-mean BCE adapter, never a sum-of-weights
denominator. Carry original prepared coordinates through native sampling.
Before GPU learning, regenerate all ten native CPU batch schedules and compare
with A. Compare complete initial tensor/RNG identities. During every epoch,
check each ordered batch hash **before** its update and check post-epoch RNG,
optimizer settings and persistent step counts. Same source batches across A/W/P.
Save all ten epoch histories and ordered validation predictions; only epoch 10
enters final contrasts, irrespective of intermediate results. Evaluation/reload
must preserve scientific RNG. Save/reload complete final EL checkpoints and
verify same-device probe prediction equality. No early stopping or search.

Primary developmental endpoint is pooled tied-score non-interpolated EL AP.
Secondary: AUROC, native all-row logit BCE, macro evaluable-HLA AP and per-HLA
AP/AUROC, with class counts; contrasts W-A, W-P, P-A. Use the same original
validation rows. Existing BigMHC EL code has no fixed-FPR recall implementation;
report that optional endpoint unavailable rather than invent an operating-point
convention. HLA win/loss summaries describe all evaluable alleles without choosing
a favored subset.

Exploratory paired uncertainty: reuse the existing Task 2.27 exact tied-score
`WeightedRanking` integer-multiplicity metric primitive. Draw 1,000 bootstrap
samples of the fixed number of **unique validation peptide groups**, local
NumPy `default_rng(23142)`; retain every observation/HLA of a selected peptide
with its sampled multiplicity, identically for all arms. Return percentile
2.5/97.5 contrasts for pooled AP/AUROC, usable/undefined draws and full draw
statistics. This is conditional internal-validation uncertainty, not biological
study/sample independence or an independent-test interval; no asymptotic p-value.
No additional seed or alternative resampling scheme.

Prespecified descriptive rank diagnostic: use only the training-positive score
reference to place each validation positive at `(training below + training tied/2)/n`.
Keep r<=.5 and r>.5 groups fixed; never add validation scores to training ranks.
Reuse the authenticated validation-positive sidecar scores, without new Teacher
predictions. Report mean pooled prediction percentile, mean predicted probability
and clipped-probability positive BCE in both groups (diagnostic only; primary
BCE remains native logit-space). No subgroup AP is promoted to primary, cutoff
search, synthetic-label change, or MS-detection outcome is used.

A's EL duration was previously selected on this validation set. Constructed
decoys, single seed/permutation, Teacher uncertainty/exposure and shared HLA/motif
structure constrain interpretation. The prior MS studies support neither this
weight formula nor coefficient. A W-P gain without W-A gain does not establish
practical improvement. No outcome triggers tuning, IM work or new benchmarks.
