# Task 2.30B execution specification, before study predictions

2026-10-21, Z790 WSL2. The unchanged
[locked protocol](EXTERNAL_REPLICATE_ASSOCIATION_TASK2_30B_PROTOCOL.md) is
controlling. Task 2.30A's 496 ordered primary and 483 fitting-neighbor-excluded
identities remain unchanged. Original Teacher outputs are generated once for
496 peptides, saved, then reused for all analyses. Preparation authenticates
the source freeze, current curation artifacts and original Teacher, and freezes
this implementation/configuration before scoring. Stage claims are exclusive;
a failed or completed inference/analysis cannot be silently repeated.

Primary: average-tie Spearman of deployed clipped log1p hours and binary
follow-up-clone direct detection. Preserve all four technical indicators;
biological Y is the union of the last two. Negative control: 10,000 score
permutations, local Random(228230), one-sided >= with plus-one correction.
Repeat only in the frozen 483 subset, reranking within it. All rows share one
clone pair: biological interval undefined, zero bootstrap draws; conditional
bootstrap settings remain 10,000 / seed 228229. No peptide-independent interval,
nominal OLS p-value, logistic alternative or additional covariate is introduced.

The locked intensity adjustment retains **496 rows**, using centered log2 index
MS1 intensity, centered-zero for missingness and a missing-intensity indicator.
This differs from the latest task's explicit request for a **complete-case**
adjustment. Preserve the locked model and add the expressly requested
complete-case companion on **473 rows**, clearly labeled supplementary. Apply
the same two adjustment versions within the frozen sensitivity subset:
**483 / 460 rows**. These complete-case populations are determined solely by
the preexisting baseline-intensity availability, before study scores/results;
no rows leave the unadjusted primary endpoint.

Each of these four descriptive regression populations uses its own average
stability percentile `(rank-.5)/N` and log2-intensity center. Compare adjusted
stability slope with intercept-plus-stability-only OLS on the **same rows and
rank scale**. This expresses probability difference per full percentile-unit
increase, not a causal risk difference or a fitted Teacher calibration.
OLS uses double reorthogonalized modified Gram-Schmidt; relative column-residual
tolerance 1e-12 marks rank deficiency undefined. Omit only a constant missingness
indicator. No regression standard errors/p-values are estimated. No new
Spearman/permutation analyses are added for complete-case populations.

Describe frozen rank quartiles, no tie splitting, and distributions by binary
outcome, missing-intensity group and nested technical count. No extra hypothesis
tests. Descriptive figures use saved results. No SHERPA reanalysis, pooling,
source acquisition, model learning, cohort adaptation or EL-weighting experiment.
