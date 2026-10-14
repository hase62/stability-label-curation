# Gate 0 scientific decision dossier (Task 1.9)

**All eligibility decisions are `decision_pending`.** This dossier prepares
aggregate evidence and alternatives; it approves no policy, constructs no training
table or inclusion mask, generates no splits, and fits no model. The ultimate
study asks whether stability-derived holding-out of questionable immunogenicity
positive training samples improves external prediction under controlled comparisons.
That utility remains a **scientific_hypothesis**, not a performance result.

## Evidence vocabulary and execution provenance

- `confirmed_evidence`: previously captured publication/source evidence or directly
  verified source lineage. It never certifies every underlying assay trace.
- `quantitative_observation`: counts/statistics computed from immutable registry files.
- `scientific_hypothesis`: possible mechanisms, biases or future effects not established.
- `candidate_recommendation`: a review proposal, with status `decision_pending`.
- `decision_pending`: no eligibility, architecture, splitting or inclusion approval.

The parent is canonical run `task-1_8-canonical-observation-registry`, code
`b3b7d060e83d76dbaa2c55b3aa4bbc72187135ad`. Six derived inputs are read: observations,
SPEARMINT aliases, registry validation summary, lineage matrix, evidence manifest
and parent run manifest. Every file is hash-gated before analysis, schemas/IDs,
units, zero flags, exact alias coverage and parent counts are checked, and hashes
are rechecked at completion. Relevant committed registry configuration is pinned.

| Derived input | Verified SHA256 |
|---|---|
| canonical_observations.jsonl | `471fa7989e7665f722998fc1314d63ef87e8d4768846bec98638e6357de87eee` |
| spearmint_stage2_aliases.jsonl | `6a07b46999dc9814dbeef5b457ef047dcdf18b26d7bd7726189c2eb27abd21e9` |
| registry_validation_summary.json | `fbd2c397c6c12d7f2e783926176db7202aa2ea0d648b02e3035d88696b0387e9` |
| source_lineage_matrix.json | `b5d3411af37ef60543168b46086b4203d063b90fdde6e87f83fd8996eeb2010f` |
| source_evidence_manifest.json | `26be9e7f5f6611a642b1b0d2d6f68369d34fa0adfca48964c3582cf4a82c7fa1` |
| parent manifest.json | `13ecca0a28aefd6418ef28bb1fbeec28e72b7fa3caae54eaa9a047eed4204270` |

Original scientific artifacts are not reread, rehashed, regenerated or downloaded
in Task 1.9. Their checksums/provenance are inherited from the parent evidence,
not fabricated as direct inputs to this run. Paths use the project resolver;
configuration uses portable parent-relative paths, not a particular user's home.

## Verified coverage (`quantitative_observation`)

| Representation | Records | Zeros | Positives | Original identifiers |
|---|---:|---:|---:|---:|
| DTU, all | 28,166 | 5,679 | 22,487 | 75 |
| DTU, ordinary A/B | 27,031 | 4,711 | 22,320 | 72 |
| DTU, C67S | 1,135 | 968 | 167 | 3 |
| Jappe A Tm | 1,094 | 0 | 1,094 | 1 |
| Jappe B Tm | 1,354 | 0 | 1,354 | 1 |
| Jappe C Tm | 272 | 0 | 272 | 1, with 136 peptides in two contexts |
| Canonical measurement values | 30,886 | — | — | Mixed modalities, not a common target |
| SPEARMINT aliases, separate | 27,031 | 4,711 | 22,320 | Same ordinary DTU observations |

SPEARMINT split counts remain 21,626 / 2,705 / 2,700. These partitions do not
supply independent experiments or an approved external evaluation cohort.
All figures above are recomputed and compared with parent validation; mismatches
fail instead of adding/deleting observations. Registry positives retain unverified
individual measurement origins. Counts are not donors or independent experiments.

## Reported-zero evidence and alternatives

`confirmed_evidence`: the [2016 audit](NETMHCSTABPAN_2016_SOURCE_EVIDENCE.md)
documents experimental dataset-level provenance and separately described artificial
training augmentation. It found no row-specific zero mechanism, detection limit,
rounding rule or censoring convention in the reviewed main article. Numerical
zero is not proof of synthetic augmentation, missingness, physical zero or censoring.

`quantitative_observation`: ordinary DTU zero fraction is **17.4281%**. A has
1,744/13,335 zeros (**13.0784%**), B 2,967/13,696 (**21.6633%**). Thus a positive-only
scenario removes different proportions across loci as well as individual alleles.
All 72 ordinary identifiers retain at least one positive value, but representation
and sample support change.

The descriptive high-zero threshold is **>=50%**, not a scientific eligibility
threshold. Four ordinary alleles meet it:

| Original identifier | Total | Zeros | Positive-only count | Zero fraction |
|---|---:|---:|---:|---:|
| HLA-B*41:01 | 368 | 220 | 148 | 59.78% |
| HLA-B*45:01 | 368 | 247 | 121 | 67.12% |
| HLA-B*51:01 | 353 | 179 | 174 | 50.71% |
| HLA-B*55:01 | 378 | 210 | 168 | 55.56% |

For example, B*45:01's cohort share drops by **0.8193 percentage points** under
hypothetical Z2. Per-allele before/after shares and count changes are in the JSON
report. Seven alleles have fewer than 50 positives (also fewer than 100), and
13 have fewer than 200. These descriptive cutoffs are not adopted support rules.

Positive-only ordinary half-life summaries, hours: minimum **0.05**, p05 **0.20**,
p25 **0.60**, median **2.10**, p75 **7.60**, p95 **29.20**, p99 **57.881**, maximum
**256.70**. Quantiles use Type 7 interpolation with Decimal precision 50. Every
positive reports two decimal places; the smallest values include 0.05 (1 row),
0.10 (436), 0.11 (1), 0.14 (1), 0.15 (13), 0.19 (1) and 0.20 (1,274).
Reported precision is not an independently established resolution/detection limit.
These ordinary-cohort statistics differ from summaries including C67S.

| Reported hours bin | Ordinary records |
|---|---:|
| Negative | 0 |
| Exact zero | 4,711 |
| (0, 0.1] | 437 |
| (0.1, 0.5] | 4,655 |
| (0.5, 1] | 3,090 |
| (1, 2] | 2,954 |
| (2, 5] | 3,687 |
| (5, 10] | 3,200 |
| (10, 24] | 2,728 |
| (24, 48] | 1,217 |
| (48, infinity) | 352 |

Bins are descriptive, not censoring or label categories. They cover all 27,031
ordinary values; no zero is removed from the registry.

| Candidate; all `decision_pending` | Hypothetical coverage | Advantages | Risks/failure modes |
|---|---|---|---|
| Z1 reported-zero-inclusive regression | 27,031 continuous values; 72 identifiers | Preserves reported low-stability information; simple reported-target reference | Unknown zero process could distort targets or reward modeling an assay artifact |
| Z2 positive-only regression | 22,320 continuous values; 72 identifiers; 4,711 zeros unused for that objective | Avoids treating ambiguous zeros as precise continuous measurements | Measurable/stable-complex selection; changing allele shares; loss of low-stability learning |
| Z3 reporting-status plus positive-value objectives | 27,031 status values and 22,320 continuous values | Preserves source reporting information without physical-zero interpretation | Extra objectives/calibration; could learn reporting-process bias; not a formal censored likelihood |

`candidate_recommendation`: review Z1 as a reported-value reference with
predeclared Z2 sensitivity; evaluate Z3 separately after defining reporting-status
semantics and model-selection rules. **No primary zero policy is selected.**
Rounding, preprocessing, censoring, missingness and augmentation explanations
remain hypotheses; no epsilon, threshold imputation or synthetic labels are used.

## C67S construct alternatives

`confirmed_evidence`: Table II separately names three constructs; the reviewed
main text did not establish their modification's experimental purpose. No biological
equivalence to wild type, construct sequence or normalization is approved.

| Original identifier | Records | Zeros | Positives | Zero fraction | Positive median hours |
|---|---:|---:|---:|---:|---:|
| HLA-B*14:01(C67S) | 374 | 333 | 41 | 89.04% | 0.60 |
| HLA-B*14:02(C67S) | 382 | 286 | 96 | 74.87% | 0.825 |
| HLA-B*39:06(C67S) | 379 | 349 | 30 | 92.08% | 0.80 |

C67S aggregate zero fraction is **85.2863%**, versus ordinary **17.4281%**.
Separate positive distributions are reported, without treating construct and
ordinary measurements as biologically interchangeable.

| Candidate; all `decision_pending` | Potential coverage | Required evidence and implications |
|---|---|---|
| C1 ordinary A/B primary scope | 27,031 records / 72 ordinary identifiers; all C67S preserved in registry | Define a wild-type prediction goal; ordinary names alone do not individually certify material identity. No supported inference to mutant behavior |
| C2 separate construct-specific analyses | 1,135 records / 3 literal constructs | Clarify construct purpose and assay context; only 41/96/30 positive values limit positive-regression validation and generalization |
| C3 combined with explicit construct representation | Potentially 28,166 records / 75 identifiers | Authenticate mutant sequences and residue indexing, molecular representation, assay comparability, modification purpose and zero process before adoption |

`scientific_hypothesis`: silent wild-type mapping may misattribute construct-dependent
binding/groove behavior and bias predictions. Its magnitude is unknown.
`candidate_recommendation`: review C1 primary scope and C2 separate evidence;
C3 remains dependent on missing molecular/assay evidence. No mutant mapping,
exclusion or training eligibility is implemented.

## Modalities and context limitations

`quantitative_observation`: **14 exact peptide–HLA keys** appear in both kinetic
and thermal groups: **8 HLA-A*02:01**, **6 HLA-B*07:02**, all **9-mers**.
DTU covers only 9-mers; Jappe covers 8–11-mers. This small two-allele overlap is
not evidence for general calibration across 75 identifiers or wider peptide lengths.

DTU reports kinetic half-life **hours**, with individual row conditions unverified.
Jappe reports thermal transition estimates **degC** in distinct C1R contexts.
Assay material, temperature treatment and row-level replicate identity are not
established as equivalent. No cross-modality numerical fit or target conversion occurs.

All 136 C pairs retain 272 distinct observation IDs and context values, 136 each
from C1R-A*02:01 and C1R-B*07:02, restricting HLA-C*04:01 in both. No averaging
or independent-replicate claim occurs. The 150 repeated keys comprise these
136 plus the 14 cross-modality keys. The C359 distribution remains unavailable.

`candidate_recommendation`: consider a primary kinetic labeler from DTU and a
separate thermal model or orthogonal signal from Jappe. These are distinct future
directions; no common numeric teacher or cross-modality calibration is proposed.

## Leakage threat model

| Risk | Current evidence/availability | Proposed future control; `decision_pending` |
|---|---|---|
| Exact pair / context reuse | Detectable: 150 repeated method/context keys | Group provenance-equivalent and same-key records; keep C contexts together during future split design |
| Exact peptide across HLA | Ordinary DTU: 5,633 unique peptides; 3,930 occur on multiple HLA identifiers, involving 25,328 records; maximum 33 identifiers/peptide | Exact-peptide grouping across all relevant representations and modalities |
| Full-registry peptide reuse | 8,202 unique peptides; 3,942 occur on multiple identifiers, involving 26,482 records; maximum 36 identifiers/peptide | Do not count measurement-record sample size as independent sequence support |
| SPEARMINT / DTU reuse | All 27,031 alias targets identical; no new measurements | Never pool aliases as observations or claim its test split is external |
| Similar/homologous sequences | Registry has sequences; no chosen metric/threshold or cluster computation | Predeclare similarity metric, alignment, threshold and transitivity; audit peptide families |
| Original studies / related antigens | DTU prior-study incorporation known; per-row study/antigen lineage incomplete | Study/family grouping when authenticated metadata become available |
| Wild-type/mutant peptides | Peptide variant/reference relationships unavailable; C67S is an HLA annotation, not peptide mutation metadata | Obtain verified peptide/reference/variant relationships; no guess from edits |
| Donor / assay / source antigen | Row tags incomplete/unavailable | Group by authenticated donors, studies, assays and antigen sources later |
| Immunogenicity overlap | Datasets not acquired; overlap unknown, not absent | Exact and similarity audit before external freeze and model selection |
| Checkpoint immunogenicity exposure | Training-corpus/label provenance unreviewed here | Binding-trained initialization with exposure audit; no contaminated immunogenicity checkpoint |
| Evaluation information in selection | Future process risk | Freeze external sets before they could influence labeler/evaluator thresholds or hyperparameters |
| Pretrained stability predictor reuse | Published predictors may use these records; checkpoint-specific membership unaudited | Verify predictor training membership; reused measurements cannot certify external validation |

Released SPEARMINT partitions have zero exact peptides crossing splits in the
read aliases. This does not verify similarity/80%-cluster claims, donor independence,
absence of checkpoint exposure, or suitability as an independent evaluation cohort.

## Candidate validation designs

| Candidate | Prevents | Does not prevent | Required metadata / feasibility | Generalization interpretation |
|---|---|---|---|---|
| S1 random pairs, simple reference | Exact pair crossing only with grouping of duplicates/contexts/aliases | Same peptide on other HLA, homologs, study/donor or pretrained exposure | Pair and provenance keys available; support after policy selection undecided | Mostly interpolation |
| S2 exact-peptide-disjoint | Identical peptide crossing alleles/modalities/contexts | Homologs, antigen families, source/checkpoint exposure | Strings available; balance allele support and rare positives later | New exact peptides, not necessarily new families |
| S3 similarity-cluster-disjoint | Defined similar-sequence crossing | Relationships outside chosen definition, shared studies/donors/checkpoints | Metric, threshold, alignment, clustering/transitivity and support rules pending; no clusters built | New groups under the declared sequence definition |
| S4 allele-stratified | Representation/support control, not leakage prevention by itself | Exact/similar sequences unless combined with S2/S3 | Counts available; low-support alleles/constructs constrain holdout sizes | Known-allele performance; unseen-allele holdout is separate |
| S5 source-study-disjoint | Authenticated study/donor/assay reuse | Shared sequences and checkpoints without extra controls | Not defensibly supported now: source IDs do not identify all original experiments | New studies only when traceability and support exist |

`candidate_recommendation`: review S2 as a kinetic validation candidate, S1 as an
interpolation reference, and S3 as a sensitivity/generalization design after its
metric and support requirements are specified. Short 8–11-mers require an explicit
unequal-length identity definition; do not silently adopt the preprint's 80% claim.
Allele stratification alone cannot remove leakage. A Jappe thermal cohort is not
an interchangeable study-disjoint kinetic evaluation set. **No splits are created.**

## Future immunogenicity study guardrails

These are user-prescribed design constraints, documented but not implemented:

- Keep evaluator architecture and loss unchanged across comparisons; use common
  initialization from a binding-trained checkpoint with verified corpus exposure.
- Do not use an immunogenicity-trained checkpoint contaminated by original labels.
- Hold out/filter questionable **positive training examples only**; never relabel
  them negative and never supply stability predictions as evaluator input features.
- Freeze untouched external immunogenicity tests before any labeler/evaluator
  selection they could influence. No external-test-driven threshold or feature choice.
- Include matched random-positive removal and affinity-only controls. Affinity-conditioned
  stability is a separately predeclared secondary analysis, not an interchangeable arm.
- Use paired evaluations, multiple seeds, uncertainty intervals and specified metrics.

`scientific_hypothesis`: stability-based holding-out might improve labels, remove
valid positives, merely change sample size/allele composition, or capture affinity
confounding. Matched controls are needed to distinguish these mechanisms.
`candidate_recommendation`: review primary paired delta AUPRC for immunogenicity,
AUROC secondary; for continuous kinetic candidates consider hours MAE primary and
RMSE secondary. Metric choice, cross-dataset aggregation, seed count, dependence-aware
bootstrap/interval unit and multiple-comparison handling remain `decision_pending`.
Z3 status metrics assess **reported-zero status**, not confirmed biological negatives.
No architecture, thresholds, metrics or performance claim is adopted by this dossier.

## Provenance and usage uncertainties

| Source | Confirmed provenance / reuse | Verified terms and scope | Unresolved |
|---|---|---|---|
| DTU 2016 | Published experimental dataset; individual traces unverified | No verified dataset redistribution license in captured audits | Zero origin, replicate fits/limits, C67S purpose and permitted redistribution |
| SPEARMINT | Exact derived ordinary-DTU representation | Dataset/license scope unresolved | Upstream receptor version, preparation history, 181-residue entries and permission scope |
| Jappe | Publication-described Tm candidates; Source Data examples/precision variants are not independent additions | Article CC BY 4.0 statement with third-party exceptions | Artifact/underlying-MS resource scope, individual traces/context independence, full C359 population |
| Historical NetMHCstab | Prior study incorporated into later DTU; original table unavailable | Software-request restrictions were verified, not applied as a dataset license | Original measurements, overlap/independence and dataset terms |
| TLStab secondary | Reprocessed transformed scores; historical lineage unresolved | No verified dataset license in captured audit | Original export version/units/assay IDs and 5,509/6,298/6,297 discrepancy |

Source evidence comes from earlier audited documents and the versioned global
registry; no new license source is contacted and no legal determination is made.
Public download or missing terms do not establish permission. Raw scientific inputs
and generated registry/dossier reports remain outside Git.

## Exact Gate 0 decisions required

All entries are `decision_pending`; ChatGPT and user review must resolve them
before a separately authorized implementation:

1. **D1:** Z1/Z2/Z3 primary zero objective, reporting interpretation and sensitivity arms.
2. **D2:** C1/C2/C3 construct scope and molecular/assay evidence needed for inclusion.
3. **D3:** Kinetic-primary and/or separate thermal direction; retain units and C contexts.
4. **D4:** Split/generalization protocol, grouping, similarity definition and support rules.
5. **D5:** External immunogenicity freeze timing and binding-checkpoint exposure audit.
6. **D6:** Later positive holding-out criterion and matched random/affinity controls.
7. **D7:** Primary metrics, aggregation, seeds, paired uncertainty and selection rules.
8. **D8:** Source/checkpoint use and redistribution clarification.

Missing evidence includes per-row zero-generation/limit/rounding information,
construct sequences and purpose, raw measurement traces, study/donor/antigen tags,
full C359 membership, historical rows, checkpoint corpora and immunogenicity overlap.
Proposed sensitivities are Z1 versus Z2 (Z3 separate), ordinary versus construct-specific
scope, S1/S2/S3 generalization, per-allele/zero-stratum reporting, matched removal,
affinity-only/conditioned controls and multi-seed paired estimates. None is run.

## Offline reproduction and canonical run

```sh
PYTHONPATH=src python3 -B -m stability_label_curation gate0 inspect --json
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
```

`--registry`, `--aliases` and repeatable `--input INPUT_ID=PATH` support explicit
local derived-file overrides. `--config` supplies their pinned identities and
analysis conventions for synthetic fixtures. Default inspection is read-only,
with no raw observation regeneration, downloads or source modification.

After commit, create one run through supported `runs create --kind scientific_preflight
--run-id task-1_9-gate0-scientific-preflight --config configs/gate0_preflight.json`
with repeatable `--input` for the six derived files. Then use `gate0 inspect
--reports-dir` with that run's `reports/` directory. The destination must be an
existing project run whose manifest records every input/hash. Paths/symlinks and
existing outputs are protected by existing nonreplacing publication helpers.

Reports cover coverage, zero/C67S alternatives, modality overlap, leakage,
decision matrix, inherited source evidence, checksums and execution verification.
They contain aggregates and overlap evidence, **no training-ready rows or eligibility
masks**. JSON is deterministic with fixed conventions; the run manifest records
actual derived inputs and the parent link. No direct raw-source relationships
are invented. Task 1.9 ends at review; Task 2.0 is not begun.
