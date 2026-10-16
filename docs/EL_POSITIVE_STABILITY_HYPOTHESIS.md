# Task 2.11: low-stability EL positives and the evidence required for curation

**Conclusion:** Low *predicted* kinetic stability occurs among released EL
positives and varies strongly by HLA. These observations neither establish
incorrect EL labels nor identify repeat-detection probabilities. No removal,
loss weighting, soft target or label-flipping rule is selected. The next justified
experiment is a small, blinded repeat-detection validation, conditional on obtaining
appropriate metadata, before choosing a training intervention.

Classification throughout: **empirical finding** means an inspected source/data
property; **model-derived estimate** means a frozen Teacher prediction or derived
summary; **hypothesis** means an untested biological relationship; **proposed
experiment** is not an approved intervention.

## 1. Primary hypothesis and biological motivation

**Hypothesis H1:** Lower kinetic stability may be associated with less repeatable
EL detection under comparable conditions. This would make observations differ in
usefulness for a model of robust presentation. It does not imply that a detected
peptide was not genuinely detected. Complex supply, processing, HLA abundance,
turnover and MS acquisition may affect the relationship; they are competing or
interacting explanations, not measured covariates in this release.

Keep five quantities separate: an observed MS detection, kinetic half-life,
conditional repeat-detection probability, cell-surface presentation probability,
and T-cell immunogenicity. Neither kinetic hours nor their within-HLA rank is a
probability for any of the latter three outcomes. A hypothetical effect on robust
presentation need not imply improved IM prediction.

H2, stable EL-negative decoys, is secondary. Stability does not establish
processing, presentation, detection or TCR response.

## 2. What the original EL labels actually mean

**Publication-described evidence:** BigMHC combines NetMHCpan-4.1 and
MHCflurry-2.0 single-allelic EL collections. Its positives originate from MS
ligand detections, while negatives are generated examples. The authors explicitly
acknowledge detection-efficiency limitations and that random negatives are not
assured negatives. This is source-level provenance, not individual spectrum
revalidation. [BigMHC, Methods / Datasets / Epitope presentation training;
Introduction; Discussion limitations](https://pmc.ncbi.nlm.nih.gov/articles/PMC10569228/).

The task rechecked the indexed primary article text. Direct PMC/publisher and
Europe PMC opens were blocked or unavailable; the evidence register records that
access limitation. Existing Task 2.1/2.2 source audits corroborate the description.
No source examined here establishes that a low stability prediction invalidates
an observed EL positive. No new scientific data payload or external model was acquired.

**Empirical finding:** The authenticated original EL view has only `mhc,pep,tgt`.
The score and preparation ledgers add original source coordinates, hashes, model
identity and processing provenance. They do not add study/run/replicate IDs,
spectrum evidence, abundance, acquisition depth or detection opportunities.

The approved population contains **1,453,578 rows: 70,069 positives and 1,383,509
decoys**. It is a restricted canonical nine-mer/HLA/Teacher-supported population,
not all released BigMHC EL observations and not a random sample of all naturally
presented peptides. All 70,069 positives have valid finite Teacher predictions
(**100% within this cohort**, not 100% of all EL positives). There are 49 observed
HLAs out of 67 trained Teacher models; five ordinary DTU alleles lacked sufficient
fitting support and remain unsupported.

**Alignment:** The 1,453,633 pre-purge scores have 70,082 positive and 1,383,551
negative original labels. Task 2.5 removed **55 rows: 13 positives, 42 negatives**,
comprising five exact-peptide and 50 one-substitution development-cohort matches.
No development outcome is read or used by this analysis. The existing purge
ledger, rather than a new selection, establishes this reduction.

The join verifies archive identity + `el_train.csv` + original row index + raw-row
hash; original peptide/HLA/label, model identity and the contiguous prepared-row
index must agree. Pair-only joins are prohibited. The full retained population has
**1,453,578 distinct peptide–HLA keys, zero duplicate pair groups and zero
conflicting-label keys**. Its positive subset contains 57,170 distinct peptides;
9,769 positive peptides occur under more than one HLA. Cross-HLA reuse is not a
replicate experiment.

## 3. Observed low-stability EL-positive distribution

**Model-derived estimates, hours:**

| Positive population | n | Median | IQR interval | p5–p95 |
| --- | ---: | ---: | --- | --- |
| All retained EL positives | 70,069 | 3.955 | 2.135–6.930 | 0.553–16.544 |

There are 354 model-floor predictions of zero (0.505%). They are outputs of
`expm1(max(0, linear_log_prediction))`, not measured zero half-lives.

Descriptive bins reuse the **historical, scientifically unapproved** Task 2.4
reporting grid. They define reporting regions only; no new biological cutoff or
curation policy is adopted.

| Predicted hours | Positive rows |
| --- | ---: |
| [0,1) | 6,937 (9.900%) |
| [1,2) | 9,324 |
| [2,5) | 26,594 |
| [5,10) | 17,406 |
| [10,20) | 7,621 |
| [20,50) | 2,082 |
| ≥50 | 105 |

Thus the answer to “how many are low?” depends on its descriptive definition;
**9.90% below the old 1-hour reference is not an EL false-positive rate**.
B*08:01 alone contributes 2,530/6,937 (36.47%) of that region. Its contribution to
all positives is only 3.63%, illustrating the allele-composition dependence.

Source-study comparisons are **unavailable**: `el_train.csv` identifies a released
member, not which contributing paper or experiment supplied an individual row.
No unsupported study assignments are inferred from peptides or HLA names.

The run supplies full positive-only quantiles and per-HLA CSV/JSON tables, with
p1/p5/p10/p25/p50/p75/p90/p95/p99, IQR, floor counts and historical-reference counts.
Figures show all observed HLAs and label sample support; no sparse HLA is hidden.

## 4. Allele-specific patterns and Teacher reliability

| HLA | EL+ n | Predicted median h | IQR h | Below historical 1 h | DTU validation n / Spearman |
| --- | ---: | ---: | --- | ---: | --- |
| A*02:01 | 7,088 | 6.228 | 3.803–9.399 | 239 (3.37%) | 193 / 0.584 |
| B*07:02 | 5,072 | 3.678 | 2.648–4.788 | 127 (2.50%) | 133 / 0.624 |
| B*08:01 | 2,543 | 0.410 | 0.278–0.559 | 2,530 (99.49%) | 94 / 0.695 |
| B*35:08 | 95 | 0.849 | 0.696–0.963 | 78 (82.11%) | 2 / −1.000, uninformatively sparse |
| A*02:03 | 1,654 | 12.597 | 8.466–18.136 | 2 (0.12%) | 65 / 0.703 |
| A*31:01 | 706 | 15.534 | 10.575–22.370 | 3 (0.42%) | 83 / 0.774 |

**B*08:01 empirical context:** 465 DTU observations, including 134 reported zeros
(28.82%), median reported half-life 0.40 h, p95 1.20 h. Its 371 fitting and 94
validation observations have different roles. Validation MAE is 0.214 h and
Spearman 0.695; the mean prediction-minus-reported difference is −0.0025 h.
A near-zero *mean* error does not imply small individual errors or EL calibration.
The absolute error is substantial relative to this allele's short scale.

B*08:01 EL-positive median 0.410 h exceeds its decoy median 0.0884 h. The
within-HLA original-label association AUC is 0.8724, or 0.8725 outside exact/one-
substitution Teacher-fitting exposure (2,540 positives/18,472 decoys). These are
training associations against constructed decoys, not independent performance,
repeat-detection discrimination or proof of label validity/invalidity.

This pattern is consistent with a real allele-specific source scale plus usable
ranking information. It does not identify how much is biology, training-source
selection or Teacher calibration error. Across observed HLAs, positive medians
range from B*08:01's 0.410 h to A*74:01's 17.803 h. Pooling their absolute scores
can conflate allele composition with within-allele effects. Within-HLA quantiles
and ranks expose heterogeneity, but discard absolute meaning and depend on the
reference population. They are **not automatically validated alternative cutoffs**. A within-HLA
percentile would designate a low fraction even if the entire allele were stable;
its existence is not evidence that the selected observations are unreliable.

Teacher v0 is 67 separate position-specific Ridge models, alpha 10, predicting
log1p hours with a nonnegative inverse transform. It lacks sequence interactions,
shared-allele inference, calibrated prediction intervals and repeat-detection
calibration. Unsupported alleles are not replaced by nearest HLA sequences.
B*35:08 has only 25 fitting/two validation rows; its two-point correlation cannot
establish useful or consistently inverted generalization. A*32:01 also has sparse
validation (n=4) despite 852 EL positives. Both are flagged in the plots/tables. EL-positive counts are also very small for
B*39:10 (n=2), B*44:05 (n=2) and B*57:02 (n=5); their distribution bars are
flagged, not treated as precise population estimates.

**Saved validation evidence, reproduced without fitting:** 5,394 scored held-out
DTU rows, overall Spearman 0.7685, MAE log1p 0.5281 and MAE 3.972 h. On these same
rows, training-allele-mean-hours baseline MAE is 5.861 h. Twelve additional
validation rows are unsupported. This is an internal provisional global peptide
component split (Hamming distance ≤1), not an external EL validation.

A new descriptive **inference-only replay on existing held-out DTU records**
reproduces the saved metrics, then examines relevant regions:

| Held-out DTU region | n | MAE h | Mean prediction−reported h |
| --- | ---: | ---: | ---: |
| Predicted below historical 1 h | 1,767 | 0.561 | −0.113 |
| Reported positive half-life below historical 1 h | 1,560 | 1.036 | +0.947 |
| Source-reported zero | 912 | 0.815 | +0.815 |

Restricted-range correlations must not be compared naively with overall
correlation; range restriction and pooling matter. More importantly, the errors
show that a low predicted value is not a precise measurement even on DTU, and no
EL low-region calibration has been established. Reported DTU zero mechanisms
also remain unresolved.

Among retained positives, 305 have exact peptide exposure to Teacher fitting data,
39 additional rows have one-substitution-only exposure, and 69,725 are outside
both. There are 236 exact fitting peptide–HLA matches. The outside-exposure
positives still have 6,888/69,725 (9.879%) below the historical 1-hour reference.
This removes one detectable exposure mechanism, not source-study dependence or
all extrapolation. No BigMHC rescoring or Teacher refitting occurs.

**Measured-source versus predicted evidence:** 301 retained positive peptide–HLA
keys also occur in DTU, with 29 source-reported zeros and median reported half-life
5.50 h; 236 were in Teacher fitting data and 65 were held out. For those 65 held-out
pair matches, stored EL predictions versus DTU measurements have Spearman 0.7453
and MAE 5.853 h (median reported 4.30 h, median predicted 3.068 h). This is a small,
EL-positive-selected subset of the existing DTU validation data, not a new external
validation or repeated EL detection. Exact keys do not establish identical physical
assay material or conditions. Most positives (69,768) have no exact DTU pair record.
The source measurements and frozen predictions remain separately identified.


## 5. Available evidence about repeated detection

**Empirical evidence gap:** Neither the released EL view nor the authenticated
ledgers/publisher artifact metadata identify technical replicates, biological
replicates, comparable run conditions, detection opportunities or nondetections.
No suitable peptide-by-run table has been recovered from the currently available
inputs. We cannot determine which positive rows arose from a single run versus
aggregation across runs/studies. Underlying studies may have replicates; their
absence from these schemas does not prove that the experiments lacked them.

**The hypothesis that low-stability EL positives become negative in repeated
experiments cannot be directly tested with the currently available data.**

Repeat-detection probability and its stability association are explicitly null,
not zero. A duplicate peptide under another allele is not evidence for technical
or biological replication. Even same-pair duplicates, if present, would require
assay linkage and opportunity denominators before serving as repeat outcomes.

Minimal additional evidence is a small authenticated peptide-by-run detection
panel with a fixed cell/HLA context, an explicit technical/biological replicate
hierarchy, comparable sample preparation/acquisition and a distinction between
not detected and not measured. Preserve peptide identity, HLA, sample/study,
run IDs, identification/FDR criteria, intensities where available, depth/QC,
conditions and repeated opportunities. A positive-only union or frequency list
without denominators is insufficient. No such dataset is acquired in this task.

## 6. What cannot be inferred from current data

- A low prediction does not overturn an actual MS detection, demonstrate low
  repeated-detection probability, or measure a presentation probability.
- Repeated nondetection, if later observed, would not by itself prove biological
  absence; abundance, sampling and detection can generate it.
- Correlation with EL-versus-decoy labels does not establish repeat-detection
  behavior or experimentally assayed T-cell immunogenicity.
- Good overall DTU correlation does not guarantee low-range calibration, EL
  domain transportability, per-HLA reliability or individual prediction accuracy.
- Removing Teacher-fitting sequence exposure does not certify study/donor
  independence. EL acquisition/selection may itself depend on binding and detection.
- No publication-level source description establishes each row's raw experimental
  trace. No model-derived pseudolabel here is experimentally verified truth.

## 7. Secondary high-stability negative findings

**Model-derived context:** 1,383,509 original decoys have median 0.947 h,
IQR 0.294–2.123 h and p5–p95 0–5.247 h. Exactly 12,818 (0.9265%) reach the
historical ≥10 h reference. The largest counts are A*74:01 (2,601), B*42:01
(2,298), A*02:11 (1,814), A*33:03 (1,612) and A*11:01 (1,565).
These tails neither establish presentation nor justify negative→positive changes.

Positive and decoy score ranges overlap. Full per-HLA distributions and pairwise
rank associations, with half credit for ties, are saved. Their interpretation
depends on decoy construction and HLA composition. The original study/row-level
decoy-generation linkage is not available here. Negative-side intervention is
not recommended on this evidence and is secondary to H1.

## 8. Comparison of possible curation approaches

| Option | Biological/target assumption | Evidence and risk | Sampling and interpretability |
| --- | --- | --- | --- |
| A. Preserve original labels | Predict the observed EL collection as released | Supported reference; retains valid detections and existing biases | Preserves authentic anchors/exposure; does not test stability intervention |
| B. Remove selected positives | Selected observations are less useful for the declared target | No repeat evidence currently supports a rule; may discard valid biology, change HLA coverage and rely on Teacher calibration | Changes anchors, steps and negative consumption; needs matched random removal and an exposure-accounted baseline |
| C. Reduce positive loss weights | Lower predicted stability warrants less positive gradient | Preserves stored labels but changes the effective task; needs justified weight reference/uncertainty. Not inherently preferable or approved | Same rows need not mean same gradient balance; compare within-HLA permuted/matched weights under identical sampling |
| D. Continuous/soft target | Target encodes a meaningful probability or utility | Hours or percentiles are not calibrated repeat/presentation probabilities; softening real detections may misrepresent valid labels | Changes gradients/target meaning; specify normalization and sampler grouping independently of soft targets |
| E. Flip positives to negative | Discordance supports the opposite binary training target | Strongest replacement assumption; low predicted stability alone is insufficient | Changes classes, anchors, negative pool and RNG/exposure. Preserve original evidence; needs stronger validation and matched controls |

No approach B–E is selected, including apparently conservative downweighting.
HLA-specific percentiles are not a justification by themselves. EL-decoy
separation cannot validate an intervention on experimentally measured IM labels.
IM training/evaluation labels remain original for any proposed EL-only H1 test.

**Supported exposure illustration, not a proposed rule:** The authenticated
Task 2.10 code and user execution summary use one positive anchor and 16 negatives
per nine-mer batch at the original population. The static pinned sampler formula
gives 70,069 steps and 1,121,104 negative consumptions. If the 6,937 positives below
the *historical* reference were hypothetically removed, it would yield 63,132
steps and 1,010,112 negative consumptions: **6,937 fewer updates and 110,992 fewer
negative exposures**. Flipping those rows also changes the negative pool. No such
subset, mask, new labels or training view is generated.

Task 2.10 is therefore not automatically an exactly matched counterfactual for
removal/flipping. Even a weighting experiment needs accounting of positive versus
negative gradient contributions, unchanged sampling and paired controls; equal
epochs/seed alone are insufficient.

## 9. Recommended next experiment, or the precise evidence gap preventing a recommendation

**Proposed next experiment: blinded repeat-detection validation, not model
training or a label-curation intervention.** First locate one small authenticated
panel meeting section 5. Freeze a reference/index run and reserve comparable
repeat runs without choosing peptides using their future detection outcomes.
The estimand is the probability/fraction of detection in reserved opportunities,
conditional on index-run detection—not biological nonpresentation.

Use the frozen Teacher continuously within HLA, keep original observations,
flag unsupported or weakly validated models, and assess whether scores predict
repeat detection after available HLA/study, baseline abundance and acquisition/QC
adjustments. Separate technical from biological replication. Avoid conditioning
on abundance observed only after successful repeat detection; record missingness
and use baseline/independent abundance where available. Account for within-peptide
and experiment dependence, and selection into the index-positive population.
Add within-HLA score-permutation controls and a Teacher-exposure sensitivity
analysis. Do not claim causality from observational associations.

Evidence against the hypothesis includes no monotonic relation, an opposite
relation, loss of association after abundance/depth adjustment, or instability
across replicate contexts/Teacher support. Imprecise estimates or unreliable
Teacher predictions mean inconclusive evidence, not proof of no relationship.

If repeat outcomes support a transportable association, a later training study
could test **one separately approved** EL intervention against a paired baseline
and matched random/score-permuted control. Predeclare affected observations and
why, whether labels/weights/inclusion/targets change, unsupported handling,
expected effect size and falsification. Fix initial tensors, seed, architecture,
EL/IM identities, original IM labels and evaluation. Log actual sampler exposure,
updates, row IDs and effective gradient balance. If any schedule or sampler must
change, rerun the matched baseline and controls under that schedule; do not reuse
Task 2.10 as if its exposure were identical. Source-study matching is unavailable
until that linkage is recovered.

Freeze the analysis and evaluation before seeing new outcomes. Do not choose
cutoffs or weights through repeated inspection of the 383-row IM development
metrics. Failure to beat the matched intervention control, or dependence on a
poorly supported allele, would argue against a stability-specific training effect.
No training comparison is run here.

Task 2.10's 70,069 EL/214 IM optimizer steps, FP32/seed42 and development AUROC
0.693124/AUPRC 0.476174 are **user-provided execution context**. The Mac has no
Task 2.10 execution artifacts to reauthenticate them. Only its approved code/config
and the source training-population counts are locally verified. These preliminary
metrics are not independent-test results or a criterion for choosing this plan.

## 10. Decisions requiring scientific approval

1. Which target is intended: observed EL detection, repeatable detection, robust
   presentation or downstream T-cell response, and which evidence links them?
2. Whether to acquire a narrowly scoped replicate panel and its opportunity/QC
   metadata; define technical versus biological replication and the estimand.
3. Whether Teacher reliability/uncertainty is adequate in the relevant HLA/range;
   no universal absolute or HLA-relative curation cutoff is approved.
4. Only after the evidence gate: whether any A–E intervention is justified, its
   predeclared specification, supported populations and uncertainty handling.
5. Paired baseline/control schedule, gradient/exposure accounting, matched random
   or score-permutation controls and an untouched evaluation/selection plan.

### Reproduction and artifacts

Implementation: `el_positive_stability_analysis.py`; configuration:
`configs/el_positive_stability_analysis_v0.json`. Inputs are accessed through the
existing path resolver and 19 exact SHA256 gates. The original ZIP and evaluation
members are not opened. Parent Teacher/scoring/preparation manifests and receipts
are verified; source scores, labels, records and completed baseline artifacts are
unchanged. No corrected views or override payloads are read.

Read-only inspection (standard library; no scikit-learn fitting required):

```sh
PYTHONPATH=src python3 -B -m stability_label_curation el-positive-analysis --json
```

Canonical outputs live outside Git under
`~/codex/runs/stability-label-curation/task-2_11-el-positive-reproducibility/`.
They include positive-only and secondary tables, all-HLA summaries, alignment,
held-out Teacher error regions, repeat-evidence assessment, exposure illustration,
and three figures in SVG and PNG. Quantiles use Type 7 linear interpolation on
saved float64 hours; curves display a 101-point quantile grid rather than exact
individual ECDF steps. A log1p *display spacing* improves readability without
changing source values or defining a training transform. Colors/counts flag fewer than ten EL positives or sparse
DTU validation (display annotations, not eligibility rules); plotted AUC is explicitly an original-training-label association.

An isolated optional plotting environment under project data storage contains
Matplotlib 3.11.2 and NumPy 2.5.4; the existing Teacher/BigMHC environments are
unchanged. Full installed versions are captured in run logs. Ordinary unit tests
need no plotting or network dependencies. SVG dates and IDs/PNG metadata are fixed
for deterministic rendering in that recorded environment.

After committing, create exactly one run with `run_manifest.create_run`, the
configuration and all `resolve_inputs` identities, then call:

```python
analysis.execute(config_path=config_path, out=run, paths=paths)
analysis.execute(config_path=config_path, out=run, paths=paths, verify_existing=True)
```

Use the plotting environment for figure generation; `--no-figures` is available
for explicit JSON/CSV-only reproduction. The execution receipt records code,
input/output hashes, no training or label changes and inaccessible repeat outcomes.
Generated rows/figures remain outside Git; only code, small configuration, tests
and this report are committed on the Task 2.11 branch. No merge or push.
