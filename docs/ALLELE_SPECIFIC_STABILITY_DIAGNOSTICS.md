# Task 2.6: allele-specific stability diagnostics

**Scientific status:** The historical LOW <1 hour and HIGH ≥10 hour criteria
are arbitrary engineering defaults and are scientifically unapproved for actual
BigMHC corrected-model training. Both LOW-only and LOW+HIGH views from Task 2.5
remain immutable historical artifacts. This task changes their current scientific
status; it does not rewrite their manifests, scores, overrides, labels or CSVs.
The new checksum-linked `historical_correction_shift_summary.json` marks each of
the six historical corrected views unapproved. No alternative is selected.

## Scope, inputs and methods

[The diagnostic configuration](../configs/allele_stability_diagnostics_v0.json)
pins 16 existing inputs through the project path resolver. It reuses the Task 2.4
configuration/evidence, the frozen Teacher, its fitting partition and saved
validation metrics, canonical DTU observations, saved EL/IM training scores and
parent receipts, plus Task 2.5 manifests, inventories and B*08:01 diagnostic.
Parent receipts and model/partition provenance are checked. Actual inputs are
hashed before and after analysis and recorded in the canonical run manifest.
The BigMHC archive, development cohort rows, test payloads and model weights other
than the saved JSON Teacher are not opened. No fitting, prediction rescoring,
new overrides or training views are performed.

Distributions use **all Task 2.4 supported training scores before Task 2.5 purge**:
1,453,633 EL rows and 3,485 IM rows. Every trained HLA model (67) appears in output,
including n=0 and null statistics for absent task/classes. There are scored rows
for 49 EL and 35 IM HLAs. Unsupported Teacher alleles are reported separately;
no fuzzy allele mapping or C67S substitution is allowed.

For EL=0/1 and IM=0/1 separately, reports give n, min/max, median, p5/p25/p75/p95,
IQR width, fraction <1 h and fraction ≥10 h. Strictly >10 h is additionally
reported to distinguish the word “above” from the historical inclusive HIGH rule.
Prediction quantiles use empirical Type 7 linear interpolation of stored float64
hours. DTU quantiles use the existing Decimal implementation and preserve decimal
text in aggregate outputs. No new stability cutoff is introduced.

ROC-AUC is the probability of a positive-labelled row ranking above a negative,
with half credit for ties. Higher stability is the declared positive direction.
An AUC is reported only with at least five rows in **each** class; this is a
transparent descriptive sample-support rule, not a correction threshold or a claim
of statistical precision. Counts and explicit missing/insufficient-class reasons
remain available for every HLA. No confidence interval, tuning or independent
predictive evaluation is performed. Array storage retains eligible prediction
values, not the 15-million-row source EL table.

Associations are reported for all scored rows and three mutually exclusive strata:
exact peptide exposure to actual Teacher fitting data across any HLA;
one-substitution-only exposure; and outside either exposure. These reuse frozen,
authenticated Task 2.4 flags tied to the verified Teacher fitting partition. Exact
peptide–HLA exposure counts are also retained. Sparse exposed strata commonly
cannot support AUC. Outside-one-mismatch exposure is not study/donor independence.

EL positives are publisher-described MS-observed ligands; EL negatives are
constructed negative/decoy labels, without per-row experimentally verified absence.
IM analyses retain original publisher training labels, whose detailed assay-level
origin is limited. Training associations do not prove a discordant experimental
label incorrect, and EL-decoy discrimination is not T-cell response validation.

## Focused observations

Values below are frozen-artifact numerical observations, rounded for readability.
IQR intervals are p25–p75; detailed reports preserve the computed values.

| HLA / original class | n | Median h | IQR interval h | p5–p95 h | <1 h | ≥10 h |
| --- | ---: | ---: | --- | --- | ---: | ---: |
| B*08:01 EL=1 | 2,543 | 0.410 | 0.278–0.559 | 0.058–0.772 | 99.49% | 0% |
| B*08:01 EL=0 | 18,473 | 0.088 | 0–0.198 | 0–0.419 | 99.97% | 0% |
| B*08:01 IM=1 | 22 | 0.568 | 0.346–0.654 | 0.158–0.741 | 100% | 0% |
| B*08:01 IM=0 | 94 | 0.347 | 0.233–0.515 | 0.086–0.742 | 97.87% | 0% |
| B*35:08 EL=1 | 95 | 0.849 | 0.696–0.963 | 0.542–1.199 | 82.11% | 0% |
| B*35:08 EL=0 | 462 | 0.758 | 0.663–0.880 | 0.520–1.072 | 89.18% | 0% |
| A*02:03 IM=1 | 7 | 8.805 | 7.115–14.107 | 6.654–19.807 | 0% | 42.86% |
| A*02:03 IM=0 | 31 | 11.412 | 8.685–13.955 | 5.193–24.562 | 0% | 64.52% |

There are no supported B*35:08 IM score rows. Missing data are not assigned zero
stability, zero counts interpreted as negative biology, or fabricated AUCs.

| HLA | EL association AUC | IM association AUC | DTU n / reported zeros | DTU median / p95 h | Saved validation n / Spearman |
| --- | ---: | ---: | --- | --- | --- |
| B*08:01 | 0.8724 | 0.6707 | 465 / 134 (28.82%) | 0.40 / 1.20 | 94 / 0.6952 |
| B*35:08 | 0.6030 | unavailable | 27 / 2 (7.41%) | 0.50 / 5.94 | 2 / −1.0, too sparse to assess reliability |
| A*02:03 | 0.9506 | 0.4286 | 379 / 14 (3.69%) | 7.10 / 45.62 | 65 / 0.7033 |
| A*31:01 | 0.9350 | unavailable: 2 positives | 382 / 34 (8.90%) | 2.80 / 73.04 | 83 / 0.7736 |

At the declared sample-support rule, 47 EL and 20 IM HLAs have available AUCs.
EL AUCs range 0.6030–0.9783 (none below 0.5); IM AUCs range 0.4286–0.8590
(two below 0.5). These ranges describe heterogeneous, selected training sets;
they are not pooled performance estimates or evidence of experimental error.

For B*08:01, excluding all exact/one-substitution Teacher fitting exposure leaves
EL AUC 0.8725 (2,540 positives / 18,473 negatives) and IM AUC 0.6237
(15 / 93). This removes one detectable exposure mechanism but establishes no
independent evaluation. B*35:08 EL has no such fitting exposure; its AUC is still
0.6030, with very sparse source/validation support.

## Interpretation and historical correction consequences

B*08:01's low DTU scale and higher positive-versus-negative prediction ranks are
consistent with an absolute-scale failure rather than absence of within-HLA
ranking information. The fixed one-hour rule lies above most source measurements
and nearly all scored positives. That is numerical consistency, **not** a causal
explanation or proof that the Teacher is calibrated for EL/IM. DTU measurement
selection, assay/reporting mechanisms, Teacher error and domain differences remain
unresolved. Reported DTU zeros retain unresolved semantics.

B*35:08 combines low source scale, modest EL association and only 25 fitting/two
validation observations. The two-point validation Spearman of −1 cannot establish
poor generalizable discrimination or reliable opposite ranking. Uncertainty is
substantial; neither its original positives nor its pseudolabels are validated by
these statistics.

The HIGH rule has a different failure mode: A*02:03 has strong EL/decoy association
but IM negatives have a higher median prediction than IM positives (AUC 0.4286,
only seven positives). It proposes 20/31 IM negative→positive changes. A*31:01
proposes 41/68 such changes while having only two IM positives—insufficient for
AUC. Stable peptide–MHC binding does not establish T-cell recognition. These
observations do not establish the cause of nonresponse or authorize relabeling.

Historical Task 2.5 retained-population counts, not new proposals:

| Task | Original positive / negative | Historical LOW 1→0 | Historical HIGH 0→1 | Historical LOW+HIGH positive / negative |
| --- | --- | ---: | ---: | --- |
| EL | 70,069 / 1,383,509 | 6,937 | 12,818 | 75,950 / 1,377,628 |
| IM | 955 / 2,473 | 55 | 281 | 1,181 / 2,247 |

B*08:01 loses 2,530/2,543 retained EL positives and 22/22 retained IM positives.
Its historical corrected IM group has zero positives. B*35:08 loses 78/95 EL
positives. Reports retain both Task 2.4 pre-purge and Task 2.5 retained counts by
HLA and direction; their populations must not be silently pooled. Flags for losing
a majority/all original positives are descriptive, not new eligibility rules.

## Future strategies: no choice or cutoff adopted

| Candidate approach | Biological assumption | Reference/calibration needed | Missing evidence and failure modes |
| --- | --- | --- | --- |
| A: allele-relative criteria | Within-HLA rank is relevant even when absolute scales differ | Prespecified allele distribution, sampling/support checks, task-specific deployment calibration | Source/reference selection can bias ranks; relative low stability can still be compatible with real presentation or immunogenicity |
| B: remove/downweight discordance | Discordance identifies less useful supervision, so withholding influence helps | Independent confidence/error reference and matched-removal/weighting controls | Valid low-stability biology may be removed; allele and class-selection bias; no demonstrated benefit yet |
| C: binary pseudolabel flipping | Discordance supports the **opposite** binary target rather than uncertainty | Directional error probabilities and allele/task-aware calibration against appropriate outcomes | Strongest replacement assumption; domain shift, Teacher errors, decoy construction and TCR biology may invalidate it |

A result on constructed EL decoys cannot establish that a functionally assayed IM
negative is actually positive, or vice versa. None of the strategies is selected.
Before corrected BigMHC training, scientific review must choose the permitted
intervention and reference population, justify EL and IM separately, define
uncertainty/unsupported handling and a validation/control plan, and explicitly
approve any subsequent numeric criteria. The current absolute rules remain
unapproved, not a fallback while that review is pending.

## Reproduce offline

```sh
PYTHONPATH=src python3 -B -m stability_label_curation allele-diagnostics
```

Default inspection is read-only and prints deterministic aggregate JSON. Explicit
`--input INPUT_ID=PATH` overrides remain checksum-gated for synthetic fixtures.
For a canonical run after committing:

```python
from stability_label_curation.paths import resolve_paths
from stability_label_curation import allele_stability_diagnostics as diagnostics, run_manifest

paths = resolve_paths()
config_path = paths.repository_root / diagnostics.CONFIG
config = diagnostics.load_config(config_path)
_, inputs = diagnostics.resolve_inputs(config, paths)
run = run_manifest.create_run(
    paths=paths, run_id="task-2_6-allele-stability-diagnostics",
    kind="allele_stability_diagnostics", config=config_path,
    inputs=[item["path"] for item in inputs], argv=["Task 2.6 diagnostic"],
)
diagnostics.execute(config_path=config_path, out=run, paths=paths)
diagnostics.execute(config_path=config_path, out=run, paths=paths, verify_existing=True)
```

The five aggregate reports and `execution_verification.json` are written under
`reports/`. Existing reports are never overwritten. `--out <run>` is the CLI write
option; add `--verify-existing` for complete read-only replay. No row-level data,
correction masks or training outputs are generated. Source payloads, scores,
historical overrides, and corrected/original views remain unchanged.
