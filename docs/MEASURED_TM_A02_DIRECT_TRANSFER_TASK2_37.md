# Task 2.37 — A*02:01 measured-Tm direct transfer into BigMHC

Completed on **Z790 WSL2 / RTX 4090, 2026-10-24 JST**. Branch
`task/2.37-a02-measured-tm-direct-transfer`, directly from approved Task 2.35
`f8e972ef340dab4d697c66debb7c61cb3dc19183`.

**The prespecified A*02:01 primary AP experiment did not demonstrate benefit
from genuine measured-Tm pairing.** T is below P and A in every fixed seed.
Mean seed-paired AP(T−P) = **−0.009394353685352826**; exploratory component-bootstrap
95% interval **[−0.05994542382145207, 0.004954235358008188]**. T−A =
**−0.010059019677749385**, T−D = **0.0021237181479812975**, also with AP intervals
spanning zero. Mean T AP **0.059232646304069846** versus A **0.06929166598181923**,
P **0.06862699998942266**, D **0.05710892815608854**.

**Recommendation: NO-GO for promoting this exact procedure as improved zero-shot
IM ranking or advancing a confirmatory AP-superiority claim on its strength.**
Primary AUROC is higher descriptively, but cannot replace failed primary AP.
Secondary full-cohort T AP gains are small, uncertain and below binary adaptation
D. The broader measured-thermostability hypothesis is not disproven. No further
training, coefficient, seed, epoch, architecture or benchmark search followed.

This is a **new, explicitly authorized A*02:01 exploratory study**, not a rescue
or continuation of the abandoned two-HLA primary. Task 2.35's committed two-HLA
NO-GO and the researcher's Task 2.36 NO-GO remain unchanged. No single-HLA primary
was silently substituted in those tasks. No Mac transfer or CapsNet artifact
access occurred.

## Prospective protocol, loss refinement and execution seal

The [protocol](MEASURED_TM_A02_DIRECT_TRANSFER_TASK2_37_PROTOCOL.md),
[configuration](../configs/measured_tm_a02_direct_transfer_task2_37.json),
[training implementation](../src/stability_label_curation/measured_tm_direct_transfer.py),
[evaluation implementation](../src/stability_label_curation/measured_tm_direct_transfer_evaluation.py)
and initial 16 focused tests were committed before updates/scoring as
**`b8207a07f9dc0ef5a5e3e11d9b26981c780d2ce4`**. Actual input/permutation/order hashes, checkpoint identity,
GPU preflight and test receipts were then pinned by the committed
[readiness receipt](../configs/measured_tm_a02_direct_transfer_task2_37.ready.json)
at **`c340208f5ddb899deb563e2d2e522261c0238a67`**, before any scientific optimizer step.

The class-balanced loss is the explicit researcher-authorized prospective
refinement of Task 2.35's provisional unweighted objective. Measured source rows
weight **16**, selected decoys weight **1**, including quantitative positive
rows regardless of their continuous target. Per native batch:

`loss = sum_i(w_i * BCEWithLogits(logit_i, target_i)) / sum_i(w_i)`

There is no batch-size denominator or alternate weight search. Each full pass
contains **11360 measured-row weight mass and11360 decoy weight mass**, total
**22720**. Every arm uses identical source-class weights, negative identities,
ordered batches and optimization budget. A negative-only batch is retained.
Known training imbalance motivated this rule, not a new IM result.

The sources/outcomes were previously examined in earlier tasks. This is not an
untouched confirmatory blind test. IM labels did not train, calibrate, select,
stop or tune a model. No new IM score or outcome revised the researcher-prespecified source,
peptide/HLA population, decoys, epochs or seeds. The A0201 focus was explicitly
authorized after known earlier class-support findings; it is not a blinded
cohort-selection claim. All nine final checkpoints and all 20 score
files were fixed before the new metrics. Scores are not ensembled.

## Authenticated A and fixed training data

Common starting model **A: Task 2.23 complete EL epoch10**, not any final IM or
W/S/P checkpoint. Canonical filename→SHA256 map digest:
**`d8e3d7d3ac5d08d7f420e00b8032fa875b8b6fec1cd9da6b36d35bca0bec04d1`**.
All 36 tensor files and expected native tensor states authenticate. Strict parent
loads use `lineage=None`; no IM overlay, auxiliary head or historical CapsNet
model is loaded. A is never adapted or retrained. Original EL source architecture,
414-feature HLA encodings and peptide preprocessing are unchanged.

Use exactly Task 2.35's preferred A0201 panel: Jappe et al. 2020
DOI `10.1038/s41467-020-20166-4`, original Supplementary Data3,
`41467_2020_20166_MOESM6_ESM.xlsx`, SHA256
`c15cdee1454aaeafc73574ebd456919e88a15acdc3d3e58cfabb0e44df6361aa`.
Task 2.35 output manifest SHA256
`e3f6702a2900393372dc5ba99c031bcba44130dbbc02a0c2679ce9113f742e73`
authenticates the consumed source/eligibility/decoy records. No public data
rediscovery or new download was performed.

| Training group | Original eligible source | Final observations | Targets | Sample weight |
| --- | ---: | ---: | --- | ---: |
| Measured A*02:01 ligands | 711 canonical9-mers | 710 | D:1; P:permuted y; T:authentic y | 16 |
| Authenticated EL-fitting decoys | 48267 eligible A0201 identities | 11360 | 0 in D/P/T; no measured Tm | 1 |
| Total fixed adaptation rows | — | 12070 | Native source identities unchanged | — |

The Task 2.35 fixed hash-ordered selected negatives were fully eligible: **zero
replacements**. Their original Task 2.23 source IDs, row hashes, sequences, exact
HLA and negative labels were rejoined to the authoritative split. None conflicts
with published measured-Tm ligand sequences or any authenticated positive EL
sequence. They are constructed EL negatives, not measurements of unstable pMHC.
No decoy receives a Celsius Tm. No synthetic thermostability label is invented.

Target **y=.5+(Tm_C−37)/72** remains authentic, unmodified and finite within [0,1].
Original Celsius and Decimal target text remain in the manifest. A0201 range
**40.10564–65.43171°C**, y **0.5431338888888889–0.8948848611111111**.
All **four unresolved repeated-minimum A0201 flags** are retained; no clipping,
imputation or censoring reinterpretation. Tm is thermal melt midpoint, not kinetic
half-life in hours. No Teacher is trained, scored or recalibrated.

Final train identities were rechecked against **both whole frozen IM sources**,
not just the primary HLA subset: **zero exact peptide–HLA hits, zero exact peptide
hits, zero distance<=2 sequence neighbors**, with exact minimum distance3 for
each source union. Witnesses preserve source IDs and allele-agnostic equal-length
Hamming comparisons. No split, evaluation row, source label or eligibility was
changed. Only canonical9-mers are compared; no artificial mismatched-length
Hamming distance. Baseline's prior fitting/selection exposure remains historical
and is not retroactively erased; neoepitope remains an exact-novel rather than a
full-baseline Hamming hard split.

## Matched three-seed adaptation and checkpoint identities

Exactly **[123,456,789]**, D/P/T once each, **nine fits**,20 passes each.
Within each seed, every D/P/T fit reloads identical complete A state, uses the
same full saved sample order and persistent optimizer. Ordering local RNG is
`Random(seed)`; P's independent local RNG is `Random(2370000+seed)`.
Quantitative targets are permuted only across the 710 measured rows; exact decimal
and FP32 target multisets are preserved; all decoys remain0. Target values change
for709/710,710/710,709/710 measured rows for seeds 123/456/789 respectively.
No derangement or alternative permutation was searched.

AdamW **lr 0.001, weight_decay 0.01, betas(.9,.999), eps 1e-8**, amsgradFalse,
foreachFalse/fusedFalse; batch 64, final partial batch38,20 complete passes,
**189 updates/pass,3780/fit,34020 total**. No skipped all-negative batch, scheduler,
AMP, TF32, early stopping, validation selection or alternative backbone unfreezing.
Final pass 20 is used unconditionally. Each fit exposes710 measured and11360 decoy
rows in every pass; across all nine fits,2172600 row exposures are optimization
exposures, not additional independent data.

Only **`condenser.out.weight` (414 values) and `.bias` (1)** are trainable and
change. All other 34 native tensor states remain equal to A. Whole model stays in
eval mode throughout adaptation, disabling dropout/stochastic updates; running
buffers are frozen. The native HLA-masked output operation is used directly,
not the historical four-parameter IM transfer list. Every fit changes all 415
allowed scalar values, with no architecture or new head. AdamW step-count checks
report3780 for each of the two trainable tensors. Original D_123 step assertions
passed before its checkpoint validation interruption, as documented below.

Only **encoded input tensors** are reused after bitwise native encoding/forward
checks on64,64 and38 training-row probes. **No learned feature cache** is used;
the native frozen backbone executes on every adaptation batch. The original
source readout uses output weights directly before its HLA mask; an ordinary
out-module forward hook is not used. No IM label is present in training inputs
or an optimizer. Full training losses, weighted numerators/denominators, exposures,
batch digests and frozen-gradient checks are saved for all 180 passes.

Adapted checkpoints contain exactly the two output tensors, an explicit complete-A
parent binding and the resulting complete36-tensor state digest. The unmodified
349MB backbone is not duplicated nine times. The explicit reconstruction loader
strictly loads A, substitutes only those two tensors, checks all 36 states and
validates native training-mode forward. This is not an IM transfer overlay.


| Fit | Saved output-tensor file SHA256 | Complete36-tensor state-map SHA256 | Final pass weighted BCE |
| --- | --- | --- | --- |
| D_123 | `cc59e2249b850a127ec0a4a2c07d7387ed65125710ad19d393fa37b2348bb4a3` | `cd6c18cb5fe71ae68e5685d50149f0819fc39d38e92f94c026b043c6609a4d63` | 0.09426583349704742 |
| D_456 | `d092cb72dd8eff51efee0ae12c0150e7b524897211d5c6699e1bf921a302b58b` | `c65118aa464c41edbc6a6764e2e5a40381faf94831d32a4e15a99a6ef041e2dc` | 0.09371292591094971 |
| D_789 | `3cdcbc94716ea644d8638ae0bbe79e274cc40d33fabf6f58a707f111d4f7b32c` | `d696910a3519e55ed8af33aad47ddf873033306fdecf25976b148a1adaa936f3` | 0.09394142031669617 |
| P_123 | `7985777f60d426db4f948581a1367d113dfdcb344bd1a3b6d2b38fd67463fe86` | `142e7887a657c743064667da46751fc99eb0c0ae082e1dabb76a72f854a04074` | 0.33666205406188965 |
| P_456 | `2e54533e68e0b67db732d1ceba91cd496e17a64ca17847a2ab10f4d8b92c57b8` | `be55f6a51b20f75ea592c83396762b9527c32583c7ebdc248369e867f36c0379` | 0.33428698778152466 |
| P_789 | `1ac04f07e607a2bdc17a5bf02f269f3c69bec1b3db1a4d3007215fffc7c0b69a` | `a07b518203ae68efe9e5acd68f0d6ea3c09c9dc1eb95268de90332c04e3bb0bd` | 0.33592551946640015 |
| T_123 | `d2e34f140325cd2cacd0cf8c23bdaf69386bd2f515e1e98b9fc1d1425fddb638` | `6fcda414745ca364797d26d9206adcf359d48fae62c0215d3b174a75177870a3` | 0.3256418704986572 |
| T_456 | `a99dd9a3a7deb55b845d106660f500e2ac37c25430ecf8ce8f70f52465eb0fbf` | `db8a2141ee6f29a0add3684d777fd8580249aa957733e0591d0b72fee7fe537c` | 0.3255113363265991 |
| T_789 | `ea4194c2329a0a070b40de030f645e61a609514b59773eaa900688120b3ac328` | `4be7239381b93546471672630b26fc257e09d92f8d8389a6c00189c6b721abae` | 0.3258480727672577 |

The two digest columns have different definitions: serialized two-tensor bytes
versus canonical parameter-name→raw-tensor-hash map. The parent A digest above
is a native filename→file-hash map; these are not interchangeable hash types.

## Documented technical interruption and completed-fit preservation

The first D seed123 finished20 passes/3780 updates, saved its head and20 histories,
then stopped at the bitwise reload assertion. **Tensor values were intact**;
the freshly loaded probe model had all parameters requiring gradients, while
the trained model had only its output tensors requiring gradients. Despite
eval/no-grad, native CUDA execution produced up to **1.430511474609375e-06**
logit difference on16 training observations. Aligning the gradient metadata made
the training-mode forward **bitwise identical, maximum difference0**.

The [technical note](MEASURED_TM_TASK2_37_RELOAD_TECHNICAL_NOTE.md) and narrow
repair were committed as **`7196f2ad561d554538f46377cfbfedcb17dfa67d`**, before any new IM scoring or
performance output. The correction changes only reload-probe metadata and
bookkeeping for resuming the remaining fits. **D_123 is not retrained, discarded
or replaced.** Its saved checkpoint bytes, all 20 histories and original failed
start/log/telemetry remain authenticated. The remaining eight fits completed
with live-versus-reloaded bitwise training probes under matching flags.

D_123's exact fit-only elapsed time and original live probe vector were lost
with the failed process and are explicitly unavailable. Its completion receipt
is reconstructed from the saved two tensors, authenticated A and all 20 pass
records; two independent training-mode reconstructions match bitwise. Optimizer
default metadata is marked reconstructed from unchanged settings; the original
step-count assertions passed before saving. No optimizer moments were needed to
continue another fit, and no original fit was extended.

A targeted AST/byte equivalence receipt confirms **prepare, target assignment,
ordering, freeze policy, loss, the entire training epoch/update loop, preflight,
inference, configuration, protocol and evaluation implementation are unchanged**
from the pretraining commit. IM scoring retains the original committed native
eval/no-grad route, matching the saved A route; inference gradients do not cause
updates. No hyperparameter, target, cohort, orientation or scientific method was
changed. New results were not available for choosing a repair. This is not an
unreported repeated experiment.

## Frozen evaluation and score interpretation

All 20 source/model score files were fixed at
**2026-10-24T14:12:55.962050+00:00** before new performance
comparisons. A's two source files are byte-identical copies from Task 2.32,
after full checkpoint/source/runtime/input/order/synthetic compatibility checks.
No A benchmark forward was repeated. Nine adapted checkpoints each score both
sources once, preserving raw logits and native FP32 sigmoid scores: **80550
aligned finite logit/score pairs** in total, including reused A. All model tensor
states remain unchanged through scoring.

All metrics use larger native sigmoid scores as stronger positive/adapted-target
responses, with one prespecified orientation. D/P/T scores are **adapted ligand/
thermostability-derived discrimination scores**, not calibrated EL/IM
probabilities, measured Tm°C or surface lifetimes. New prediction columns are
`raw_logit`/`score`; the reused A files retain their historical native field names.
No calibration, HLA normalization, logit-based alternative performance analysis,
ensemble or outcome-driven sign inversion was introduced. Inference uses batch 16,
original input encoding, FP32, eval/no-grad and constant-zero schema placeholders.
Actual experimental IM labels are joined only by frozen source IDs at evaluation.

| Prespecified population | N | Positive | Negative | Unique peptides | HLA count | Dependence units |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Primary IMPROVE A0201 | 616 | 21 | 595 | 610 | 1 | 16 patient/peptide components |
| Secondary full IMPROVE>=3 | 7788 | 227 | 7561 | 6576 | 36 | 38 patient/peptide components |
| Descriptive B0702 IMPROVE | 555 | 8 | 547 | 535 | 1 | 10 original components |
| Descriptive remaining IMPROVE HLAs | 6617 | 198 | 6419 | 5673 | 34 | 38 original components |
| Additional neoepitope primary | 267 | 57 | 210 | 265 | 46 | 265 peptide clusters |
| Descriptive neoepitope A0201 | 46 | 5 | 41 | 46 | 1 | Unknown patient/assay links |

Original source counts/order, duplicates, peptide/HLA mappings and patient/study
associations are preserved. IMPROVE patient-specific recognition observations
are not deduplicated. Global original components are retained even in subsets,
not recomputed to increase apparent independence. A0201 has26 patients across
three studies; full IMPROVE70 patients/three studies. These sources have known
prior model-evaluation exposure. Neoepitope source/assay linkage is incomplete,
and its A0201 subgroup has only 5 positives. No source/HLA becomes primary after
seeing outcomes; optional neoepitope analysis was included before training.

Primary non-interpolated AP groups exactly tied scores at a single threshold.
AUROC gives ties half credit. Top-K ties use peptide,HLA,study DOI,patient,source-ID
in that order after descending score. Per-seed metrics are paired on the same
original rows. Descriptive seed means average metrics, **not prediction vectors**;
primary statistic averages the three seed-paired AP differences. Seeds are not
independent biological replicates. Serialized mean values retain normal binary
floating-point roundoff, including repeated-A averages at approximately1e-17;
A's underlying score vector and per-seed metrics are exactly unchanged.

## Primary A*02:01 results: N616,21 positive/595 negative


| Seed | A AP | D AP | P AP | T AP | T−P | T−A | T−D |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 123 | 0.06929166598181923 | 0.06079162784881577 | 0.07250277100310618 | 0.06268331283407365 | -0.009819458169032527 | -0.006608353147745577 | 0.0018916849852578799 |
| 456 | 0.06929166598181923 | 0.057170806055201084 | 0.06156737077237559 | 0.05777765817801998 | -0.003789712594355607 | -0.011514007803799242 | 0.0006068521228188989 |
| 789 | 0.06929166598181923 | 0.05336435056424878 | 0.07181085819278624 | 0.05723696790011589 | -0.014573890292670345 | -0.012054698081703334 | 0.0038726173358671137 |
| Descriptive mean | 0.06929166598181923 | 0.05710892815608854 | 0.06862699998942266 | 0.059232646304069846 | -0.009394353685352826 | -0.010059019677749385 | 0.0021237181479812975 |

| Metric, seed mean | A | D | P | T | Mean paired T−P | T−A | T−D |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AP | 0.06929166598181923 | 0.05710892815608854 | 0.06862699998942266 | 0.059232646304069846 | -0.009394353685352826 | -0.010059019677749385 | 0.0021237181479812975 |
| AUROC | 0.5430172068827531 | 0.536374549819928 | 0.5576097105508869 | 0.5799119647859143 | 0.02230225423502737 | 0.03689475790316125 | 0.0435374149659864 |
| precision_at_10 | 0.20000000000000004 | 0.10000000000000002 | 0.13333333333333333 | 0.13333333333333333 | 0.0 | -0.06666666666666667 | 0.03333333333333333 |
| precision_at_20 | 0.10000000000000002 | 0.10000000000000002 | 0.10000000000000002 | 0.10000000000000002 | 0.0 | 0.0 | 0.0 |
| prevalence | 0.03409090909090909 | 0.03409090909090909 | 0.03409090909090909 | 0.03409090909090909 | 0.0 | 0.0 | 0.0 |
| AP_minus_prevalence | 0.03520075689091014 | 0.023018019065179456 | 0.03453609089851358 | 0.025141737213160754 | -0.009394353685352826 | -0.010059019677749385 | 0.0021237181479812975 |
| AP_over_prevalence | 2.0325555354666975 | 1.6751952259119307 | 2.0130586663563985 | 1.7374909582527156 | -0.2755677081036829 | -0.2950645772139821 | 0.06229573234078467 |

T AP is below both P and A **in all three seeds**; mean T AP is slightly above D,
but this is not a stability-specific advantage because P is better. T has higher
AUROC than A/P/D on this primary population; those secondary rank-wide findings
cannot replace the failed primary AP or the high-ranking candidate objective.
A identifies2/10 and2/20 recognized observations. T identifies2/10,1/10,1/10
across seeds and2/20 in each. No optimized cutoff or favorable seed is selected.

## Paired uncertainty and limitations

Each of 10000 fixed bootstrap draws samples the original number of sorted
components with replacement, retaining original observations with multiplicity
and pairing **all ten conditions / all three seeds**. Per-draw contrasts average
all three seed-paired differences; an undefined constituent makes the contrast
undefined, never a reduced-seed average.95% percentile intervals use linear
interpolation at(n−1)q, q=.025/.975. No row bootstrap, seed bootstrap, p-value
search or interval-driven selection. All component multiplicities and contrast
draws are retained in compressed evidence.

Primary uses 16 original patient/peptide components, Random(237001); seven contain
positives and the largest has 262/616 observations. **One classless draw is invalid
for AP/AUROC**, leaving 9999 usable; it is not replaced. Fewer than 20 units flags
primary intervals as **unreliable exploratory uncertainty**, not population-level
biological significance.21 positive peptide observations are not21 independent
biological systems. Full IMPROVE uses 38 components / 30 positive-bearing units,
Random(262742),10000 usable AP/AUROC draws. Neoepitope uses 265 peptide clusters,
Random(24242),10000 usable draws; unknown patient/assay dependence persists.
Shared peptides connect all three IMPROVE studies into one study/peptide unit:
study-level interval is **undefined**, zero draws, not a fabricated study bootstrap.


### IMPROVE_A02: seed-averaged paired95% intervals

| Endpoint | Contrast | Mean seed-paired difference | Lower95 | Upper95 | Usable / invalid draws |
| --- | --- | --- | --- | --- | --- |
| AP | T-P | -0.009394353685352826 | -0.05994542382145207 | 0.004954235358008188 | 9999 / 1 |
| AP | T-A | -0.010059019677749385 | -0.023490078983147145 | 0.007755221058118085 | 9999 / 1 |
| AP | T-D | 0.0021237181479812975 | -0.03421506992216752 | 0.013365360969951405 | 9999 / 1 |
| AUROC | T-P | 0.02230225423502737 | 0.00034403288449627253 | 0.03703866432337433 | 9999 / 1 |
| AUROC | T-A | 0.03689475790316125 | 0.010966515952011683 | 0.09100295854356179 | 9999 / 1 |
| AUROC | T-D | 0.0435374149659864 | 0.014611882135533124 | 0.08437855892738319 | 9999 / 1 |
| precision_at_10 | T-P | 0.0 | 0.0 | 0.06666666666666667 | 9999 / 1 |
| precision_at_10 | T-A | -0.06666666666666667 | -0.3 | 0.10000000000000002 | 9999 / 1 |
| precision_at_10 | T-D | 0.03333333333333333 | -0.03333333333333333 | 0.06666666666666667 | 9999 / 1 |
| precision_at_20 | T-P | 0.0 | -0.03333333333333333 | 0.016666666666666673 | 9999 / 1 |
| precision_at_20 | T-A | 0.0 | -0.10000000000000002 | 0.0 | 9999 / 1 |
| precision_at_20 | T-D | 0.0 | 0.0 | 0.04999999999999999 | 9999 / 1 |
| AP_over_prevalence | T-P | -0.2755677081036829 | -1.662129999862652 | 0.16613917112573012 | 9999 / 1 |
| AP_over_prevalence | T-A | -0.2950645772139821 | -0.7372443405015207 | 0.29090385130214763 | 9999 / 1 |
| AP_over_prevalence | T-D | 0.06229573234078467 | -0.9214637661167349 | 0.3128240343238911 | 9999 / 1 |

### IMPROVE_full: seed-averaged paired95% intervals

| Endpoint | Contrast | Mean seed-paired difference | Lower95 | Upper95 | Usable / invalid draws |
| --- | --- | --- | --- | --- | --- |
| AP | T-P | 0.0006186660779594946 | -3.495198961930954e-05 | 0.0019012212870792976 | 10000 / 0 |
| AP | T-A | 0.0004985639229080167 | -0.0016419549629660907 | 0.0018100708815813294 | 10000 / 0 |
| AP | T-D | -0.0006606415677715577 | -0.007758657899553017 | 0.0018960643262968411 | 10000 / 0 |
| AUROC | T-P | 0.0020063930351302086 | -0.0006969628331093145 | 0.00406617159812112 | 10000 / 0 |
| AUROC | T-A | 0.002600678456434894 | -0.0074367021989895175 | 0.009085521273812012 | 10000 / 0 |
| AUROC | T-D | 0.0009452245573495407 | -0.014864340293045961 | 0.010971667611244684 | 10000 / 0 |
| precision_at_10 | T-P | 0.0 | -0.03333333333333333 | 0.0 | 10000 / 0 |
| precision_at_10 | T-A | -0.10000000000000002 | -0.16666666666666666 | 0.0 | 10000 / 0 |
| precision_at_10 | T-D | 0.0 | -0.19999999999999998 | 0.10000000000000002 | 10000 / 0 |
| precision_at_20 | T-P | 0.0 | -0.016666666666666666 | 0.05000000000000001 | 10000 / 0 |
| precision_at_20 | T-A | 0.0 | -0.10000000000000002 | 0.0 | 10000 / 0 |
| precision_at_20 | T-D | 0.0 | -0.18333333333333335 | 0.05000000000000001 | 10000 / 0 |
| AP_over_prevalence | T-P | 0.02122542473633726 | -0.0011130331406727732 | 0.07086752523331319 | 10000 / 0 |
| AP_over_prevalence | T-A | 0.017104915557743034 | -0.059742760752512204 | 0.06186165893940765 | 10000 / 0 |
| AP_over_prevalence | T-D | -0.022665535373589767 | -0.2634849602232908 | 0.06657991277312195 | 10000 / 0 |

### neoepitope: seed-averaged paired95% intervals

| Endpoint | Contrast | Mean seed-paired difference | Lower95 | Upper95 | Usable / invalid draws |
| --- | --- | --- | --- | --- | --- |
| AP | T-P | -0.004488920306144006 | -0.0125830992978035 | 0.0012306629035958917 | 10000 / 0 |
| AP | T-A | 0.0014783724975854045 | -0.018112148541915406 | 0.028873135699310465 | 10000 / 0 |
| AP | T-D | 0.02976178742616133 | 0.005458756976592252 | 0.06773101176698156 | 10000 / 0 |
| AUROC | T-P | -0.0022834864940128132 | -0.009540130053213093 | 0.0045805957644464365 | 10000 / 0 |
| AUROC | T-A | 0.003230297967140028 | -0.015067338211955522 | 0.021526544589160385 | 10000 / 0 |
| AUROC | T-D | 0.01821219715956557 | -0.009390923167581942 | 0.047020262773726486 | 10000 / 0 |
| precision_at_10 | T-P | 0.0 | -0.10000000000000002 | 0.033333333333333326 | 10000 / 0 |
| precision_at_10 | T-A | -0.09999999999999998 | -0.3 | 0.10000000000000003 | 10000 / 0 |
| precision_at_10 | T-D | 0.06666666666666667 | -0.03333333333333333 | 0.39999999999999997 | 10000 / 0 |
| precision_at_20 | T-P | -0.050000000000000044 | -0.10000000000000003 | 0.06666666666666667 | 10000 / 0 |
| precision_at_20 | T-A | 0.04999999999999999 | 0.0 | 0.25000000000000006 | 10000 / 0 |
| precision_at_20 | T-D | 0.14999999999999997 | 0.0 | 0.3333333333333333 | 10000 / 0 |
| AP_over_prevalence | T-P | -0.02102704774983244 | -0.05994779187268743 | 0.005850733902246193 | 10000 / 0 |
| AP_over_prevalence | T-A | 0.006925008015005174 | -0.08987104708263004 | 0.1391741704485545 | 10000 / 0 |
| AP_over_prevalence | T-D | 0.13941047794359776 | 0.026219973985947595 | 0.3256329385725293 | 10000 / 0 |

All three primary **AP** intervals span zero. Primary AUROC contrast intervals
are positive, but remain secondary and flagged unreliable at 16 components;
we do not promote AUROC to the scientific primary or claim confirmatory
significance. The full IMPROVE T−P/T−A AP intervals span zero. Neoepitope T−D AP's
interval is positive, but T is below P there, so it does not isolate useful
sequence–Tm pairing. All metrics/intervals, including prevalence and AP minus
prevalence, are preserved; undefined values remain undefined.

## Secondary full IMPROVE and negative transfer


| Arm | Seed123 AP | Seed456 AP | Seed789 AP | Mean AP | Mean AUROC | Mean Precision@10 | Mean Precision@20 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 0.03638362130144917 | 0.03638362130144917 | 0.03638362130144917 | 0.03638362130144917 | 0.5024228783573484 | 0.10000000000000002 | 0.05000000000000001 |
| D | 0.037513515749184115 | 0.03753943090642946 | 0.03757553372077266 | 0.037542826792128746 | 0.5040783322564338 | 0.0 | 0.05000000000000001 |
| P | 0.03611978160839398 | 0.0361895776563055 | 0.0364811981744936 | 0.036263519146397694 | 0.5030171637786531 | 0.0 | 0.05000000000000001 |
| T | 0.036942285045963454 | 0.03672697165358478 | 0.03697729897352332 | 0.036882185224357183 | 0.5050235568137834 | 0.0 | 0.05000000000000001 |

Mean T−A AP **0.0004985639229080167**, T−P **0.0006186660779594946**, T−D
**−0.0006606415677715577**. Thus the small secondary pooled gain is not better
than binary ligand/decoy adaptation. Mean AUROC A/D/P/T is
0.5024228783573484 /0.5040783322564338 /0.5030171637786531 /0.5050235568137834;
paired intervals do not establish a directional full-cohort gain. Adapted arms
find 0/10 primary full-cohort positives in every seed, versus A 1/10; all find 1/20.

| Descriptive IMPROVE group | A AP | Mean D AP | Mean P AP | Mean T AP | T−A AP | T−P AP | T−D AP |
| --- | --- | --- | --- | --- | --- | --- | --- |

| IMPROVE_A02 | 0.06929166598181923 | 0.05710892815608854 | 0.06862699998942266 | 0.059232646304069846 | -0.010059019677749385 | -0.009394353685352826 | 0.0021237181479812975 |
| IMPROVE_B07 | 0.016544720423775784 | 0.018130188417390294 | 0.015669119459873048 | 0.015764431685986468 | -0.0007802887377893175 | 9.531222611342098e-05 | -0.002365756731403828 |
| IMPROVE_other | 0.03811075507843292 | 0.039947597006886985 | 0.03866698751246586 | 0.03908006839506148 | 0.0009693133166285584 | 0.0004130808825956224 | -0.000867528611825504 |
| IMPROVE_full | 0.03638362130144917 | 0.037542826792128746 | 0.036263519146397694 | 0.036882185224357183 | 0.0004985639229080167 | 0.0006186660779594946 | -0.0006606415677715577 |

**Negative transfer is visible:** A0201 T−A AP is negative in every seed, as is
unsupported B0702 T−A AP; B0702 mean AUROC also falls from 0.5082266910420475 to
0.5013711151736745. Remaining34-HLA pooled T−A AP is weakly positive, but D is
better, and this does not demonstrate learned thermostability at untrained HLAs.
The head coefficients/bias are shared through HLA encodings; AdamW decay also
changes allowed output coefficients without allele-specific data gradients.
Frozen backbone does not guarantee unchanged other-HLA rankings.

Per-HLA descriptive adequacy was fixed at N>=20,positive>=5,negative>=5. Among
20 evaluable IMPROVE alleles, mean T−A AP is positive in 10 and negative in 10;
T−P positive in 15/negative in 5; T−D positive in 7/negative in 13. Those descriptive
sign counts are not independent replication units, and no favorable HLA is
promoted. All evaluable alleles are shown; sparse-allele outputs remain explicit
nulls in the artifact, without excluding their observations from pooled metrics.


| HLA | N | Positive | A AP | Mean D AP | Mean P AP | Mean T AP | Mean T−A AP | Mean T−P AP |
| --- | ---: | ---: | --- | --- | --- | --- | --- | --- |
| HLA-A*01:01 | 251 | 14 | 0.24873022826034774 | 0.25018938155299697 | 0.1960532370038417 | 0.21618906946141345 | -0.0325411587989343 | 0.020135832457571733 |
| HLA-A*02:01 | 616 | 21 | 0.06929166598181923 | 0.05710892815608854 | 0.06862699998942266 | 0.059232646304069846 | -0.010059019677749385 | -0.009394353685352826 |
| HLA-A*03:01 | 474 | 6 | 0.04540146865059447 | 0.03592373638499259 | 0.0967333510623925 | 0.06353198099427108 | 0.018130512343676606 | -0.03320137006812143 |
| HLA-A*11:01 | 153 | 6 | 0.2583597123495256 | 0.1721577339199828 | 0.2373035342742994 | 0.23864560493941353 | -0.019714107410112054 | 0.0013420706651141405 |
| HLA-A*24:02 | 379 | 12 | 0.057683133530915774 | 0.06643340780351772 | 0.06458458585868879 | 0.06462817013268814 | 0.006945036601772379 | 4.3584273999359526e-05 |
| HLA-A*26:01 | 243 | 6 | 0.0414011081148827 | 0.057434170076295865 | 0.04423757356821795 | 0.044006715359519694 | 0.002605607244636994 | -0.00023085820869825127 |
| HLA-A*30:01 | 163 | 6 | 0.1826370273189117 | 0.14591400900871773 | 0.19796777384429165 | 0.20169559412288685 | 0.019058566803975125 | 0.003727820278595186 |
| HLA-A*32:01 | 239 | 6 | 0.032907430224428096 | 0.043149542780570205 | 0.03133246158927629 | 0.03256208132086703 | -0.0003453489035610639 | 0.001229619731590736 |
| HLA-B*07:02 | 555 | 8 | 0.016544720423775784 | 0.018130188417390294 | 0.015669119459873048 | 0.015764431685986468 | -0.0007802887377893175 | 9.531222611342098e-05 |
| HLA-B*08:01 | 402 | 7 | 0.129219942676558 | 0.12450315030693038 | 0.10128843737264397 | 0.12529051966479957 | -0.003929423011758433 | 0.024002082292155603 |
| HLA-B*27:05 | 119 | 5 | 0.09002720705507083 | 0.15355600629074548 | 0.09719466293074765 | 0.10189826004208313 | 0.011871052987012307 | 0.004703597111335491 |
| HLA-B*35:01 | 225 | 8 | 0.03578027731268153 | 0.03399332811815968 | 0.03482671298974089 | 0.03500928514320781 | -0.0007709921694737271 | 0.00018257215346691633 |
| HLA-B*35:03 | 91 | 6 | 0.10937077575402654 | 0.11428882260537676 | 0.10904428172745308 | 0.11203588684967847 | 0.0026651110956519286 | 0.002991605122225391 |
| HLA-B*38:01 | 390 | 10 | 0.05421426664004988 | 0.054956244846459425 | 0.05378002366556322 | 0.05453463197701728 | 0.00032036533696740605 | 0.0007546083114540631 |
| HLA-B*40:01 | 276 | 13 | 0.052013671370497304 | 0.053138702873154316 | 0.04633794286433484 | 0.04745686018800228 | -0.004556811182495016 | 0.0011189173236674417 |
| HLA-C*03:04 | 288 | 10 | 0.0883740597996097 | 0.12799093828328442 | 0.08143092794532715 | 0.07733195347513026 | -0.011042106324479448 | -0.004098974470196896 |
| HLA-C*04:01 | 389 | 7 | 0.053136974531209503 | 0.05796418978671671 | 0.06909419768412438 | 0.06987543607880237 | 0.01673846154759286 | 0.0007812383946780022 |
| HLA-C*06:02 | 225 | 25 | 0.13695268426453108 | 0.13789468089176063 | 0.13411613297306194 | 0.13460155469864232 | -0.00235112956588876 | 0.0004854217255803687 |
| HLA-C*07:01 | 556 | 15 | 0.05378140791449567 | 0.0666041287628197 | 0.05382292475511504 | 0.05393413461447552 | 0.00015272669997985536 | 0.0001112098593604773 |
| HLA-C*07:02 | 275 | 14 | 0.05514664529240518 | 0.05660962939265655 | 0.056291225961230464 | 0.05565892669184486 | 0.0005122813994396814 | -0.0006322992693856047 |

Per-seed AP/AUROC and all per-HLA contrasts are retained in the machine-readable
results. B0702's8 positives remain inadequate for the abandoned two-HLA primary;
reporting descriptive metrics here does not reverse that NO-GO.

## Prospectively included neoepitope descriptions


### neoepitope: N267,57 positive/210 negative

| Arm | Seed123 AP | Seed456 AP | Seed789 AP | Mean AP | Mean AUROC | Mean Precision@10 | Mean Precision@20 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 0.2564378062905638 | 0.2564378062905638 | 0.2564378062905638 | 0.2564378062905638 | 0.5375104427736007 | 0.3 | 0.3 |
| D | 0.22565625151472185 | 0.2283082657392799 | 0.23049865683196183 | 0.22815439136198787 | 0.5225285435811752 | 0.13333333333333333 | 0.20000000000000004 |
| P | 0.26461704729502833 | 0.26124357659675057 | 0.2613546733911007 | 0.2624050990942932 | 0.5430242272347535 | 0.20000000000000004 | 0.4000000000000001 |
| T | 0.2576829815233609 | 0.2590199852706047 | 0.25704556957048197 | 0.2579161787881492 | 0.5407407407407407 | 0.20000000000000004 | 0.3499999999999999 |

### neoepitope_A02: N46,5 positive/41 negative

| Arm | Seed123 AP | Seed456 AP | Seed789 AP | Mean AP | Mean AUROC | Mean Precision@10 | Mean Precision@20 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| A | 0.09528679653679653 | 0.09528679653679653 | 0.09528679653679653 | 0.09528679653679654 | 0.3463414634146342 | 0.0 | 0.05000000000000001 |
| D | 0.09533411033411035 | 0.097000777000777 | 0.09842934842934842 | 0.09692141192141192 | 0.3544715447154472 | 0.0 | 0.03333333333333333 |
| P | 0.0891767297030455 | 0.08593619593619595 | 0.0859885466862211 | 0.08703382410848752 | 0.2829268292682927 | 0.0 | 0.05000000000000001 |
| T | 0.08593619593619595 | 0.08749259839777082 | 0.0870328282828283 | 0.08682054087226503 | 0.2813008130081301 | 0.0 | 0.05000000000000001 |

Full neoepitope mean T−P AP **−0.004488920306144006**, T−A
**0.0014783724975854045**, T−D **0.02976178742616133**. P also outperforms D,
so the T−D gain cannot be attributed specifically to genuine measured-Tm pairing.
The source's A0201 subgroup has only 46 observations/5 positives; T mean AP
0.08682054087226503 is below baseline A per-seed AP0.09528679653679653.
These are additional descriptions, not a rescued primary or selection dataset.
Different prevalences/assay contexts preclude interpreting raw AP across sources
as the same difficulty scale. The full neoepitope source has unknown patient/
assay links and only an exact baseline fitting-exclusion guarantee.

## Scientific interpretation and historical context

1. **Genuine pairing versus permutation:** the principal primary T−P AP statistic
   is negative in all seeds, with an exploratory interval spanning zero. There
   is no demonstrated primary AP benefit from correct sequence–Tm pairing.
2. **Practical baseline comparison:** T is below unchanged A on primary AP in
   every seed. Its greater primary AUROC represents a different ranking trade-off,
   not improved primary average precision or stronger top-candidate evidence.
3. **Additional ligand learning:** T's small primary T−D AP advantage is uncertain;
   D gives the best pooled secondary IMPROVE AP. Generic additional discrimination
   and quantitative target-distribution effects cannot be called stability-specific.
4. **Other-HLA effects:** B0702 deterioration and mixed per-HLA changes coexist
   with a tiny full-cohort AP gain. Shared parameters permit transfer in both
   directions, without new allele-specific thermostability supervision.
5. **Further confirmation:** no positive primary signal justifies promoting this
   exact procedure or advancing a confirmatory AP-superiority claim. Independently
   planned work could study broader biology, but none is initiated here.

Task 2.32's fixed positive EL upweighting and Task 2.33's auxiliary EL supervision
used **predicted kinetic-stability ranks**, not the experimentally measured
Celsius Tm targets here. Their zero-shot primary AP results did not support
practical improvement over A. The present study tests a different intervention,
with a different A0201 primary population; absolute APs or qualitative failures
are not a pooled causal estimate. No earlier W/S/P checkpoint starts this fit,
and no prior result chose the current loss weights, seeds or endpoints.

The January 2024 CapsNet-MHC pilot is historical motivation only: different
architecture and evaluation data. We accessed/reproduced no CapsNet code,
checkpoint, transformed data or prediction output and make no formal
cross-architecture superiority claim.

Important limitations: **710 measured ligands from one HLA/source,21 primary IM
positives,16 known components with a large shared-patient/peptide unit, only
three optimization seeds, constrained output-only adaptation, constructed decoys,
compressed soft-target distribution and the fixed balanced objective**. Author
C1R HLA assignments and four unresolved minimum-Tm flags are retained rather
than reinterpreted after results. Prior EL fitting/selection exposure is not
new measured-Tm validation; no adaptation epoch was selected on EL validation.
Prior external benchmark inspection and incomplete assay/patient provenance
prevent a pristine confirmatory interpretation. Seed variability is optimization
variability, not biological replication; primary component intervals are flagged
unreliable. Residual sequence/assay dependencies remain beyond the frozen
Hamming protection.21 recognition positives do not establish generalization to
new HLAs, biological systems or patient populations.

EL presentation, thermal melting temperature, kinetic half-life, MS repeat
identification and T-cell recognition are distinct quantities. Adapted outputs
are not measured pMHC lifetimes or calibrated immunogenicity probabilities.
This negative AP result does not prove measured thermostability biologically
irrelevant; neither these models nor the earlier rank models measure false EL
labels. No labels were retrospectively corrected, no source subset was optimized,
and no BigMHC training pipeline was redesigned on this result.

## Engineering checks, resources and artifact locations

**Initial 16 focused tests pass; after the narrow metadata repair, 17 focused tests
pass**, zero skipped (corrected suite 1.060s). Tests cover native A identity,
source/score alignment, exact target multisets, independent sampling/permutation
streams, hand-checked balanced BCE/gradients, frozen dropout/BatchNorm behavior,
output-only changes, checkpoint tampering/reconstruction, score orientation,
tied AP/AUROC, integer-multiplicity equivalence, paired seed-mean uncertainty,
classless/one-unit undefined handling, stable serialization and no IM labels or
selection calls in training. Synthetic fixtures are engineering tests, not extra
scientific model arms or biological seeds.

GPU preflight passes: exact36-state A reload; only415 trainable scalars and two
gradient keys; native/encoded-input bitwise probes; no parameter update; exact
A synthetic logit−4.594468593597412 consistent with Task 2.32. No learned feature
cache. Training verification passes all nine fits and their common source/order
and frozen state checks. [Completion verification](../scripts/verify_measured_tm_direct_transfer.py)
passes 80550 finite aligned score pairs,20 files and 30000 paired draws without
model inference or metric recomputation. The [figure script](../scripts/plot_measured_tm_direct_transfer.py)
uses saved results only; PNG/PDF show all seeds, primary/secondary intervals and
all 20 evaluable HLA changes. No post-result scientific code was modified.


| Stage | Wall seconds | Peak host RSS bytes |
| --- | --- | --- |
| prepared | 14.674575665034354 | 340914176 |
| preflight | 5.261867399909534 | 1615220736 |
| training_complete | 137.0133806229569 | 2138980352 |
| predictions_frozen | 25.359195755096152 | 1966088192 |
| evaluation_complete | 31.28645658795722 | 134533120 |

The `training_complete` stage resource entry covers **remaining eight fits**;
first D123 training attempt, including its postfit validation failure, took
**19.859961 seconds**. First-fit-only elapsed time/allocator peak are
unavailable, not fabricated. The training process wall sum is approximately
156.8733416229569 seconds, excluding the
diagnostic/recovery/orchestration gap. User/system CPU counters are cumulative
within each process, distinct from stage wall timestamps.

Remaining-fit Torch peak GPU allocation **906357248 bytes**,
reservation **1147142144 bytes**; inference peak allocation
**545342976 bytes**.
The 33 five-second device samples across the two training launches have maximum
used 2175MiB, utilization 63%, power 247.58W and temperature 62°C. Device memory
includes display/context/other allocations and is not a process-exclusive peak.
Python 3.13.5, Torch 2.13.0+cu130, NumPy 2.5.4, CUDA 13.0, cuDNN 92000,
NVIDIA RTX 4090, Linux 6.18.33.2-microsoft-standard-WSL2; deterministic FP32,
AMP/TF32 off, 4 CPU threads. Existing Matplotlib 3.10.7 environment only for figures;
no dependency installation or unrelated download.

All scientific artifacts resolve outside Git under project runs /
**`task-2_37-a02-measured-tm-direct-transfer/`**:

- `inputs/`: frozen training identities, authentic Tm/source fields, class weights,
  seed-specific target/permutation/order files, leakage witnesses, exact external
  identity references/subset IDs and native encoded input tensors.
- `checkpoints/`: nine parent-bound two-tensor checkpoints and complete-state,
  optimizer/update, reload, source and all-pass history receipts.
- `reports/`: source/configuration/pretraining seal, focused tests, native GPU
  preflight, all 180 per-pass reports, training/prediction/evaluation completion,
  preserved failure and metadata repair/equivalence/recovery evidence.
- `predictions/`:20 original-row-associated raw-logit/score files; earlier Task
  2.32/2.33 scores are unchanged.
- `evaluation/`: joined outcomes, every seed/arm metric and mean, predefined
  contrasts, per-HLA descriptions, ties, three paired-draw streams and intervals.
- `figures/`: inspected PNG/PDF; `logs/`: tests, original/resumed training,
  inference/evaluation and actual GPU telemetry.

Final output hashes and a small completion receipt authenticate the artifacts;
large model/data/score files are not in Git. **No IM-supervised training, IM
calibration, checkpoint/epoch selection, outcome-driven tuning, new source,
favorable seed/subset selection, abandoned two-HLA reinterpretation, merge or
push occurred.** All three seeds and all controls are reported, including losses
and negative transfer. No follow-up experiment was started.
