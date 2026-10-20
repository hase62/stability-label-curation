# Task 2.25R — Completed independent neoepitope A/S/P evaluation

**Completed once on Z790 WSL2 / RTX 4090, 2026-10-20.** S did not improve
the predefined primary AP over A. Its AP exceeded P, but the paired uncertainty
interval includes zero. This evaluation does not establish a useful stability-
specific predictive improvement over standard BigMHC.

Branch: `task/2.25-independent-neoepitope-evaluation`.
Execution commit: `93a3225` (complete frozen implementation before identity review).
The [original blocked-stage report](BIGMHC_INDEPENDENT_NEOEPITOPE_TASK2_25_BLOCKED.md)
is preserved byte-for-byte from `c4e827740090bae12fa06613a37a88280651d9b7`.
All original blocked-stage run records remain unchanged.

## Approved amendment and chronological safeguards

The researcher explicitly approved removing the mandatory assay-level provenance
crosswalk in Task 2.25R. The [protocol amendment](BIGMHC_INDEPENDENT_ASP_EVALUATION_PROTOCOL.md)
was committed as **`357a4b7b99ce0ef0bbbf5a7010fed4713f1007f9`**, at
`2026-10-20T01:45:40Z`, before identity review, benchmark predictions, or outcomes.
It replaces original-assay deduplication with the released-observation unit,
retains repeated eligible rows, and treats missing assay/material identifiers
as an explicit independence limitation. The source, models, exact sequence
exclusions, endpoints, tie conventions and uncertainty procedure remain frozen.

Original protocol SHA256:
`cb386443d768fb168366299ae7125aeec7115dda4e81da2dce62d90b4b99d250`.
Amended protocol SHA256:
`794f6cb4a68e8f0cae9d9fba9cc706872141ed1a12c5a5badaf616716903c2f4`.
Original Task 2.24 code/configuration hashes and the original Git protocol blob
were authenticated; only the explicitly approved document amendment is excepted
from the historical protocol hash comparison.

| Boundary | UTC |
| --- | --- |
| Amendment committed | 2026-10-20T01:45:40Z |
| Identity-only eligibility started | 2026-10-20T01:50:01.930930+00:00 |
| Ordered eligible manifests frozen | 2026-10-20T01:50:09.371183+00:00 |
| All A/S/P predictions frozen; no outcomes accessed | 2026-10-20T01:50:48.748764+00:00 |
| Outcome association and one evaluation started | 2026-10-20T01:51:09.418812+00:00 |
| Point estimates and bootstrap complete | 2026-10-20T01:51:16.904130+00:00 |

The identity reader decodes only the first two released fields (`mhc`, `pep`)
and discards the opaque remainder without parsing outcome or predictor values.
Synthetic tests verify this with deliberately undecodable sealed-tail bytes.
All three prediction files were immutable before the first access to `tgt`.
Original published prediction values were never inspected or used.

## Authentic source and identity-only eligibility

The benchmark is **Mendeley Version 4 `datasets.zip`, member `im_test.csv`**,
DOI `10.17632/dvmz6pkzvb.4`, CC BY 4.0, as documented in the existing
source provenance and frozen protocol. The release describes the combined
NEPdb/Neopepsee/TESLA/MANAFEST neoepitope collection. No alternative source,
MANAFEST-only subset, infectious-disease data or reconstructed assay source
was substituted. The authenticated local archive was reused without downloads.

Archive: **144,274,974 bytes**, SHA256
`0d152a452756cf2e0014ffced6afc25118e7c11cf1f626b26e49f50f79edffaa`.
Member: **279,819 uncompressed bytes**, ZIP CRC32 `9b37e4c2`.
Original acquisition HTTP evidence remains at the run root in
`reports/source_acquisition.json`.

Identity is archive SHA256 + member + original one-based data-row index;
source locators are formatted `im_test.csv:row:000000000001`, preserving lexical
and numerical order. Raw HLA/peptide strings and original line numbers are kept.
Peptide normalization strips surrounding whitespace and uppercases, identically
for benchmark and training. Only canonical 20-amino-acid 9-mers and exact,
unambiguous human HLA-I encodings are allowed; no nearest-allele mapping occurs.

| Eligibility step | Excluded at step | Remaining |
| --- | ---: | ---: |
| Original source observations | — | 937 |
| Invalid/non-9-mer peptide | 656 | 281 |
| Unsupported/ambiguous exact HLA representation | 0 | 281 |
| Exact EL-training peptide exposure, across every HLA | 8 | 273 |
| Exact full-IM-training peptide exposure, across every HLA | 6 | **267 primary** |
| Fixed outcome-quality check | 0 | **267 primary** |

All 281 length-nine peptides were valid canonical 9-mers (273 unique sequences).
The overlapping reason counts are also 656 / 0 / 8 / 6; EL and IM sequence
exclusions do not overlap in this source. Primary exclusions total **670**.
The secondary IM-novel cohort excludes 656 non-9-mers and six IM-exposed rows,
retaining **275**. No outcome-quality exclusion occurred in either population.
All 937 released peptide–HLA pairs are distinct; none was silently collapsed.
Source sequence repetition: 915 unique peptides, 14 repeated-peptide groups,
22 excess observations. Original assay and patient counts remain unknown.

The exact Task 2.23 training manifest was joined row-for-row to the authenticated
original EL view, without regenerating a split: **1,308,196 training rows**,
**1,122,528 unique training peptides**, including all **1,245,143 negatives**
and **63,053 positives**. The **145,371 validation** and **11 excluded** rows
were kept outside the training inventory. The complete authenticated
**3,428-row final IM training view** was used. Hashes for both training views,
the split, reference and historical identity inventory are saved in the freeze.

| Descriptive exact exposure in the original benchmark | Observations | Unique peptides | Exact training-pair matches |
| --- | ---: | ---: | ---: |
| EL training | 8 | 7 | 0 |
| Full IM training | 6 | 1 | 0 |
| EL validation | 0 | 0 | 0 |
| Original EL view outside training | 0 | 0 | 0 |
| Historical development | 0 | 0 | 0 |

These are global sequence exclusions even where the benchmark HLA differs from
the training HLA. **Primary EL-training and IM-training peptide overlaps are
both zero; secondary IM-training overlap is zero.** No EL validation exposure
remains. Two source observations / one peptide overlap EL training positives
that received Teacher targets; these observations are EL-exposed and outside
the primary population. Teacher fitting-source exposure was not independently
established and was not used to alter eligibility.

The source spans **54 exactly representable HLAs**; primary and secondary each
span **46**. Primary HLA-A/B/C observation counts are **122 / 88 / 57**;
secondary counts are **128 / 89 / 58**. Exact allele counts are in each cohort's
population report. Sparse allele coverage and HLA-C observations beyond the
project's A/B-restricted training views limit interpretation; no new HLA subset
evaluation was performed.

| Population | N | Unique peptides/clusters | Unique pairs | Positive | Negative | Prevalence / random-ranking AP reference |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| primary | 267 | 265 | 267 | 57 | 210 | 0.21348314606741572 |
| IM_novel | 275 | 272 | 275 | 57 | 218 | 0.20727272727272728 |
| EL_exposed | 8 | 7 | 8 | 0 | 8 | 0.0 |

Primary retains two repeated sequences across distinct HLAs (two excess rows);
secondary retains three repeated sequences (three excess rows). The EL-exposed
subgroup has seven peptide clusters, only eight observations and **no positives**.
Its AP/AUROC and contrasts are unavailable under the frozen minimum-20/both-class
rule. The primary and secondary meet those count/class conditions, but remain
modest cohorts with 57 positives each. No observation was excluded for similarity.

## Frozen checkpoints and inference

| Arm | Final complete IM checkpoint under project runs | Canonical file-map SHA256 |
| --- | --- | --- |
| A | `task-2_23-el-multiepoch-baseline/checkpoints/final_all_IM` | `b92308ab3e35d02530867053ada7e29ee18076bf653df26458f5c3728a2be3a0` |
| S | `task-2_24-fully-trained-stability-auxiliary/checkpoints/S_IM_epoch_20` | `9d5a5012d38b0f7f7203c35769a5a29e35572ced3b8f708a525c03a99996862a` |
| P | `task-2_24-fully-trained-stability-auxiliary/checkpoints/P_IM_epoch_20` | `01014a37c3a4101f90d7765e48420a463a7094169a8c0163fc5994dc4a0c903b` |

All models are frozen EL-10 / full-IM-20 checkpoints, each fitted on all 3,428
IM observations. Each model was loaded and scored once on the same ordered
275-row union (the secondary cohort); primary scores are the fixed 267-row
subset of those same files. There were **18 native batches per arm**, with the
same native input transformation, exact HLA encoding, eval mode, deterministic
CUDA FP32 and original sigmoid IM probability. No auxiliary head or hook entered
inference. A constant-zero target field served only the native input schema;
native non-shuffling inference batches do not use it for selection or scores.
No actual outcomes were loaded for inference.

All 36 tensors per arm strictly match their frozen hashes before inference and
remain unchanged afterward. All **825 probabilities** are finite and serialized
with full FP32 round-trip precision. Native emitted source indices exactly match
the ordered manifest for every arm; no rows were missing. Full checkpoint files
and model manifests remain preserved.

## Full-precision point estimates and contrasts

Primary population: **267 observations, 57 positive, 210 negative**. Every cell
in the following table uses exactly those observations and original outcomes.
Non-interpolated AP groups exactly tied scores at one threshold; AUROC gives
half credit to ties. P@10/P@20 use descending score, canonical peptide, HLA,
then immutable source locator. There are **zero tied score groups** for every
arm on primary and secondary, and no top-10/top-20 boundary ties (group size 1).

| Metric | A | S | P | S−A | S−P | P−A |
| --- | --- | --- | --- | --- | --- | --- |
| AP | 0.2551935661411448 | 0.24661434811487393 | 0.23544913269789144 | -0.008579218026270874 | 0.011165215416982482 | -0.019744433443253356 |
| AUROC | 0.5586466165413534 | 0.531578947368421 | 0.5355889724310777 | -0.02706766917293235 | -0.004010025062656686 | -0.023057644110275666 |
| precision_at_10 | 0.3 | 0.3 | 0.2 | 0.0 | 0.09999999999999998 | -0.09999999999999998 |
| precision_at_20 | 0.2 | 0.25 | 0.15 | 0.04999999999999999 | 0.1 | -0.05000000000000002 |

Secondary IM-novel population: **275 observations, 57 positive, 218 negative**.
Globally unseen subgroup metrics are exactly the primary values above.

| Metric | A | S | P | S−A | S−P | P−A |
| --- | --- | --- | --- | --- | --- | --- |
| AP | 0.24932465958713643 | 0.24157522930294253 | 0.23062747660738364 | -0.007749430284193892 | 0.010947752695558893 | -0.018697182979752786 |
| AUROC | 0.55866731047803 | 0.5335586673104781 | 0.5373410590696925 | -0.025108643167551903 | -0.003782391759214465 | -0.021326251408337438 |

EL-exposed IM-novel subgroup: **8 observations, 0 positive, 8 negative**.
AP/AUROC for all three arms and all three contrasts are **unavailable**; they
were not substituted with another population or metric. JSON null values have
this explicit meaning. All small floating-point contrast residuals shown above
are preserved exactly as recorded, without rounding or score transformations.

## Prespecified paired uncertainty

The single uncertainty analysis used **10,000 draws**, local **Random(24242)**,
and shared-peptide clusters fixed before outcome access. Every row from a drawn
cluster was included with multiplicity. In each draw, each cohort's fixed number
of clusters was resampled in frozen order primary → IM-novel → EL-exposed using
one RNG stream. Within each cohort/draw the same rows serve A/S/P, all defined
endpoints and the paired contrasts. Percentile intervals use linear interpolation
at index `(n−1)q` for q = 0.025 and 0.975. This adds no model or cohort condition.

Primary has **265 clusters** and secondary **272**. Every reported primary and
secondary endpoint/contrast has **10,000 jointly usable draws, zero undefined**;
neither triggers the fewer-than-20-cluster or fewer-than-1,000-draw flag.
The EL-exposed subgroup has **seven clusters**, **zero usable / 10,000 undefined**
draws for AP/AUROC and contrasts; its uncertainty is unavailable/unreliable.
Patient dependence remains unmeasured because patient identifiers are unavailable.

Primary percentile 95% intervals:

| Metric | A 95% interval | S 95% interval | P 95% interval | S−A 95% interval | S−P 95% interval | P−A 95% interval |
| --- | --- | --- | --- | --- | --- | --- |
| AP | [0.18380688957252042, 0.3541107642133599] | [0.17639342392006593, 0.3459633188270979] | [0.17181102900481085, 0.32306548345332115] | [-0.053363738982957785, 0.04069652602525732] | [-0.01512166068622275, 0.04932118034898689] | [-0.0666705410045517, 0.01839086986023603] |
| AUROC | [0.4832552266854592, 0.6360644887845592] | [0.45105674143554525, 0.6137461239933214] | [0.4616373040444248, 0.6115076694909435] | [-0.07154624732735791, 0.01781331904078367] | [-0.03827834188515306, 0.031212828217328813] | [-0.06006793431399604, 0.015257874011803257] |
| precision_at_10 | [0.1, 0.6] | [0.0, 0.6] | [0.0, 0.5] | [-0.30000000000000004, 0.2] | [0.0, 0.30000000000000004] | [-0.4, 0.2] |
| precision_at_20 | [0.05, 0.45] | [0.05, 0.45] | [0.0, 0.3] | [-0.19999999999999998, 0.2] | [-0.04999999999999999, 0.3] | [-0.3, 0.1] |

Secondary IM-novel percentile 95% intervals:

| Metric | A 95% interval | S 95% interval | P 95% interval | S−A 95% interval | S−P 95% interval | P−A 95% interval |
| --- | --- | --- | --- | --- | --- | --- |
| AP | [0.18002840126220312, 0.34894587586144465] | [0.17209775852950818, 0.3391202557503691] | [0.16705120527799955, 0.3176549568461449] | [-0.05382791686578792, 0.04054154208747542] | [-0.015402776302672443, 0.0509261559025191] | [-0.06767937706284287, 0.02099271256339068] |
| AUROC | [0.4832821686198178, 0.6331419285156312] | [0.45450070601313397, 0.6106270431298112] | [0.46402984724346397, 0.6110082889664553] | [-0.06888341053914444, 0.019749002913837344] | [-0.03845632090423756, 0.031129752975206284] | [-0.05879638808779935, 0.01673971802455627] |

The primary AP S−A interval spans **−0.053363738982957785 to
0.04069652602525732**; S−P spans **−0.01512166068622275 to
0.04932118034898689**. Both include zero. No formal multiplicity-adjusted
superiority claim or additional significance test was planned or performed.

## Scientific interpretation

1. **S does not improve primary AP over A:** 0.24661434811487393 versus
   0.2551935661411448; S−A = −0.008579218026270874. S also has lower primary
   AUROC, equal P@10 and higher P@20, which cannot replace the primary endpoint.
2. **S has higher point-estimate AP than P:** S−P = 0.011165215416982482,
   with a paired interval including zero. S's AUROC is slightly below P.
3. **No benefit over A persists on globally EL/IM-unseen peptides:** that is
   precisely the primary population. The broader IM-novel AP has the same
   ordering A > S > P. An advantage over P alone does not establish practical
   stability-specific improvement when S does not beat A. Both auxiliary arms
   have lower AP than baseline; the permutation comparison does not establish
   a useful generic auxiliary-learning effect either.
4. This is consistent with the prior one-epoch finding of no convincing
   stability-specific benefit. Task 2.23's longer-training improvement was
   developmental evidence on another population. These independent AP values
   cannot be numerically compared with its developmental AP as a common test,
   and no earlier-epoch model was evaluated here.
5. All three observed primary AP values exceed the prevalence reference
   **0.21348314606741572**, and secondary AP values exceed
   **0.20727272727272728**, descriptively. This is not a significance claim
   against random ranking or evidence of strong discrimination.
6. The result applies to this frozen single-seed comparison and released
   source-dataset benchmark. Complete original assay, patient/specimen and
   study independence cannot be verified. Repeated measurements may remain
   dependent. Peptide clustering captures exact repeats but not unmeasured
   patient dependence. Exact sequence exclusion leaves similar peptides and
   shared HLA biology; this is **not a sequence-similarity hard split**.
   Modest positive counts, sparse HLA representation, HLA coverage shift,
   published candidate-selection/source differences, Teacher error, one seed,
   one permutation and earlier adaptive developmental work constrain claims.

Teacher-derived predicted kinetic stability is not a measurement of EL-label
errors or repeated EL detection. No inference about label correctness or repeat-
detection probability follows. Kinetic half-life and thermal melting temperature
remain scientifically separate. This negative/inconclusive stability-utility
result triggers no follow-up experiment, tuning or model change in this task.

## Focused validation, resources and retained artifacts

**19 focused tests passed, zero failures/errors/skips**, using the existing GPU
Python environment and synthetic examples only. They cover opaque identity
projection, retained duplicate observations, global sequence exclusions, exact
tied-score AP/AUROC, deterministic top-K ordering, undefined metrics, contrast
signs, interpolated quantiles and paired peptide-cluster bootstrap behavior.
Actual CUDA checkpoint reload, finite predictions, native row association and
unchanged tensors passed as execution gates. Final verification authenticates
saved hashes and chronology without rerunning scoring, point metrics or bootstrap.

Actual runtime: Python **3.13.5**, PyTorch **2.13.0+cu130**, NumPy **2.5.4**,
CUDA **13.0**, cuDNN **92000**, Linux **6.18.33.2-microsoft-standard-WSL2**,
RTX **4090**, four CPU threads. Deterministic algorithms on; AMP and TF32 off;
batch size 16. No new dependency was installed.

| Executed stage | Wall seconds |
| --- | ---: |
| Identity-only inventory and eligibility freeze | 7.439088860002812 |
| Authentication, reload and all three inference passes | 8.153754698985722 |
| Outcome association, point metrics and 10,000-draw bootstrap | 7.483732221997343 |
| Sum of measured stage times | 23.076575780985877 |

The recorded start-to-completion span was **74.9732 seconds**, including
between-stage inspection gaps. Peak inference-process host RSS:
**1,909,587,968 bytes**. Peak Torch GPU allocated/reserved:
**525,777,408 / 765,460,480 bytes**.
Metric-process peak RSS: **46,436,352 bytes**. These are process
high-water/Torch allocator measures; no system GPU power/utilization profile
or kernel-level timing was collected.

All new outputs are under resolved project runs /
`task-2_25-independent-neoepitope-evaluation/resumed/`, preserving original
blocked-stage files at the run root. Key retained artifacts:

- `reports/protocol_amended.md`, source identity and frozen model receipts.
- `cohorts/all_source_identities.jsonl`, exclusions, primary/secondary/EL-exposed
  ordered manifests and their pre-outcome hashes.
- `predictions/A.jsonl`, `S.jsonl`, `P.jsonl` and subsequent associated outcomes.
- `reports/metrics.json`, `bootstrap.json`, `class_distributions.json`,
  `contrasts.json`, `resource_summary.json` and this interpretation.
- Exclusive stage-start/freeze/completion receipts, focused test report/log,
  stage logs, immutable output manifest and final verification/finalization.

**One frozen A/S/P benchmark evaluation is complete.** The amendment preceded
outcome inspection; identities preceded predictions; all predictions preceded
outcome association. No training, retraining, additional seed, tuning,
calibration, model/checkpoint selection, ensembling, threshold optimization,
outcome-based eligibility change, stricter similarity split, benchmark search,
additional download, merge or push occurred. Models and historical results
remain unchanged. Work stops after this evaluation and its documentation.
