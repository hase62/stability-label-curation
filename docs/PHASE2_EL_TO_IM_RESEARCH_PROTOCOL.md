# Phase 2 EL-to-IM research protocol, version 2.0.0

Task 2.0 records the user's updated scientific decisions. It authorizes protocol
and leakage diagnostics, not training, actual splits, correction masks, or dataset
acquisition. The [Task 1.9 dossier](GATE0_SCIENTIFIC_DECISION_DOSSIER.md) remains
historical evidence. Its provisional intervention on questionable IM positives
has been superseded by the EL intervention described here.

## Scientific question and definitions

Does correcting potentially unreliable MHC-I eluted-ligand training labels with
an independent peptide–MHC kinetic stability Teacher improve prediction of
experimentally assayed T-cell responses after EL-to-IM transfer learning?

| Term | Meaning |
| --- | --- |
| EL | MHC-I presentation labels: MS-identified ligands and constructed negatives/decoys |
| IM | T-cell immunogenicity labels from functional immune-response assays |
| Stability Teacher | Independently trained kinetic half-life predictor |
| EL baseline | Model trained using original EL labels |
| EL corrected | Model trained using stability-informed candidate pseudolabels |
| IM evaluator | Each EL model transferred with identical IM training data and procedure |
| Final evaluation | Shared independent, experimentally assayed T-cell response tests |

EL positivity does not establish T-cell immunogenicity. A stability pseudolabel
is a modeling intervention, not a new experimental EL or IM measurement.

## Versioned D1–D8 decisions

Machine-readable authority: [phase2_el_im_protocol.json](../configs/phase2_el_im_protocol.json).
These decisions change research scope, not canonical observations.

| ID | Status | Current direction and limits |
| --- | --- | --- |
| D1 | adopted | Z1 reported-zero-inclusive regression: 27,031 ordinary DTU HLA-A/B nine-mers, 72 identifiers, 4,711 reported zeros. Their generation and physical interpretation remain unresolved. Z2/Z3 are conceptual alternatives, not scheduled implementations or experiments. |
| D2 | adopted | All 1,135 C67S records stay in the registry but are outside Teacher training and primary evaluation. Never map constructs to wild type automatically. |
| D3 | adopted | Jappe Tm stays in the registry but is outside current Teacher and EL-correction experiments. No conversion to hours. |
| D4 | methodology_pending | Review split rules and support before choosing algorithm or thresholds. No published “hard” designation serves as clearance. |
| D5 | adopted_conceptual_design | Matched EL baseline/corrected models, then matched IM transfer and common independent tests. |
| D6 | adopted_directions_thresholds_pending | Baseline, correction A (low-stability EL=1 → pseudo-0), correction B (A plus high-stability EL=0 → pseudo-1); matched random perturbation and affinity-only controls. |
| D7 | adopted_principle | Prioritize experimentally assayed IM positives and justified negatives; proposed primary AUPRC depends on valid positive/negative labels. Cohorts remain unselected. |
| D8 | adopted_basic_compliance | Preserve provenance and check applicable terms before redistributing raw data or weights. No legal conclusion from absent terms. |

## Principal matched comparison

1. Initialize both EL models identically under a declared common initialization
   policy. Random versus binding-trained initialization remains to be specified
   and audited. An already IM-trained BigMHC checkpoint is not the common starting
   point for the principal causal comparison.
2. Train one with original EL labels and the other with the intended EL
   pseudolabel intervention. Hold architecture, loss, representation,
   initialization policy, hyperparameter-selection rules, training budget and
   seed pairing comparable. Record consequences such as changed class balance.
3. Transfer both EL models using the same IM training data and procedures.
4. Compare on the same untouched, experimentally assayed IM tests. Preserve
   experimental IM labels unchanged.

No separate adaptation experiment starting from an existing BigMHC-IM model is
required. Stability scores are not extra inputs to the final IM evaluator.

## EL correction and controls

Correction A proposes flipping low-predicted-stability EL positives to pseudo-0.
Correction B adds high-predicted-stability EL negatives to pseudo-1. Thresholds,
uncertainty requirements and multi-allelic assignments remain pending. An
EL=0→1-only ablation may later separate directional effects; it is not scheduled
here. Plan matched random-label perturbations and affinity-only corrections;
record matching strata, direction and perturbation counts before comparisons.
Affinity-conditioned stability can be a separately declared secondary analysis.

EL pseudolabel flipping replaces the earlier provisional no-label-flipping rule
**for EL training interventions only**. IM experimental labels remain unchanged.
Never edit original EL labels in place. A future correction ledger must retain
original/proposed labels, reason, Teacher identity, confidence and provenance.
An MS-observed ligand remains an experimental EL observation even if its
pseudolabel changes. High predicted stability does not prove that a decoy was
experimentally presented. Calling such changes experimentally validated label
repairs would exceed the evidence.

## Source and modality scope

The canonical registry contains 30,886 measurement-value records, not that many
independent experiments or approved training samples. Its 27,031 SPEARMINT
aliases add no measurements and do not define an independent external test.
The selected Teacher scope retains source-reported zeros, without asserting
synthetic status, exact physical zero, missingness or censoring. Kinetic hours
and thermal degrees Celsius remain different measurements. C67S and Jappe
records are preserved unchanged outside the current experimental scope.

Task 2.0 computes only sequence diagnostics on ordinary DTU nine-mers from the
approved Task 1.8 registry. It does not materialize a Teacher training table,
assign folds, transform targets, or regenerate raw observations.

## IM tests and selection discipline

Before selection or checkpoint use, audit peptide identity, HLA restriction,
assay/label definitions, study/subject/donor/antigen relationships, exact and
near-sequence training exposure, and pretrained checkpoint history. Distinguish
assayed IM negatives from constructed decoys. Freeze external test definitions
before Teacher, EL-correction and evaluator hyperparameter/threshold selection
if their information could influence those choices. No cohort or test outcome
is accessed in this task.

Proposed primary AUPRC requires meaningful experimental positive and negative
labels. Predeclare prevalence, aggregation, multiple paired seeds, uncertainty
intervals and secondary metrics. Test prevalence and dependence groups affect
interpretation. No performance claim is made here.

## Pending decisions before later execution

- Hard-split similarity definition, grouping scope, thresholds and support rules.
- Independent IM cohort selection, negative evidence and freeze timing.
- EL correction thresholds, confidence/calibration and multi-allelic assignment.
- Matched-control construction and affinity-comparator training exposure.
- Common initialization and complete checkpoint training-history audit.
- Evaluation metrics/aggregation, budgets, seeds and uncertainty protocol.

The [hard-split audit](HARD_SPLIT_METHODS_AND_LEAKAGE_THREATS.md) documents evidence,
controls and computational limits. Task 2.1 should narrowly specify a source-
and checkpoint-exposure audit and candidate split comparison plan for review;
actual acquisition, splits and training need separate authorization.

## Reproduction and canonical evidence

```sh
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
PYTHONPATH=src python3 -B -m stability_label_curation leakage inspect --json
```

Default inspection is offline and read-only. `--registry PATH --config PATH`
supports explicitly pinned fixtures; hashes are required even for overrides.
`--max-mismatches 0|1|2` changes a diagnostic rule, not an approved threshold.
Report writing requires `--reports-dir` in an existing project run and all three
derived inputs recorded in that run. See the companion document for the exact
run commands, input identities and determinism procedure.
