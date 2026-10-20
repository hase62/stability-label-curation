# Task 2.29A — Conditional monoallelic source amendment

Prepared 2026-10-20 under explicit Task 2.29A authorization, before any Teacher
prediction or stability–detection association on this source. This narrowly
amends source eligibility and unit identities in
[the conditional Task 2.29 protocol](REPLICATE_STABILITY_ASSOCIATION_TASK2_29_PROTOCOL.md).
It authorizes no prediction or association by itself. The Task 2.28 report and
its multi-HLA blocked status remain historical and unchanged.

## Newly satisfied source gate

The authenticated PXD023064 SHERPA processed data provide source-defined
monoallelic K562 HLA-I assignments and original run/scan direct-identification
evidence. The complete acquisition, exact source hashes, original author/SDRF
mapping, confidence limitations, separate chemical states and counts are in
[the Task 2.29A report](MONOALLELIC_REPLICATE_FEASIBILITY_TASK2_29A.md).
Source attribution comes from stable single-HLA/B2M transfection, W6/32 flow
confirmation and mock-background filtering, not a per-peptide restricting-allele
validation or binding/Teacher prediction. Residual/background restriction and
unrecorded culture/preparation batch remain limitations.

The primary candidate is **only the three comparable CID biological units for
HLA-A*02:01**. Their biological replicate labels are deposited community SDRF
annotations, corroborated by three author-mapped sample identities and the
paper's biological-triplicate design; no independent culture log is available.
Preserve that provenance qualification in any future conclusion.

Use these frozen units in exactly this order:

1. Index: `K562-HLA-A02:01-37882`, `MSB37882A.raw`.
2. Reserved biological repeat: `K562-HLA-A02:01-33405`, `MSB33405A.raw`.
3. Reserved biological repeat: `K562-HLA-A02:01-35123`, `MSB35123A.raw`.

One first CID injection per biological sample is used. The latter samples' B
injections cannot augment the primary endpoint or be substituted for A based
on richness or scores. The 1,536-peptide direct union remains descriptive.
The **671 peptides directly detected in the fixed index** are the future
primary cohort; reserved detection counts are 99 zero, 207 one, 365 two.
Y is the number of direct detections in those two reserved biological units
divided by two, retaining zero-repeat detections.

Every positive detection requires released accepted peptide–HLA membership and
a direct PSM passing the original supplementary-code fragment/chimera filters.
There are no transfer-only successes. Preserve the unmodified canonical 9-mer
requirement and separate modified/fixed-CAM molecular species. Do not assign
scores to modified-only observations. A missing run is not a nondetection;
all three selected runs have deposited direct-identification evidence, although
detailed run-level acquisition QC and input quantities remain unavailable.
Peptides not discovered in the index do not enter the primary association.

Frozen derived root: resolved project runs /
`task-2_29a-monoallelic-replicate-rescue/`. Require the complete
`reports/dataset_freeze.json` inventory before prediction, SHA256
`06567f225b07e1642ddd46e2fd349863b48b4cdc0dec5bd8d6fbb62d50985f46`.
Specific identities:

- `manifests/replicate_groups.json` SHA256
  `09979263de3e52f09506f98204045956a5c93da2b5cfdd7b626fbc4255d82d3d`.
- `manifests/primary_biological_union.jsonl` SHA256
  `e3a7b12053de9d407d273f77780199ef8f3a25d880bd307b5239a031e5c03aa4`.
- `manifests/future_primary_index_cohort.jsonl` SHA256
  `fc3f18266eef091b13903db1aca44715fcfe3199bad9fdcbfaceaa96fae6d50d`.

The A*31:01/B*35:01 biological pairs and nine technical CID pairs do not satisfy
the existing three-unit primary gate. Retain their descriptive matrices; do
not pool them into the primary correlation or promote them after scores are
known. The eight CID/EThcD pairs are nonexchangeable method comparisons and
have no replicate-frequency denominator. No new association conditions are
authorized for these groups by this amendment.

## Remaining model gate and unchanged analysis

HLA-A*02:01 is among the exact 67 trained models documented by the authenticated
Task 2.13 `supported_HLA` metadata. Before any future prediction, restore and
verify **the original** Teacher SHA256
`a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99`,
its original validation/support and fitting partition. Expected fitting-partition
SHA256 is `ec065f1d42b6c36149e42f7c7110cb956000bc229e9f14ea74d10107604bc1b5`;
the original canonical kinetic registry SHA256 is
`471fa7989e7665f722998fc1314d63ef87e8d4768846bec98638e6357de87eee`.
These are currently absent. The approved registry has no exact-byte Teacher
restore artifact; its R2 reconstruction requires prohibited retraining.
**Association execution therefore remains NO-GO.** No substitute model,
reconstruction by refitting, or approximate fitting population is acceptable.

The original continuous within-HLA Teacher average ranks, Spearman primary
summary, clipping/tie handling, sample/peptide connected components, 10,000-draw
component bootstrap with seed 228229 and conditional negative-control
permutation with seed 228230 remain unchanged. No resampling has been run.
All 671 observations share the same independent biological group and related
sample units; **there is one dependence component**. Consequently the prescribed
component-bootstrap interval is undefined. Do not replace it with a
peptide-independent interval. The equal-HLA/context summary reduces to one
A*02:01 group and cannot estimate effects across HLA or independent cell contexts.
Any future permutation tail fraction remains descriptive and depends on
exchangeability despite abundance/sequence confounding.

There is no established quantitative index-run precursor intensity in the
prioritized source files. Fragment-ion intensity is not that covariate, so the
original abundance-adjusted sensitivity is unavailable unless authentic matched
quantitation is separately authorized and frozen before scores. Source-protein,
sequence, DDA and confidence confounding must remain explicit.

Preserve descriptive BigMHC fitting/selection/prior-benchmark exposure flags
without exclusion or conflation with Teacher exposure. Once the authentic
Teacher fitting identities are restored, the original exact/one-substitution
exposure flags and fixed sensitivity apply. Do not adapt eligibility to the
result. The endpoint is MS identification conditional on index detection,
not cell-surface absence, a false EL label, thermal stability or immunogenicity.
Further execution requires explicit researcher authorization after the model
gate is satisfied. Task 2.29A ends with curation and feasibility only.
