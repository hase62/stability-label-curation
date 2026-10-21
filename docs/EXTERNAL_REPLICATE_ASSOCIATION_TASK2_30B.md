# Task 2.30B — External stability–MS repeat-detection association

Completed on Z790 WSL2, 2026-10-21. Branch
`task/2.30b-external-replicate-association`, directly based on approved Task
2.30A commit `a72cf49324a77c5a856bc79a685caffe7dd33408`.

**A small positive association was observed in the external JY context:**
Spearman rho **0.09125203893737674** in the frozen 496 peptides. The one-sided
conditional score-permutation tail is **0.0198980101989801**. The biological
confidence interval is **undefined: one independent clone-pair component**.
The positive descriptive stability slope persists after baseline MS1 intensity
adjustment and fitting-neighbor exclusion. This is directional support for the
SHERPA hypothesis, with limited effect size and biological replication; it is
not proof of a causal stability effect or population-level significance.

**Recommendation: GO for a separately approved, tightly controlled exploratory
EL-positive stability-weighting experiment; NO-GO for adopting such weights as
validated label corrections or changing a production training pipeline.** The
basis is consistent positive point estimates in two experimental contexts,
including this source's intensity-adjusted analysis. Only one HLA, one clone
pair here, nonmonotonic quartile rates and residual confounding prevent a
stronger conclusion. No weighting experiment is started in this task.

## Frozen protocol and chronology

The [locked Task 2.30B protocol](EXTERNAL_REPLICATE_ASSOCIATION_TASK2_30B_PROTOCOL.md)
was followed without changing it. Implementation, nine focused tests, machine
configuration and the [execution specification](EXTERNAL_REPLICATE_TASK2_30B_EXECUTION_SPEC.md)
were committed **before study inference** in
`c764a8f5a7d074fbf1f1b6a42b2b480795edb4ea`.

The locked protocol specifies missing-indicator intensity adjustment on all
496 observations, whereas the latest task also explicitly requests complete-case
adjustment. Both were specified before predictions: the locked 496-row model
remains the principal secondary adjustment; the requested 473-row complete-case
model is a labeled companion. The identical distinction applies to sensitivity
populations of 483 and 460. No new covariate or alternative primary endpoint
was introduced. Each regression population uses its own average percentile ranks
and available-value log2-intensity center. Complete-case companions receive no
additional Spearman/permutation tests.

Pre-prediction freeze: **2026-10-21T07:21:23.762733+00:00**. All 496 predictions
were saved by **07:21:49.728661+00:00**. Association analysis completed at
**07:22:05.001573+00:00**. Figures completed at **07:22:39.497727+00:00**.
Exclusive inference/analysis stage claims prevent overwrites or silent reruns.
No association result influenced source selection, index, rows, missingness
handling, predictor, method, seeds, transformations, strata or sensitivity.

Nine focused tests passed before the implementation commit. An initial attempt
to persist a subsequent test log found that its directory did not exist; the
logging problem was corrected and the nine checks were persisted before
association analysis. Study inference had completed once and was not repeated.
This did not change any scientific input or calculation.

## Source, experimental units and identity alignment

Cobos-Figueroa et al., *Innovative CRISPR/Cas9-Based Strategy for Allele-Specific
HLA Peptidome Analysis Using a Pan-HLA Antibody*, MCP (2026),
[DOI 10.1016/j.mcpro.2026.101578](https://doi.org/10.1016/j.mcpro.2026.101578),
[MassIVE MSV000099922](https://massive.ucsd.edu/ProteoSAFe/dataset.jsp?accession=MSV000099922).
The authenticated [Task 2.30A curation](EXTERNAL_REPLICATE_FEASIBILITY_TASK2_30A.md)
was reused, including processed MaxQuant evidence, author mapping and original
published run-specific accepted sets. No source search, new downloads, RAW
processing or dataset reconstruction was performed. Sixty-six entries in the
current curation source/derived/code inventory were verified against its freeze;
this is a targeted current-input check, not a historical artifact audit.

The system is edited JY cells with classical HLA-B*07:02 and C*07:02 disrupted,
A*02:01 retained, and W6/32 capture. This is experimental-condition restriction,
not independent peptide-level proof of HLA restriction; residual/nonclassical
HLA or nonspecific co-isolation remains possible. Computational affinity or
Teacher scores were not used to assign HLA.

| Biological unit | Role | Nested technical runs |
| --- | --- | --- |
| ΔBC1 | Fixed index clone | `Seq84886_HF`, `Seq84886_3-4_HF` |
| ΔBC2 | Follow-up clone | `Seq84887_HF`, `Seq84887_3-4_HF` |

The index is the direct-identification union of both ΔBC1 measurements.
Follow-up Y is **any direct identification in either ΔBC2 measurement**.
Two technical measurements are not two independent biological follow-ups.
Preparation-versus-repeat-injection details are not independently established.

The full descriptive unmodified 9-mer union has 1,472 peptides; only the frozen
**496 unique index peptide–HLA pairs** were scored. Source manifest SHA256:
`37d5247b7533243d4083142b9ec3dd4645eb8bcc344293908763cfb94bac5cd2`.
All original source identities, exact peptide/HLA, evidence identifiers, four
run states and index-only intensity values are unchanged in joined predictions.

| Analysis population | N | Follow-up detected | Not detected | Baseline intensity available / missing |
| --- | ---: | ---: | ---: | ---: |
| Frozen primary | 496 | 366 | 130 | 473 / 23 |
| Frozen fitting-neighbor exclusion | 483 | 355 | 128 | 460 / 23 |
| Complete-case companion | 473 | 356 | 117 | 473 / 0 |
| Sensitivity complete-case companion | 460 | 345 | 115 | 460 / 0 |

Primary follow-up detection fraction is **0.7379032258064516**. Nested technical
follow-up counts 0/1/2 are **130 / 182 / 184**; binary patterns 00/01/10/11 are
**130 / 42 / 140 / 184**. These technical patterns are descriptive only.
Condition-wide direct 9-mer yields in the four fixed runs are 336 / 311 /
1,119 / 667; clone-level unions are 496 versus 1,342. Unequal depth and clone
biology can therefore affect conditional detection substantially.

Direct features have original spectrum support; match-between-runs was
**False**. Source PSM FDR is **0.05**. Processed Protein FDR is literally `1`,
differing from article .01; source variable modifications include acetylation
omitted from the article's stated list. Those Task 2.30A quality limitations
remain unresolved. Canonical unmodified 9-mer acceptance and original
reverse/contaminant exclusions were preserved, with no new PEP/FDR threshold.

## Original Teacher verification and exposure

Original recovered model: project data / `teacher-v0-recovered/`, checkpoint
`checkpoints/teacher_model.json`, SHA256
`a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99`.
It is the original per-exact-HLA positional one-hot Ridge, **not SPEARMINT**:
180 features, fixed alpha 10, predicting log1p reported kinetic half-life hours.
The original DTU NetMHCstabpan-2016 `Stability.txt` kinetic measurements and
fitting/validation partition are authenticated. Source-reported zeros retain
unresolved original semantics. Thermal melting data and synthetic negatives
are not the target. See [original Teacher documentation](STABILITY_TEACHER_V0.md).

The handoff verifier passed again: 48 package files, original fitting/validation
identities and source implementation, exact A*02:01 compatibility, three
original synthetic predictions within 1e-12, unsupported-input checks and
reload consistency. Every bundled source module matched its repository copy.
Global fitting/validation counts are 21,625 / 5,406, including **830 / 193 for
HLA-A*02:01**. No coefficients, loading, encoding or inference code changed.

Each of the 496 study peptide–HLA pairs was predicted **exactly once**, using
`Teacher.predict_stability()`. All 496 are finite, accepted and correctly
aligned; hours equal `expm1(max(0, original linear log prediction))`. There are
**4 floor-clipped zero predictions** and **493 distinct deployed values**.
Average ranks preserve these floor ties. A floor zero is not a measured zero.
Prediction file SHA256:
`98de2de85c7f6d6ca9fbdce89ab3d11212234ac1ad33218b4251353d717a39a2`.

Teacher sequence exposure was confirmed from frozen Task 2.30A manifests before
association; primary membership was retained regardless of exposure.

| Exact overlap | Fitting | Validation |
| --- | ---: | ---: |
| Peptide–HLA | 10 | 1 |
| Peptide-only, any HLA | 10 | 1 |

| Minimum Hamming distance | 0 | 1 | 2 | ≥3 |
| --- | ---: | ---: | ---: | ---: |
| A*02:01 fitting references | 10 | 3 | 3 | 480 |
| All-HLA fitting references | 10 | 3 | 3 | 480 |
| A*02:01 / all-HLA validation references | 1 | 0 | 0 | 495 |

The frozen sensitivity excludes exactly ten fitting matches and three
one-substitution fitting neighbors, retaining 483. No validation exclusion or
alternative distance cutoff was introduced. Normalization/identity problems:
**0**. Kinetic-label exposure is distinct from training on MS detection outcomes;
it limits sequence-novel generalization without automatically constituting
repeat-detection-label leakage.

## Primary result and uncertainty

| Population | N | Average-tie Spearman rho | Biological 95% interval | One-sided conditional permutation tail |
| --- | ---: | ---: | --- | ---: |
| **Primary** | **496** | **0.09125203893737674** | **Undefined** | **0.0198980101989801** |
| Frozen fitting-neighbor exclusion | 483 | 0.09117896713054392 | Undefined | 0.022097790220977902 |

Primary: 198/10,000 permutations equaled or exceeded the observed statistic;
sensitivity: 220/10,000. Both used local `Random(228230)`, with 10,000 usable
and zero undefined draws, and plus-one tails 199/10,001 and 221/10,001.
Integer doubled average ranks retain exact tied-statistic comparisons.
These are **exchangeability-dependent descriptive negative controls**, not
biological-population significance tests. Peptide sequence families, common
sample effects and detectability can violate the exchangeability assumption.

All observations share the same two biological clones: **one independent
connected component**, size 496 (sensitivity 483). Consequently no biological
bootstrap interval is estimable and **zero bootstrap draws** were executed;
conditional settings 10,000 draws / seed 228229 remain recorded. No peptide-level
bootstrap, nominal regression standard errors or asymptotic p-values were
substituted. There is no biological confidence interval establishing a directional
population effect, despite a positive point estimate and a small conditional tail.

## Baseline MS1 intensity adjustment

The covariate is the frozen mean of available positive per-run sums of direct
unmodified MS1 feature intensities in **index-clone runs only**, in arbitrary
instrument units. Follow-up intensity never enters adjustment. Available-value
log2 intensity is centered at **26.58728105535483** for primary/complete-case
and **26.53977984247876** for sensitivity/its complete-case companion.

Index availability across zero/one/two technical measurements is **23 / 327 /
146**. The 23 missing intensities include **10 detected / 13 not detected**;
available intensities include **356 / 117**, respectively. Missingness is thus
associated descriptively with lower follow-up yield and cannot be assumed
unconditionally random. No missing value was treated as zero abundance or
used to remove an observation from the primary endpoint.

OLS uses binary Y, intercept, cohort percentile rank `(average rank-.5)/N`,
centered log2 index intensity, and a missingness indicator where nonconstant.
Missing values receive centered zero plus the indicator. The complete-case
companions omit the constant indicator, using the exact predeclared 473/460
identities. Each unadjusted comparison below uses the same rows and rank scale
as its adjusted counterpart. No nominal regression p-value or interval is given.

| Population / adjustment handling | N | Rank-only stability slope | Intensity-adjusted stability slope | Log2 intensity slope | Missingness coefficient |
| --- | ---: | ---: | ---: | ---: | ---: |
| Locked primary, missing indicator | 496 | 0.13901598201918353 | **0.13301482653068544** | 0.033055696159993944 | -0.32073949734791585 |
| Frozen sensitivity, missing indicator | 483 | 0.13939858593924473 | **0.13326207942512977** | 0.031189066362117594 | -0.318026223413214 |
| Requested complete-case companion | 473 | 0.1198241400257433 | **0.10960719206399677** | 0.03320919325436976 | Omitted: constant |
| Sensitivity complete-case companion | 460 | 0.11968873015266375 | **0.10935669535679647** | 0.03136725447317045 | Omitted: constant |

A full percentile-unit increase has a descriptive adjusted probability slope
of 0.1330 in the locked model; a 0.5-unit rank difference corresponds to about
**6.65 percentage points**, holding the recorded covariates fixed. The
complete-case counterpart is about **5.48 percentage points** per 0.5-unit
rank difference. These are linear-probability summaries, not odds ratios,
measured half-life effects, causal risk differences or calibrated predictions.

Adjustment slightly attenuates the positive coefficient without reversing it;
the same is true after fitting-neighbor exclusion. This supports persistence
conditional on **this measured baseline covariate**, not freedom from abundance
confounding. MS1 measurement error, unnormalized run response, missingness,
protein expression and index-conditioning remain. The complete-case result
cannot resolve potentially nonrandom missingness. All four designs have full
rank; normal-equation residual checks are below 1e-10. No alternate covariate
model was tried after observing results.

## Stability summaries and fixed descriptive strata

| Predicted half-life summary | Hours |
| --- | ---: |
| Minimum | 0.0 |
| 25th percentile | 5.262380959964621 |
| Median | 8.137720830816667 |
| 75th percentile | 11.586281500721263 |
| Maximum | 38.68783703314506 |
| Mean | 8.914786336939759 |

Deployed log1p mean / median are 2.1431178635248447 / 2.2124064048399483.
By follow-up Y=0 / Y=1, hours medians are **7.596257948723296 /
8.228460743312684**; means **8.261909019576914 / 9.146682651850059**.
Distributions overlap substantially.

| Fixed stability-rank quartile, low to high | Primary detected / N | Primary fraction | Sensitivity detected / N | Sensitivity fraction |
| --- | ---: | ---: | ---: | ---: |
| 1 | 80 / 124 | 0.6451612903225806 | 77 / 121 | 0.6363636363636364 |
| 2 | 99 / 124 | 0.7983870967741935 | 97 / 121 | 0.8016528925619835 |
| 3 | 97 / 124 | 0.782258064516129 | 94 / 120 | 0.7833333333333333 |
| 4 | 90 / 124 | 0.7258064516129032 | 87 / 121 | 0.71900826446281 |

No ties were split and no strata tests were performed. The lowest quartile has
lower detection, but detection **does not rise monotonically across quartiles**;
the highest quartile does not have the greatest detection rate. This limits a
simple dose-response interpretation and does not justify selecting a cutoff.
The saved PNG/PDF figure shows outcome distributions, all fixed quartiles and
both principal adjustment variants without fabricated confidence bars.

## Comparison with SHERPA and biological interpretation

The reported Task 2.29C SHERPA discovery used transfected K562 HLA-A*02:01,
671 index peptides and count 0/1/2 in two reserved biological runs. Its rho was
**0.16170853503670887**, and fitting-neighbor-excluded rho
**0.15801680731393347** (N=661). No quantitative baseline precursor intensity
was available. Those historical results were copied from documentation; no
SHERPA predictions, outcomes or analyses were rerun.

The present JY/CRISPR study uses a binary endpoint in one other clone, with
nested technical consolidation. Its positive direction agrees with SHERPA;
its numerical rho is smaller, but different outcome ties, follow-up design,
source confidence, MS platforms/methods, chemical acceptance and detection
depths prevent treating coefficients or p-values as commensurate effect scales.
Both sensitivities retain the positive direction. This source adds a positive
intensity-adjusted descriptive result unavailable in SHERPA. Neither experiment
has enough independent systems for a biological-population interval. The two
studies were not pooled.

The evidence is compatible with kinetic stability contributing to repeated MS
detection, and supports a carefully bounded next hypothesis test. It does not
isolate that mechanism from abundance, motifs, ionization/fragmentation or
identification stochasticity. Predicted solution-assay half-life is not measured
cell-surface persistence. MS repeat detection is not T-cell immunogenicity.
An undetected peptide may remain on the surface, and a low-stability detected
EL-positive observation is not thereby an incorrect label.

Remaining limits include one HLA and one biological clone pair, shared samples
and peptide families, clone-specific editing/expression, unequal depth, joint
search context and FDR discrepancies, residual HLA restriction, uncertain
technical preparation history, index-discovery conditioning, no matched protein
abundance, incomplete/intensity-scale-limited MS1 adjustment and Teacher source
calibration/sequence exposure. Conditional permutation does not remove these.

## Focused checks, artifacts and execution

**Nine focused tests passed**: three authentic Teacher synthetic smoke outputs;
frozen 496/483 and 473/460 identities; nested technical outcome construction;
index-only intensity and missingness handling; exact source/prediction alignment;
tied binary rank statistic/permutation; known synthetic OLS coefficients and
rank deficiency; one-component interval handling; finite stable serialization
and overwrite refusal. Post-execution integrity checks passed for all 496
source/prediction links and original unchanged model/implementation hashes.
No additional Teacher study calls or association computations were needed.

Run location: resolved project runs /
`task-2_30b-external-replicate-association/`.

- `manifests/`: configuration, original ordered primary rows, exact four
  population identity lists, Teacher exposure witnesses, pre-prediction freeze.
- `predictions/Teacher_primary.jsonl`: all 496 original Teacher outputs, ranks,
  validity, source identities and exact peptide/HLA links.
- `observations/predictions_and_detection.jsonl`: unchanged source observations
  joined to saved predictions, including outcomes and index-only covariates.
- `reports/`: handoff verification, preflight, overlap, inference, full-precision
  association/regression summaries, undefined uncertainty and integrity checks.
- `resampling/`: one-component membership and all 10,000 saved conditional
  permutation statistics for each of the two prespecified cohorts.
- `figures/external_association.png` and `.pdf`: standalone descriptive figure.
- `logs/`: once-only stage claims, focused tests and figure execution log.

CPU only, Python **3.13.5**, Linux **6.18.33.2-microsoft-standard-WSL2**;
statistics/inference use the standard library. Existing isolated plotting
software was reused unchanged (Matplotlib **3.10.7**), with cache under this run.
No dependency installation was needed. Recorded elapsed times: preparation
**1.4565548729733564 s**, study inference **0.02478894597152248 s**, analysis
**1.2160319549730048 s**, figure rendering **1.3095085910172202 s**. Stage
user/system counters and high-water RSS are saved. Main-stage reported RSS is
**682,148 KiB**, plotting **108,256 KiB**; high-water values can include inherited
launcher history and are not incremental allocation measurements. No GPU was
used. Figure generation uses saved study results, with no repeated analysis.

No training, tuning, Teacher recalibration, checkpoint selection, new benchmark
inference, outcome-driven cohort change, SHERPA reanalysis, RAW download, merge,
push or EL-weighting experiment occurred. The authorized external association
study is complete and stops here.
