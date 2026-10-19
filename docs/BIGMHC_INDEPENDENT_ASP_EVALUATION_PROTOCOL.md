# Locked independent A/S/P evaluation protocol — Task 2.24

Version 1, fixed before S/P scientific execution. This document prepares a future
single comparison; Task 2.24 authorizes no benchmark access or evaluation.
The cohort, outcomes, predictions and scores remain sealed. Eligibility counts
and HLA distributions are unknown until separately authorized identity review.
No population size or performance is inferred here.

## Models and freeze boundary

A is exactly Task 2.23's EL-10 / IM-20 final fit on all 3,428 original IM
observations. S/P each use the same frozen 1,308,196-row EL training partition,
10 EL epochs and 20 full-IM epochs, with the Task 2.20 414-to-1 auxiliary head
and coefficient 0.1 during EL only. S uses Teacher ranks computed among only
the 63,053 EL training positives; P permutes those ranks within HLA with the
fixed independent stream. No labels change. All auxiliary heads are excluded
from IM inference. No externally pretrained backbone weights are used.

Run storage is resolved by `stability_label_curation.paths`. A is referenced
in `task-2_23-el-multiepoch-baseline/checkpoints/final_all_IM/`; S/P final
complete checkpoints are in
`task-2_24-fully-trained-stability-auxiliary/checkpoints/{S,P}_IM_epoch_20/`.
The latter run's `reports/frozen_models.json` must authenticate all model file
and tensor identities and this document's SHA256 before any benchmark access.
The future evaluation must also retain the repository commit, configuration,
runtime, prediction code and eligibility-manifest hashes. No model choice,
checkpoint choice, calibration, refit, threshold optimization or metric changes
are allowed after freeze. The historical 383-row development cohort and 686-row
internal validation subset cannot select or rank these final-fit models; the
686 rows are part of all three final IM fits.

## Source and observation unit

Use the published BigMHC **neoepitope** immunogenicity evaluation source, initially
human HLA-I 9-mer peptide–HLA assay observations, as identified in the existing
[Task 2.22 protocol](BIGMHC_PEPTIDE_DISJOINT_MULTIEPOCH_PROTOCOL.md),
[publication](https://doi.org/10.1038/s42256-023-00694-6) and
[publisher repository](https://github.com/KarchinLab/bigmhc).
Do not substitute the infectious-disease cohort or pool different sources to
increase the sample. Source payload identity, release, source member and assay
definitions must be pinned in a separately authorized, label-blind identity
receipt before outcome access. If the source cannot be resolved unambiguously,
stop before opening outcomes. No source payload is read in Task 2.24.

An observation is one documented experimental peptide–HLA assay. Repeated
copies of the same source assay identifier count once, selected by the lexical
source locator; retain distinct documented assays and report repeated peptide
and peptide–HLA counts. Do not collapse assays by model score. Unresolvable
assay identity or provenance is quarantined before scoring. The later outcome
quality check uses only the source's documented binary T-cell-response label;
no assay absence, synthetic negative or stability prediction defines a negative.
Missing/ambiguous labels and contradictory copies of the same assay are
quarantined under this fixed rule, reported separately, and identically for A/S/P.
Distinct assays with differing outcomes remain distinct observations.

## Identity-only eligibility, frozen before outcome access

Normalize peptide by trimming surrounding whitespace and uppercasing. Require
exactly nine residues in the canonical 20-amino-acid alphabet; no truncation,
residue substitution or ambiguous sequence repair. Canonicalize human HLA-I
using the existing project resolver, retaining the original string. Require an
unambiguous exact allele supported by the pinned BigMHC pseudosequence mapping.
No nearest-allele imputation or outcome-based HLA restriction is permitted.

Before viewing labels, scores or predictions, join identities to the **complete
eligible EL training partition**, including negatives never sampled by the
positive-anchored sampler, and **all 3,428 original IM training observations**.
Use Task 2.23's frozen EL manifest, partition `train`, 1,308,196 rows and
1,122,528 unique peptides, preserving the 11 exclusions and 145,371 validation
rows outside that inventory. This is the actual A/S/P EL training population.
Exact sequence overlap is global across HLAs and labels. Also report exact
peptide–HLA overlap, original full-EL-view exposure outside the training
partition, Teacher/source exposure where provenance permits, and historical
development exposure separately. These flags cannot silently change eligibility.

The **primary globally EL/IM-unseen population** requires all of:

1. Valid canonical 9-mer and compatible exact peptide–HLA representation.
2. Peptide absent from every EL training sequence, regardless of HLA or label.
3. Peptide absent from every full-IM training sequence, regardless of HLA or label.
4. No shared training source observation, assay, patient/specimen or other
   established source/provenance overlap compromising independent measurement.
   Unknown material provenance is quarantined pending label-blind resolution.

The **secondary IM-novel population** uses the same validity, HLA, provenance
and assay rules and excludes every IM-training peptide, while permitting EL
training exposure. Divide it into EL-exposed and globally unseen subgroups.
IM novelty does not imply complete EL/IM novelty. Exact peptide novelty does
not establish lack of similar peptides or independence of shared HLA biology.

Create an immutable identity eligibility manifest and hash before outcome access.
Report sequential exclusion counts in the order above, all overlapping reason
flags, final eligible observations/unique peptides/unique pairs/assays/patients,
HLA distribution and missing provenance. After the fixed outcome-quality check,
report the identical summaries on evaluable rows, positives, negatives and
prevalence for each cohort. Report excluded or unsupported HLAs and the effects
of the 9-mer, source, ancestry/patient and allele coverage on generalizability.
The primary and secondary cohorts cannot be exchanged or exclusions relaxed
when the primary population is small or lacks either outcome class. For fewer
than 20 observations or fewer than five in either class, mark estimates as
very limited. With either class absent, report counts and no discriminative
comparison; keep the original eligibility rules unchanged.

## One locked comparison and metrics

Run each frozen final IM model once on the same ordered eligible observations
using authentic BigMHC evaluation mode, deterministic CUDA FP32, no auxiliary
head, and the original IM probability output. Retain full FP32 probabilities,
source identities and all eligibility flags. Nonfinite scores or missing model
rows stop the comparison; do not drop rows for only one arm. All model metrics
within each cohort use exactly the same observations and original outcomes.

Primary endpoint: **non-interpolated IM average precision (AP) on the globally
EL/IM-unseen eligible independent population**. Group exactly tied score values
into a single threshold; compute the sum of recall increments times precision
at each threshold. Do not interpolate a precision envelope. Report prevalence
alongside AP so class imbalance is visible.

Secondary endpoints:

- IM AUROC on the primary population, giving half credit to positive/negative
  score ties.
- Precision@10 and Precision@20 on the primary population. Rank descending
  probability; resolve exact ties by canonical peptide, canonical HLA, then
  immutable source assay/row locator, identically defined for every arm. Report
  boundary ties and their size. K larger than the cohort is undefined and is
  never replaced by another K.
- IM-novel population AP and AUROC with the same tie conventions.
- EL-exposed IM-novel subgroup AP and AUROC when at least 20 observations and
  both classes are present; otherwise report counts and mark metrics unavailable.

Report A, S and P and all fixed contrasts **S−A, S−P, P−A** for every evaluable
endpoint. No secondary endpoint can replace an unfavorable primary endpoint.
No outcome-dependent K, HLA subset, score transformation, class rebalance or
threshold is allowed. No PPVn or additional metric is part of the locked
comparison; exploratory additions require a separately labeled future protocol.

## Uncertainty and interpretation

Retain the assay-level point estimates. Use one paired cluster bootstrap with
10,000 draws, independent RNG `Random(24242)`, and the same resampled rows for
all arms. Define clusters before labels as connected components of observations
sharing a canonical peptide or a documented patient/specimen; if patient
identities are unavailable, use shared peptide and state that residual patient
dependence is unmeasured. Sample the fixed number of clusters with replacement,
including every row in each drawn cluster with multiplicity. Recompute all
defined endpoints and paired contrasts in each draw. Report percentile 95%
intervals using sorted empirical 2.5%/97.5% quantiles with linear interpolation
at index `(n−1)q`; report undefined-draw counts and use only jointly defined
paired draws. Flag fewer than 1,000 usable draws or fewer than 20 independent
clusters as unreliable. No formal multiplicity-adjusted superiority claim is
planned; secondary contrasts are descriptive. Report tie frequencies and class
balance so discreteness and sparse positives are visible.

Task 2.21's one-epoch result showed no convincing stability-specific benefit;
Task 2.23 improved developmental performance with longer training. The frozen
comparison asks whether stability auxiliary supervision changes generalization
under that stronger training regime. Teacher-predicted kinetic stability is
not verified EL-label correctness or actual EL repeat-detection probability.
Measured kinetic half-life and thermal melting temperature remain separate.
One seed, one permutation, a limited independent cohort, Teacher error and
previously adaptive developmental work constrain causal and general claims.
Even a positive primary result needs uncertainty analysis and external
replication. The future evaluation requires separate authorization after all
three model identities and this complete protocol have been frozen.
