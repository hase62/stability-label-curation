# Task 2.41-B: frozen low-stability hard-filter experiment

This protocol is fixed before new training or IMPROVE comparisons. Base: Task 2.40
`7ccf81de8ccb6bd1340c34f17b320ce4e0dbee06`. No historical artifact is modified.
Machine: Z790 WSL2 / RTX 4090. The executable configuration is
`configs/low_stability_hard_filter_task241b.json`.

## Scientific population and intervention

Reuse the actual Task 2.23 EL partition (1,308,196 rows, 63,053 positive,
1,245,143 negative) and fixed validation (145,371 rows, 7,006 positive).
Reuse the authenticated original per-HLA Ridge Teacher score sidecar and the
existing Task 2.31 **unfiltered training-only** exact percentile ledger.
Teacher quantity is predicted kinetic half-life in hours, not measured Tm.
No new Teacher scoring, rank estimation or model fitting is permitted.

Within each HLA's covered original positives, H removes `floor(n/10)` rows,
sorted by exact saved rank and then lexicographic immutable source-row ID.
Missing scores and unsupported HLAs remain. Negative observations remain.
Labels are preserved, including those of excluded rows in the exclusion ledger.
Physical filtered CSVs, not zero weights or sampling masks, are model inputs.
Fail if an entire positive HLA×length stratum disappears.

R1–R5 sample without replacement from the same covered positives, matching
H's exact HLA×length quotas. Strata and populations are lexicographically ordered;
each replicate has its own Python Random stream seeded 20264101–20264105.
The random selector accepts identities and quotas, **not score values**.
Selection, rank/source binding, full row readback and ordered negative-pool
fingerprints are frozen in preflight before any new IM comparison.

## Baseline compatibility and optimization

A is Task 2.23 EL epoch 10, checkpoint file-map SHA256
`d8e3d7d3ac5d08d7f420e00b8032fa875b8b6fec1cd9da6b36d35bca0bec04d1`.
It is never retrained. Authenticate saved Task 2.32 A IMPROVE predictions and
Task 2.23 A validation predictions. Check native GPU forward equality on fixed
first-16-row probes, both logits/probabilities for IM, before reuse.
Compare the reused scientific function ASTs with Task 2.31's approved commit.
The later strict EL loader's metadata repair is reused; no IM transfer overlay.

H and R1–R5 start from the same historical **epoch-0 random initialization**
and RNG state, not from A epoch 10. Same original architecture, EL sampler,
optimizer and input encoder: seed 42; CUDA FP32; TF32/AMP off; four CPU threads;
persistent AdamW lr 5e-5, original defaults, no scheduler; native batch request 16,
one positive anchor plus 16 negatives; original batch-mean unweighted BCE.
Exactly 10 epochs, final epoch used regardless of intermediate validation.
All backbone parameters train as in historical EL training. No auxiliary loss,
stability weighting, relabeling, IM fitting or calibration.

H/R have fewer anchors/updates than A, but identical update counts to each other.
Their negative pool, algorithm and seed match; actual negative draws/order need
not match after physical deletion alters dataframe permutations. We do not
replace the native sampler to force a new negative stream.

Execution policy: six independent processes (one per H/R fit), each with its
original RNG, thread setting and CUDA context. Host/GPU resources permit this;
concurrency is an infrastructure choice, not a model change. Redirect verbose
native logs to external storage. Save every epoch's losses, source/batch hashes,
RNG boundaries and validation metrics. Verify continuous AdamW update counters.
Save final native EL checkpoint, hashes and strict-reload equality. No automatic
scientific retries or changed settings after failure.

## Frozen evaluation

The original EL validation remains peptide-disjoint and identical for all arms.
Report AP, AUROC, macro per-HLA AP, stable-logit BCE, per-HLA AP, and per-class
mean probability/Brier/correct fraction at fixed 0.5. No threshold optimization.
A's duration was selected on this validation; it is developmental evidence.

Only IMPROVE is evaluated: exact Task 2.32 ordered identities (7,788 rows), native
FP32 sigmoid EL outputs, higher is better, no HLA-wise score transformation.
Reuse A only after exact compatibility checks. Generate and hash all six new
score vectors and seal them before associating original IM outcomes.
Preserve repeated observations. No Neoepitope or additional subsets/benchmarks.

Primary endpoint: non-interpolated pooled IM AP, H−A. Key secondary: AP(H) minus
the arithmetic mean of **five separate APs**, not AP of averaged predictions.
Also H−Ri and Ri−A; AUROC with same contrasts; prevalence and descriptive top K;
all-HLA counts and defined AP/AUROC, including unfavorable effects. Undefined
single-class metrics remain null. Exact tied-score groups follow Task 2.32's
WeightedRanking implementation. No checkpoint/threshold/subgroup selection.

Paired uncertainty: 10,000 attempts, seed 262742, Python Random.randrange,
sorted original 38 patient/peptide components. One component multiplicity vector
per attempt applied to all seven score vectors. For H−mean R calculate individual
APs in each draw before averaging. Use 2.5/97.5 percentiles; report invalid draws
without replacing them. These intervals condition on the five fixed random
selections and one training seed; they do not capture all optimization or
random-subset uncertainty. No independent-row primary bootstrap.

Descriptive removal/score diagnostics use all HLA×length strata: removal count,
remaining positive count, EL-validation-positive mean probability shift, and
IM score shift. These do not redefine endpoints or select favorable HLAs.
Recompute aggregate tables from saved scores without model reruns as a final
serialization/alignment check.

## Interpretation and stop rule

IMPROVE has been repeatedly inspected; this is exploratory, not an untouched
confirmatory evaluation. Thirty-eight dependence components are not 7,788
independent biological experiments. Random-filter repeats vary deletion sets,
not training seeds. Reduced positive anchors also reduce total update budget;
H versus R controls this, while H versus A combines these changes.
Constructed EL negatives are not measured nonpresentation. Teacher stability
and MS detection do not establish EL-label falsity or T-cell immunogenicity.

Claim a potential selective-filter benefit only if H exceeds both A and mean R;
uncertainty and HLA heterogeneity must temper any claim. H exceeding R alone
does not show practical benefit over retaining data. No further thresholds,
seeds, variants, fusion or tuning follow this experiment.

Commit implementation/config/tests/protocol before preflight. Commit a compact
preflight-ready receipt before optimizers run. Scientific files are hash-locked;
generated data/models/predictions stay outside Git. Record results in a separate
commit; clean worktree; no merge or push.
