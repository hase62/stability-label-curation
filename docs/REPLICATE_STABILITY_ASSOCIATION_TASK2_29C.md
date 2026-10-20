# Task 2.29C — Original Teacher stability and SHERPA biological repeat detection

Completed on Z790/WSL2, 2026-10-20. Branch:
`task/2.29c-stability-replicate-association`, based directly on approved Task
2.29A commit `795d67ac4689127e48a2f99d42869decdfcf6fd7`.

**A small positive descriptive association was observed:** primary Spearman
rho **0.16170853503670887**, with the prespecified one-sided permutation tail
fraction **0.00009999000099990002** (1/10,001; zero of 10,000 permutations
equaled or exceeded the observed statistic). The biological confidence interval
is **undefined** because there is one independent biological dependence
component. No peptide-independent interval was substituted. Excluding exact
and one-substitution Teacher fitting neighbors gave rho
**0.15801680731393347**, N=661. Quantitative index precursor abundance is
unavailable, so robustness to abundance adjustment cannot be established.

This supports further external validation of the hypothesis. It does not
establish a causal stability effect, biological-population significance, false
EL labels, or readiness to change BigMHC training or EL confidence weights.

## Frozen specification and chronology

The [Task 2.29 protocol](REPLICATE_STABILITY_ASSOCIATION_TASK2_29_PROTOCOL.md) and
[Task 2.29A amendment](REPLICATE_STABILITY_ASSOCIATION_TASK2_29A_AMENDMENT.md)
were authoritative. Their historical blocked status is preserved; the recovered
original Teacher resolves the model-availability gate for this authorized task.

Implementation, tests, machine-readable configuration and the
[execution specification](REPLICATE_STABILITY_TASK2_29C_EXECUTION_SPEC.md)
were committed **before inference** in
`aefe9f919924fc27e1be77ab9d57ca69194f0870`. This fixed the following details:

- Original ordered 671 index peptides; continuous deployed clipped log1p
  predicted half-life; average ranks for tied predictions and outcomes.
- Y = direct detection count in two reserved biological runs divided by two.
  The rank coefficient is identical for Y and count 0/1/2, which was checked.
- Primary statistic: the protocol's Spearman HLA/context summary. With one
  HLA/context it is the single cohort coefficient.
- Uncertainty: whole biological-sample/peptide connected components. With one
  component, the protocol explicitly yields no interval and zero bootstrap
  draws. Seed 228229 and 10,000 draws remain recorded as conditional settings;
  they were not executed. The user's fallback suggestion of a peptide bootstrap
  does not replace the already specified method.
- Negative control: 10,000 within-HLA score permutations with local
  `Random(228230)`, one-sided greater-or-equal comparison and the plus-one
  correction. Doubled average ranks make the comparison exact with ties.
- One sensitivity: remove peptides at minimum Hamming distance 0 or 1 from
  **any actual Teacher fitting peptide across HLA**. This conservatively
  implements the original fitting-exposure exclusion; no alternate threshold,
  A*02-only subset or validation-exclusion analysis was tried.
- Descriptive strata: quartiles of `(average rank - 0.5)/N`, with fixed upper
  bounds .25/.50/.75/1. Entire ties stay together. No stratum significance tests.
- No index precursor intensity is available; do not substitute fragment-ion
  intensity, fit an all-missing adjustment, or introduce post-result covariates.

The pre-prediction freeze was written at
`2026-10-20T14:21:50.214657+00:00`, after overlap assessment and before scoring.
All 671 predictions were saved by `2026-10-20T14:22:24.933419+00:00`; association
analysis finished at `2026-10-20T14:22:40.872493+00:00`. No results were used to
revise parameters, eligibility, index, method, strata or sensitivity identities.

## Source cohort and direct detection endpoint

Source: SHERPA [PXD023064](https://www.ebi.ac.uk/pride/archive/projects/PXD023064),
*Precision Neoantigen Discovery Using Large-scale Immunopeptidomes and Composite
Modeling of MHC Peptide Presentation*,
[DOI 10.1016/j.mcpro.2021.100111](https://doi.org/10.1016/j.mcpro.2021.100111).
The [Task 2.29A curation report](MONOALLELIC_REPLICATE_FEASIBILITY_TASK2_29A.md)
and its authenticated processed artifacts were reused without reconstruction,
new source search, RAW downloads or changed exclusions.

This is source-defined experimentally monoallelic K562 HLA-A*02:01, supported
by single-HLA/B2M transfection, W6/32 flow confirmation and background filtering.
W6/32 is pan-HLA-I; restriction was not independently measured for each ligand.
Biological replicate labels are deposited community SDRF annotations supported
by distinct author-mapped samples and the reported triplicate design. No
independent culture log or quantitative per-run residual-HLA assay is available.

| Role | Frozen sample | CID direct-identification run |
| --- | --- | --- |
| Index | `K562-HLA-A02:01-37882` | `MSB37882A.raw` |
| Follow-up 1 | `K562-HLA-A02:01-33405` | `MSB33405A.raw` |
| Follow-up 2 | `K562-HLA-A02:01-35123` | `MSB35123A.raw` |

All observations are the frozen unmodified canonical 9-mers. Original accepted
peptide–HLA membership, scan/fragment evidence and PSM QC remain unchanged.
The 1,536-peptide union is descriptive: 776 detected in one of the three runs,
395 in two and 365 in all three. **Only the 671 index-run peptides are scored
and used for primary association.** Other biological pairs, nine CID technical
pairs, modified species and CID/EThcD method comparisons are not added.

Primary reserved follow-up counts are:

| Count | Peptides |
| --- | ---: |
| 0 | 99 |
| 1 | 207 |
| 2 | 365 |
| Total | 671 |

Follow-up binary patterns `(run 1, run 2)` are 00: **99**, 01: **122**,
10: **85**, 11: **365**. Thus 450/671 (0.6706408345752608) are detected
in follow-up 1 and 487/671 (0.7257824143070045) in follow-up 2. These are
index-conditioned counts, distinct from all-run source yields 920 and 1,070.
The overall mean reserved detection frequency is 0.6982116244411326.

Original source identity is preserved through the Task 2.29A manifest SHA256,
original ordered row number, peptide, exact HLA, group and original PSM IDs.
Every prediction and joined observation retains a stable source-identity hash.
All source, peptide, HLA, row, outcome and prediction links passed validation.

## Original Teacher and preflight

Bundle: resolved project data / `teacher-v0-recovered/`. Checkpoint:
`checkpoints/teacher_model.json`, original SHA256
`a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99`.
This is the historical Teacher, **not SPEARMINT, a new fit or an external model**.

The handoff verifier passed again on Z790: 48 files, original registry/partition
identity, all fitting/validation identities, original feature contract, three
dummy predictions, four unsupported-input cases and exact reload consistency.
All bundled inference modules matched their repository counterparts byte for
byte. The unchanged `stability_teacher.load_model()` and
`Teacher.predict_stability()` implementations were used directly.

The model is per-exact-HLA positional one-hot Ridge: 9 residues × 20 canonical
amino acids, alpha 10, original coefficients and intercept. `HLA-A*02:01` is
supported; there is no nearest-allele inference or HLA-sequence substitution.
The source is the authenticated DTU NetMHCstabpan-2016 `Stability.txt` kinetic
half-life measurements in hours, preserved in the canonical registry. Targets
are log1p reported hours; source-reported zeros have unresolved underlying
mechanisms and were not relabeled. Thermal melting measurements and synthetic
negatives are not Teacher targets.

Training/validation comprise **21,625 / 5,406 observations** globally and
**830 / 193 for A*02:01**. Original global exact/one-substitution components
separate fitting from validation. Saved A*02:01 kinetic validation Spearman is
0.5835703799853088 and hours MAE 5.0702606033228586, copied as historical model
limitations rather than reevaluated or used for selection. This pilot validation
does not establish external half-life calibration or study/donor independence.

Every SHERPA input was accepted before scoring. Each of the **671 distinct
peptide–HLA pairs was predicted exactly once**, then all outputs were saved
before association. All outputs are finite and nonnegative, with original
`expm1(max(0, linear_log_prediction))` inversion. There are 13 clipped zero
predictions and 659 distinct deployed values; floor ties were preserved with
average ranks. A model-floor zero is not a measured zero or instantaneous
dissociation. No additional real-data inference was used for verification.

## Teacher fitting and validation exposure

Overlap was assessed before predictions/associations, against the authenticated
identity CSVs. Normalization/identity problems: **0**. All 671 primary identities
remain included regardless of exposure.

| Exact overlap type | Training | Validation |
| --- | ---: | ---: |
| Peptide–HLA | 7 | 4 |
| Peptide alone, any HLA | 7 | 4 |

The 21,625 fitting observations contain 4,548 distinct peptides globally;
the A*02:01 fitting subset contains 830 distinct peptides. Exact minimum
unweighted 9-mer Hamming distances and nearest-sequence witnesses were saved:

| Fitting reference | Distance 0 | Distance 1 | Distance 2 | Distance ≥3 |
| --- | ---: | ---: | ---: | ---: |
| Relevant A*02:01 fitting peptides | 7 | 2 | 2 | 660 |
| All-HLA fitting peptide union | 7 | 3 | 3 | 658 |

The global fitting-exposure sensitivity therefore excludes ten peptides,
retaining **661**. Its counts 0/1/2 are **99 / 205 / 357**. All four exact
validation overlaps remain, as specified: validation exposure is reported
separately and does not become an additional post-result exclusion. The one
extra global one-substitution neighbor is cross-HLA exposure, not direct
fitting of the A*02:01 coefficient model.

Kinetic-stability labels differ from MS repeat-detection labels. Sequence overlap
does not itself mean the Teacher was trained on MS outcomes. It does limit a
claim of wholly novel kinetic-sequence generalization; absence of exact/one-step
overlap cannot eliminate broader motif, protein-family or detectability dependence.

## Prediction summaries and primary statistical results

Predicted half-life hours across all 671 peptides:

| Summary | Hours |
| --- | ---: |
| Minimum | 0.0 |
| 25th percentile | 3.6684047924460135 |
| Median | 6.070151318570333 |
| 75th percentile | 9.223448904770109 |
| Maximum | 30.36943255419544 |
| Mean | 6.865910957742954 |

The mean deployed log1p value is 1.8885813481840796, median
1.9558818825889661. Association uses the continuous original log-space output,
not an optimized half-life cutoff.

| Analysis | N | Spearman rho | 95% biological interval | One-sided descriptive permutation tail |
| --- | ---: | ---: | --- | ---: |
| **Primary fixed index cohort** | **671** | **0.16170853503670887** | **Undefined: one component** | **0.00009999000099990002** |
| Prespecified global fitting-neighbor exclusion | 661 | 0.15801680731393347 | Undefined: one component | 0.00009999000099990002 |

For each frozen cohort, 10,000 usable negative-control draws were generated;
zero were undefined and zero equaled/exceeded its observed statistic. The
reported tail is **1/10,001**, the plus-one Monte Carlo reporting floor. It is
not zero, a precisely resolved smaller tail, or a biological-population p-value.
The control assumes score exchangeability between peptides within HLA. Shared
sequence families, sample effects and abundance/detectability can violate that
assumption. It does not account for unmeasured covariates or create biological
replication.

All primary observations share the same biological group and three related
sample units: component size 671 (sensitivity size 661), independent units **1**.
Under the locked protocol, neither cohort receives a bootstrap interval.
Consequently there is **no interval supporting a population-level directional
conclusion**, despite a positive point estimate and small descriptive null tail.

## Prespecified secondary descriptions and missing adjustment

Half-life distributions by follow-up count, in hours:

| Count | N | Q25 | Median | Q75 |
| --- | ---: | ---: | ---: | ---: |
| 0 | 99 | 2.8381272611631996 | 4.624505352009047 | 7.231454471542645 |
| 1 | 207 | 3.4090759499206325 | 5.802557014886084 | 8.374857278799805 |
| 2 | 365 | 4.198452076875571 | 6.680222129909764 | 9.643531111610125 |

Prespecified stability-rank quartiles retain ties and all observations:

| Quartile, low to high | N | Count 0 / 1 / 2 | Mean Y | Follow-up 1 rate | Follow-up 2 rate |
| --- | ---: | --- | ---: | ---: | ---: |
| Q1 | 168 | 38 / 62 / 68 | 0.5892857142857143 | 0.4880952380952381 | 0.6904761904761905 |
| Q2 | 168 | 24 / 52 / 92 | 0.7023809523809523 | 0.6726190476190477 | 0.7321428571428571 |
| Q3 | 167 | 18 / 50 / 99 | 0.7425149700598802 | 0.7365269461077845 | 0.7485029940119761 |
| Q4 | 168 | 19 / 43 / 106 | 0.7589285714285714 | 0.7857142857142857 | 0.7321428571428571 |

The increase is stronger in follow-up 1; follow-up 2 is relatively flat and not
monotonic in the upper quartiles. We do not present this as consistent biological
replication of a gradient across both follow-ups. Medians for binary patterns
00/01/10/11 are 4.624505352009047 / 4.7990955640708695 /
7.049541504238872 / 6.680222129909764 hours. No additional per-run association
tests or favorable-run selection were performed.

**Intensity-adjusted analysis: unavailable.** All **671/671** quantitative
index precursor-intensity values are missing from the authentic prioritized
source outputs. The existing values describe fragment-ion intensity, not
precursor peptide abundance. Per-PSM individual q values and matched per-run
protein abundance are likewise unavailable. No covariate values were invented,
no abundance-adjusted model was fitted, and no alternative covariates were
introduced after results. The observed association cannot be described as robust
to intensity adjustment. Source protein/RT/charge/fragment information remains
traceable in the frozen curation, without a new adjusted endpoint.

## Interpretation and scientific decision

1. **Direction and magnitude:** a small positive rank association is observed
   within this fixed A*02:01 index cohort, compatible with the biological
   hypothesis. It is an association with two-run MS identification, not a
   measured effect on surface half-life.
2. **Uncertainty:** the prescribed biological interval is undefined. The
   negative control is informative only under its peptide exchangeability
   assumptions and cannot establish biological-population significance.
3. **Exposure sensitivity:** the small positive effect remains after the fixed
   ten-peptide fitting-neighbor exclusion, so these near fitting sequences do
   not alone explain the point estimate. Validation exposure and broader motif
   similarities remain explicit limitations.
4. **Confounding and run differences:** unmeasured peptide/protein abundance,
   hydrophobicity/ionization, fragmentation, HLA motif/sequence similarity,
   source-protein families, DDA precursor selection, identification stochasticity,
   preparation recovery and run depth may contribute. The different follow-up
   patterns reinforce this concern; no adjustment can rule it out here.
5. **Sampling and scope:** discovery in the fixed index conditions the cohort
   and can induce selection bias. Unobserved cell-surface peptides are absent
   from the study, not synthetic negatives. There is one source study, one
   cell-line/HLA context and only three biological runs; peptides are not 671
   independent biological experiments. Residual HLA background, culture/input
   equality, and community replicate annotation cannot be fully independently
   verified. The frozen unmodified 9-mer subset also limits chemical/length scope.
6. **GO/NO-GO:** **GO for separately authorized external validation** with
   independent biological groups, additional HLA contexts and reliable index
   quantitative abundance. **NO-GO for treating the result as a validated EL
   confidence weight or changing/retraining BigMHC from this study.** It provides
   motivation for further stability-informed confidence research, not proof
   that low-stability EL positives are mislabeled. No follow-up was executed.

Teacher kinetic predictions, MS repeat identification, biological presentation,
thermal melting stability and T-cell immunogenicity remain distinct quantities.
Neither a nondetection nor a low model output proves surface absence or an
incorrect EL label. The reported small effect does not resolve causality.

## Engineering, artifacts and execution evidence

All generated artifacts are outside Git under resolved project runs /
`task-2_29c-stability-replicate-association/`. Model/source data remain in their
existing data/run locations without overwrite. Key files:

- `preflight/handoff_verification.json`, `Teacher_overlap.jsonl`,
  `Teacher_overlap_summary.json`, `analysis_freeze.json`.
- `frozen/primary_cohort.jsonl`, `sensitivity_source_identities.json`,
  `dependence_components.json`, `config.json`.
- `predictions/Teacher_predictions.jsonl`, `inference_started.json`,
  `inference_receipt.json`: all 671 ordered predictions, validity, original
  source identities, clipped log/hour output, average ranks and fixed strata.
- `observations/predictions_and_repeat_detections.jsonl`: joined original
  observations, separate follow-up indicators, count/frequency, exposure and
  explicit missing covariates.
- `statistics/association_results.json`, `descriptive_results.json`, and the
  two complete saved 10,000-draw permutation distributions.
- `figures/stability_repeat_detection.png` and `.pdf`: outcome distributions,
  all four rank strata, separate follow-ups and the primary null control.
  `figure_metadata.json` pins input results and exports.
- `logs/`: original stage stdout, `/usr/bin/time -v` resource records, focused
  tests and isolated plotting package versions. Completion records preserve
  interpretation, final alignment checks and output hashes.

Important SHA256 identities:

| Artifact | SHA256 |
| --- | --- |
| Task 2.29A index manifest | `fc3f18266eef091b13903db1aca44715fcfe3199bad9fdcbfaceaa96fae6d50d` |
| Pre-prediction analysis freeze | `e3bfc7d4bfd3604c7b9fa0b142bcdfa1a535253a5cc3167b7b4281734a826e99` |
| Ordered Teacher predictions | `c752dea2260a6892688c526186637aa28733c8e6714538998eca353eaef96def` |
| Association results | `0d6de8813d9f5e1353ce0bcd45e782bd222ee6d4d1b89ab59814b2b0dc2d6d92` |
| Descriptive results | `6f090766063a22e100c2d653ce59f2adb985b2425e86f55f28999d74d5d16ef5` |

**Tests/preflight:** 19 focused tests passed: 12 association/model/cohort tests
and seven curation tests. These cover original synthetic smoke consistency,
frozen cohort identity, follow-up counts, hand-calculated tied Spearman,
permutation ties/plus-one/determinism, exact Hamming search against brute force,
one-component uncertainty, shared-peptide dependence, missing covariates and
stable finite serialization. Execution additionally checked all 671
source–peptide–HLA–prediction associations and original outcome alignments.
All 42 original Task 2.29A pinned files passed authentication, and all
pre-prediction implementation/input hashes remained unchanged afterward.

Actual `/usr/bin/time -v` resource evidence:

| Phase | Wall seconds | User / system CPU seconds | Peak RSS KiB |
| --- | ---: | --- | ---: |
| Preparation, handoff and overlap | 2.57 | 2.37 / 0.19 | 145,852 |
| All 671 Teacher predictions | 0.08 | 0.07 / 0.00 | 32,844 |
| Primary and fixed sensitivity analysis | 1.69 | 1.67 / 0.00 | 32,448 |
| Saved-result figures | 1.63 | 4.81 / 0.09 | 110,068 |

The four phase wall times sum to 5.97 seconds, excluding implementation, tests
and plotting-environment setup. No phase swapped. CPU execution used Python
3.13.5 on Linux `6.18.33.2-microsoft-standard-WSL2`, x86_64. Teacher/statistical
computation uses the standard library and no NumPy/SciPy/sklearn/Torch inference
dependency. Figure export alone uses Matplotlib 3.10.7 in a dedicated resolved
data-root environment; its complete package freeze is saved. No GPU was used.

Reproducible stage entry point:
`PYTHONPATH=src python -B -m stability_label_curation.replicate_stability_association <prepare|infer|analyze|figures>`.
These are the executed stages, not permission to repeat the frozen analysis.
Exclusive sentinels and outputs prevent accidental repeated preparation,
real-data inference or association analysis.

No Teacher or BigMHC training, tuning, calibration, model modification, A/S/P
reevaluation, RAW download, cohort revision, favorable subset selection or
historical-result revision occurred. The prespecified Task 2.29C study is complete.
