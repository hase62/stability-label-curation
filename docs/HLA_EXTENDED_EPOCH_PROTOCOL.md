# HLA extended A/W/L training — prospective protocol, 2026-11-02

This user-authorized experiment investigates whether one-epoch EL/IM pilots
undertrained, without changing or replacing any historical result. New work is
isolated from all prior worktrees. Base is Task2.41b commit
`ba19137ede817d32f7df35a30d7a735f4fdd1e1d`; the authoritative machine-readable
configuration is `configs/hla_extended_epoch_training.json`.

## Fixed comparison

Use authentic source BigMHC `199e890fa69a63646730bcecea0a520e08ca4f02`,
the exact Task2.23 peptide-disjoint EL partition (1,308,196 training rows,
63,053 positives; 145,371 validation rows, 7,006 positives) and all original
3,428 IM training observations (955 positives). No resplitting or relabeling.
Teacher is the authenticated original positional Ridge kinetic half-life model
`a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99`;
reuse its source-bound historical positive-score sidecar, without rescoring.

Paired seeds are **42, 123, 456**, fixed before any new training or external
scoring. A42 reuses the authenticated Task2.23 EL10 and full-IM20 checkpoints;
A123/A456 and all W/L are new fits. W denotes Task2.17's two-sided B intervention,
not Task2.31's upper-only W. Within each training HLA, use the original numeric
tie-aware midrank r=(number below + half tie count)/n:

* A: all weights 1.
* W: positive weight 1+0.5*(r−0.5).
* L: positive weight min(1,1+0.5*(r−0.5)).

All negatives have weight1, all labels and observations are retained. Rank
references use **training positives only**, matching Task2.24/31. This deliberately
differs from the pilots' full 70,069-positive reference: the new held-out EL
validation rows must not enter training ranks. Coefficient, tie formula and
underlying Teacher remain unchanged. Consequently this is a matched extension
under the established later data protocol, not an exact reproduction of the
original pilot population.

Each fit starts from the same seed-specific authentic random initialization,
trains exactly EL10 and then native IM20. Epoch10/20 are used unconditionally;
no early stopping, epoch search or IM-based selection. Native persistent AdamW
defaults, lr5e-5, batch request16, positive-anchor +16 negative sampler, CUDAFP32,
deterministic algorithms, no AMP/TF32, no scheduler. Loss is the **batch-row mean**
of weighted BCE, never normalized by sample-weight sum. IM loss is unweighted
and updates only the four native condenser transfer parameters, with fresh
optimizer and reset seed. Every native ordered batch, skip mask, optimizer
setting and RNG boundary is checked against the same-seed A. New A epoch
receipts become the paired schedule; seed42 uses authenticated historical ones.

EL validation AP/AUROC/BCE are diagnostics, never selection criteria. IM fitting
BCE is recorded; final full-IM fitting has no independent validation curve.
The original A duration had previous EL/IM development selection exposure;
its reuse does not make the present comparison independent or duration-optimal.

## Outputs and boundaries

Save all epoch training/validation records, initialization and sampler evidence,
complete EL10 and IM20 checkpoints, strict reload probes, environment/elapsed
resources and file identities in a new run. A42 is not retrained. Maximum four
workers are an execution resource setting; no scientific condition differs
between arms. A failed fit is recorded and not silently restarted. Infrastructure
recovery requires preserving evidence and identical conditions.

Freeze native positive-class sigmoid scores (and logits) from both checkpoint
stages on the original ordered IMPROVE7788 and Neo267 identity manifests. Preserve
biological duplicates and dependence metadata; use original HLA preprocessing.
External scoring uses dummy target0 solely to satisfy the input schema: the
target is never used in a model forward or optimization. **No external outcome
reader, IM AP/AUROC calculation or bootstrap is invoked**. Mac L2 receives those
scores for separately authorized evaluation. No selection by IM results.

Before training, authenticate sources/Teacher/checkpoints/runtime, test weighting
and row alignment, freeze seed-specific initial states, and commit protocol,
implementation and tests. Only code, tests and compact documentation enter Git.
Private identities, labels, scores, checkpoints and logs stay in runs. The
internal audit export contains identities/scores and is not for public release;
large checkpoints and full training data are not exported. Historical runs are
read-only. No merge, push, Release, upload or automatic Mac transfer.
