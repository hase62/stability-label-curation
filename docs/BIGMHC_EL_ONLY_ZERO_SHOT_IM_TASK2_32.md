# Task 2.32 — Direct EL-only zero-shot immunogenicity evaluation

Completed on Z790 WSL2 / RTX 4090, **2026-10-22 JST**. Branch
`task/2.32-el-only-zero-shot-im`, directly based on approved Task 2.31 commit
`e6cdb4a2d49848a672131e76cd5614fb7574789f`.

**Stability-weighted EL training did not improve the primary zero-shot IM AP.**
On IMPROVE Hamming >=3, A/W/P AP is **0.03638362130144917 /
0.03417089015419916 / 0.03604068959075655**. W−A =
**−0.0022127311472500064**, W−P = **−0.0018697994365573858**; both paired
exploratory intervals include zero. On the secondary neoepitope cohort W also
falls below A, while its small advantage over P has an interval including zero.
No useful stability-specific zero-shot improvement is demonstrated.

**Recommendation: NO-GO for promoting this exact weighting rule or claiming
zero-shot IM superiority.** Preserve this negative/inconclusive result rather
than tuning, selecting another epoch or choosing a favorable source/HLA. The
broader stability hypothesis remains open; an independently designed replication
could address other contexts, but this result supplies no positive superiority
signal to advance the current rule. No new training or benchmark was started.

## Scientific distinction and prospective freeze

This task is **EL training → frozen EL checkpoint → direct T-cell-recognition
ranking**. No immunogenicity label trained, tuned, calibrated or selected any
new model here. There is **no EL→IM transfer, IM head or IM fine-tuning**.
The [Task 2.32 protocol](BIGMHC_EL_ONLY_ZERO_SHOT_IM_TASK2_32_PROTOCOL.md),
[configuration](../configs/bigmhc_el_only_zero_shot_im_task2_32.json), implementation
and initial nine focused tests were committed before all new study predictions
and performance calculations:
`31bb3998b330e14ae64f9173d4898a6db9118d5c`.

Both sources were previously evaluated with **different IM-fine-tuned models**.
This is a prespecified follow-up of EL checkpoints already frozen in Task 2.31,
**not a previously untouched confirmatory blind test**. Prior outcomes/results
were known. They did not choose these models, score transforms, subsets,
thresholds or resampling rules. This supersedes the proposed external-EL task.

The only new scores are native sigmoid EL outputs. Preserve raw FP32 logits
and probabilities; every ranking endpoint uses the same **native FP32 sigmoid
probability** in all arms/sources. No HLA normalization, learned transformation,
IM calibration, score cutoff, ensembling or logit-based alternative performance
analysis was introduced. EL-positive scores are presentation proxies, not
calibrated T-cell-recognition probabilities.

## Exact EL checkpoints and common inference

All arms use authentic BigMHC source commit
`199e890fa69a63646730bcecea0a520e08ca4f02`, the same architecture, EL source
partition, original labels and ten EL epochs. A is unweighted; W is Task 2.31's
`1+0.5*max(0,r-.5)` with training-only HLA ranks; P is its within-HLA permuted
positive-weight control with identical HLA weight multisets/masses. These are
**not** the Task 2.24 auxiliary S/P models.

| Arm | Checkpoint under resolved project runs | Canonical file-map SHA256 |
| --- | --- | --- |
| A | `task-2_23-el-multiepoch-baseline/checkpoints/EL_epoch_10` | `d8e3d7d3ac5d08d7f420e00b8032fa875b8b6fec1cd9da6b36d35bca0bec04d1` |
| W | `task-2_31-el-stability-positive-upweighting/checkpoints/W_EL_epoch_10` | `a6b24dad431f50f170e1945f7fe9ad366bee323890b9055830cd5e56078a6892` |
| P | `task-2_31-el-stability-positive-upweighting/checkpoints/P_EL_epoch_10` | `53cb323e3e81137713a80a443cd40b8d7c574f6af31525ea3ff6f5d62d4294a9` |

File maps use SHA256 of canonical sorted filename→SHA256 JSON. All 36 tensor
files, ordered tensor keys and exact expected tensor states authenticate against
the approved Task 2.31 manifest/EL lineage. Exact checkpoint paths and hashes,
not architecture alone, distinguish these from complete IM models. Only explicit
complete EL tensor files are loaded; no four-layer transfer overlay or parent-IM
fallback. All models strictly reload, are FP32, have no auxiliary hooks/heads,
and remain byte/tensor-identical after inference.

Same frozen canonical uppercase 9-mers, exact normalized HLA IDs and original
414-feature HLA pseudosequence encodings; no approximate allele. Native input
transformation and emitted source order were checked for every arm. Targets
are constant-zero schema placeholders, never benchmark labels or sampler filters.
Eval/no-grad, batch16, deterministic CUDA FP32, AMP/TF32 off. A synthetic
non-benchmark probe verifies finite EL outputs for all three before study inference.

Each arm scores **7,788 + 267 = 8,055 original observations once** in separate
source passes: 487 + 17 native batches. All six prediction files, totaling
**24,165 raw-logit/probability pairs**, were fixed by
**2026-10-22T03:20:33.587623+00:00**, before any new comparison. All outputs are
finite, correctly source-associated, with unchanged model tensors. No Teacher
checkpoint was scored or refitted. No IM training payload or optimizer was used.

## Authenticated fixed populations

### Primary IMPROVE Hamming >=3

Borch et al., [Frontiers in Immunology 2024, DOI 10.3389/fimmu.2024.1360281](https://doi.org/10.3389/fimmu.2024.1360281).
Reuse the exact Task 2.26/2.27 author-repository source and frozen cohort:
`SRHgroup/IMPROVE_paper` at `c67094276b52358b5202ad9e5597acd87888ea1d`,
archive `data.zip`, member `data/01_data/01_Validated_neoepitopes.txt`.
The endpoint is screened DNA-barcoded pMHC multimer **T-cell recognition** in
patient material, not an untested synthetic label, direct cytokine function or
measured endogenous presentation. Screen negatives are contextual nondetections
of recognition, not universal non-immunogenicity.

Curation freeze SHA256:
`20e45f3740beebc39fd78581afd5da7ff49c59798bfcd505cd3ddfcf2c763557`.
Original ordered identity SHA256:
`bd555e21e3ce16ea0aafe9b4dbc8f5ed88548cc366d07c8160ba222ba9fb74ed`.
Outcome SHA256:
`64ed767d65e4e5f9895b1062f9ff160054d1d29b9b460d7bd3e8037279e31709`.

Keep the exact minimum Hamming >=3 exclusion from the predefined fitting and
selection/development sequence union, including EL fit and selection references.
All exact/one-/two-substitution neighbors and the original prior-benchmark exact
overlaps remain excluded. IM-fitting/selection sequences are retained in the
**historical eligibility reference**, not supplied to training or an optimizer
in this EL-only task. Curation/distance witnesses were reused without rerunning
the search or changing rules. No >=2 or >=4 diagnostics were scored.

### Secondary published neoepitope primary cohort

Mendeley Version 4 [DOI 10.17632/dvmz6pkzvb.4](https://doi.org/10.17632/dvmz6pkzvb.4),
authenticated local `datasets.zip` SHA256
`0d152a452756cf2e0014ffced6afc25118e7c11cf1f626b26e49f50f79edffaa`,
member `im_test.csv`. Reuse Task 2.25's **primary**, not its 275-row IM-novel
secondary population. Primary identity SHA256:
`c910f6913d669b3d48c85019cff04f56c0bed72a594060a465c0e1bd47912d48`;
eligibility freeze SHA256:
`663c7dedb42432e1efaebbd151daa9fc8ed4d263430e652505fd83244e72d79a`.
It remains exactly peptide-disjoint from actual EL and full IM fitting data,
but is not a sequence-similarity hard split. Original source row indices,
raw/canonical peptide/HLA, duplicates and published labels are unchanged.
Only the first three source fields identify HLA, peptide and `tgt`; published
model-score columns were discarded and never model inputs. Unknown source
assay/patient linkage remains the approved Task 2.25 limitation.

| Population | N | Positive | Negative | Positive prevalence / AP reference | Unique peptides | Unique pMHC | HLAs | Patients | Studies |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| IMPROVE >=3 | 7788 | 227 | 7561 | 0.029147406266050335 | 6576 | 7750 | 36 | 70 | 3 |
| Neoepitope primary | 267 | 57 | 210 | 0.21348314606741572 | 265 | 267 | 46 | Unknown | Unknown |

No original observations are deduplicated. IMPROVE has 1,212 excess peptide
observations and 38 excess pMHC observations; neoepitope has two excess peptide
observations. Patient-specific responses remain distinct. Both include exactly
encodable HLA-C observations beyond the A/B-only EL-fitting allele scope; their
mapping compatibility is not evidence of supervised allele support. No HLA
subset is excluded to improve performance.

| IMPROVE contributing study DOI | Patients | Observations | Positive |
| --- | ---: | ---: | ---: |
| 10.1038/s41467-022-29342-0 | 24 | 3255 | 84 |
| 10.1101/2024.03.17.585416 | 20 | 2034 | 51 |
| 10.1172/JCI150535 | 26 | 2499 | 92 |

Original patient/study class counts and HLA composition are retained in the
point report. Different patients/clones/studies are not claimed exchangeable
merely because rows are numerous. No previous prediction or outcome table was
reanalyzed to curate these populations.

## Full-precision primary and secondary point results

AP is pooled non-interpolated average precision grouping exact ties. AUROC
credits ties by one half. Top-K uses descending probability, then canonical
peptide, HLA, study DOI, patient, immutable source locator; unknown neoepitope
study/patient fields do not invent provenance. All metrics/contrasts in each
table use that table's complete unchanged N and class balance.

### IMPROVE: N=7788, positive=227, negative=7561

| Metric | A | W | P | W−A | W−P | P−A |
| --- | --- | --- | --- | --- | --- | --- |
| AP | 0.03638362130144917 | 0.03417089015419916 | 0.03604068959075655 | -0.0022127311472500064 | -0.0018697994365573858 | -0.0003429317106926205 |
| AUROC | 0.5024228783573484 | 0.512905024450184 | 0.512942312947207 | 0.010482146092835598 | -3.728849702300252e-05 | 0.0105194345898586 |
| Precision@10 | 0.1 | 0.0 | 0.0 | -0.1 | 0.0 | -0.1 |
| Precision@20 | 0.05 | 0.1 | 0.05 | 0.05 | 0.05 | 0.0 |
| Prevalence / AP reference | 0.029147406266050335 | 0.029147406266050335 | 0.029147406266050335 | 0.0 | 0.0 | 0.0 |
| AP minus prevalence | 0.007236215035398834 | 0.0050234838881488275 | 0.006893283324706213 | -0.0022127311472500064 | -0.0018697994365573858 | -0.0003429317106926205 |
| AP / prevalence | 1.2482627431528022 | 1.1723475441449474 | 1.2364973151225198 | -0.07591519900785482 | -0.06414977097757246 | -0.011765428030282354 |

### neoepitope: N=267, positive=57, negative=210

| Metric | A | W | P | W−A | W−P | P−A |
| --- | --- | --- | --- | --- | --- | --- |
| AP | 0.2564378062905638 | 0.22265066613706244 | 0.21776514233858985 | -0.033787140153501344 | 0.004885523798472596 | -0.03867266395197394 |
| AUROC | 0.5375104427736007 | 0.5048454469507101 | 0.5033416875522139 | -0.03266499582289062 | 0.0015037593984962294 | -0.03416875522138685 |
| Precision@10 | 0.3 | 0.2 | 0.1 | -0.09999999999999998 | 0.1 | -0.19999999999999998 |
| Precision@20 | 0.3 | 0.3 | 0.25 | 0.0 | 0.04999999999999999 | -0.04999999999999999 |
| Prevalence / AP reference | 0.21348314606741572 | 0.21348314606741572 | 0.21348314606741572 | 0.0 | 0.0 | 0.0 |
| AP minus prevalence | 0.04295466022314806 | 0.009167520069646717 | 0.004281996271174121 | -0.033787140153501344 | 0.004885523798472596 | -0.03867266395197394 |
| AP / prevalence | 1.2012086715715884 | 1.0429425940104504 | 1.0200577720070787 | -0.15826607756113797 | 0.02288482200337172 | -0.1811508995645097 |

W has lower AP than A in **both** sources. W−P AP is negative on the primary
and positive on the secondary, so a stability-specific advantage is not
consistent. A is best by AP in both. Primary W's AUROC increase over A cannot
replace failed primary AP; W/P AUROC is almost identical there. Neoepitope W's
AUROC is below A. No endpoint was promoted after reading results.

Observed primary top candidates: A has **1/10 and 1/20** recognized; W **0/10
and 2/20**; P **0/10 and 1/20**. Secondary: A **3/10, 6/20**; W **2/10, 6/20**;
P **1/10, 5/20**. Thus there is no uniform high-ranked-candidate improvement.
Top-K is especially discrete with low primary prevalence and dependent rows.

The AP references differ substantially, **2.9147% versus 21.3483%**. Absolute
AP across sources is not a common measure of difficulty. W AP/prevalence is
1.1723475441449474 on IMPROVE versus 1.0429425940104504 on neoepitope; these are
descriptive references, not significance against random ranking. Predicted EL
probability is not calibrated to either source's recognition prevalence.

## Paired uncertainty and dependence

Reuse the frozen **38 patient/peptide connected components** for IMPROVE, where
sharing a peptide or patient (namespaced by study) joins observations. The
largest component has 2,475 observations and connects 21 patients. There are
not 7,788 independent biological samples. Use 10,000 paired cluster draws,
local Random(262742), sorted component IDs, fixed component count with
replacement, retaining every row with multiplicity identically in A/W/P.
Study/peptide sensitivity has **one** connected component linking three studies;
its confidence interval is **undefined**, with **zero executed draws**. Do not
manufacture independent three-study intervals. Seed 262743 is recorded only.

Neoepitope uses **265 canonical-peptide clusters**, 10,000 paired draws and
local Random(24242). Patient/assay dependence cannot be captured without IDs.
These reuse prior clustering/metric/seed rules, with separate single-population
streams; they do not reproduce earlier streams interleaving now-unauthorized
cohorts. No other cohort was scored or resampled to advance a historical RNG.
Exact integer multiplicities implement expanded samples and preserve ties.
Percentiles interpolate linearly at `(n-1)q`, q=.025/.975. No p-value search,
row-independent biological interval or cross-source pooling was performed.

| Dataset / contrast | AP exploratory 95% interval | AUROC exploratory 95% interval |
| --- | --- | --- |
| IMPROVE / W-A | [-0.007474497903949556, 0.0021681901946677164] | [-0.014288464560285376, 0.039710700689076055] |
| IMPROVE / W-P | [-0.005708711796714972, 0.0009783982076402875] | [-0.014426047761534977, 0.016131554663448823] |
| IMPROVE / P-A | [-0.003451440856867785, 0.0028933779806680888] | [-0.004647519931778503, 0.028522129062009998] |
| neoepitope / W-A | [-0.07553861790150554, 0.0007226005804069825] | [-0.06632608588594503, -0.0005901182530020783] |
| neoepitope / W-P | [-0.015404828374688581, 0.028043118869739262] | [-0.025981479619200953, 0.029174883525400715] |
| neoepitope / P-A | [-0.07545738581850367, -0.005834262422003257] | [-0.06541548815511757, -0.003442743107360617] |

All listed endpoints have **10,000 jointly usable / zero undefined draws**.
All four W−A/W−P AP intervals include zero; primary evidence supports no
superiority conclusion. Neoepitope P−A AP/AUROC and W−A AUROC intervals are
negative conditional on this peptide bootstrap; no population-level biological
significance is inferred. Counts meet the protocol's >=20-unit/1000-usable-draw
flags, but those flags do not remove within-study dependence or assure broad
generalization. Complete intervals for every endpoint, including top-K and
prevalence-relative AP, and all component multiplicities/draw contrasts are saved.

## Descriptive HLA and score diagnostics

Prespecified HLA evaluability is N>=20 and at least five original positives and
five negatives, fixed before scoring. All original rows remain in the pooled
primary regardless. **20/36 IMPROVE alleles** qualify: W beats A in AP for
**8/20** and P for **6/20**, with mixed effects. **2/46 neoepitope alleles**
qualify: W beats A for both, and P for one; this small favorable descriptive
subset does not replace the worse pooled result. Other allele endpoints are
explicitly null for insufficient counts, not selected or substituted.

Rounded HLA display below; full-precision AP/AUROC and all contrasts/class
counts, including every nonevaluable allele, are in `evaluation/point_metrics.json`.

| Dataset / HLA | N | Positive | A AP | W AP | P AP | A AUROC | W AUROC | P AUROC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| IMPROVE / HLA-A*01:01 | 251 | 14 | 0.248730 | 0.257420 | 0.281587 | 0.675407 | 0.630802 | 0.630199 |
| IMPROVE / HLA-A*02:01 | 616 | 21 | 0.069292 | 0.049643 | 0.073477 | 0.543017 | 0.538215 | 0.577911 |
| IMPROVE / HLA-A*03:01 | 474 | 6 | 0.045401 | 0.067184 | 0.032728 | 0.527422 | 0.507479 | 0.521724 |
| IMPROVE / HLA-A*11:01 | 153 | 6 | 0.258360 | 0.190043 | 0.185428 | 0.664399 | 0.706349 | 0.679138 |
| IMPROVE / HLA-A*24:02 | 379 | 12 | 0.057683 | 0.059072 | 0.064938 | 0.594460 | 0.589464 | 0.559037 |
| IMPROVE / HLA-A*26:01 | 243 | 6 | 0.041401 | 0.030890 | 0.029804 | 0.362166 | 0.373418 | 0.413502 |
| IMPROVE / HLA-A*30:01 | 163 | 6 | 0.182637 | 0.208972 | 0.242671 | 0.835456 | 0.887473 | 0.883227 |
| IMPROVE / HLA-A*32:01 | 239 | 6 | 0.032907 | 0.031956 | 0.033876 | 0.467096 | 0.423462 | 0.448498 |
| IMPROVE / HLA-B*07:02 | 555 | 8 | 0.016545 | 0.017613 | 0.017749 | 0.508227 | 0.497258 | 0.530850 |
| IMPROVE / HLA-B*08:01 | 402 | 7 | 0.129220 | 0.037550 | 0.068405 | 0.530199 | 0.540325 | 0.528752 |
| IMPROVE / HLA-B*27:05 | 119 | 5 | 0.090027 | 0.071585 | 0.074513 | 0.545614 | 0.510526 | 0.519298 |
| IMPROVE / HLA-B*35:01 | 225 | 8 | 0.035780 | 0.034542 | 0.040513 | 0.455069 | 0.432028 | 0.472350 |
| IMPROVE / HLA-B*35:03 | 91 | 6 | 0.109371 | 0.123072 | 0.091296 | 0.621569 | 0.615686 | 0.607843 |
| IMPROVE / HLA-B*38:01 | 390 | 10 | 0.054214 | 0.052776 | 0.049286 | 0.586842 | 0.584474 | 0.579737 |
| IMPROVE / HLA-B*40:01 | 276 | 13 | 0.052014 | 0.053157 | 0.058064 | 0.464756 | 0.436385 | 0.477625 |
| IMPROVE / HLA-C*03:04 | 288 | 10 | 0.088374 | 0.073746 | 0.077179 | 0.703957 | 0.674460 | 0.687410 |
| IMPROVE / HLA-C*04:01 | 389 | 7 | 0.053137 | 0.034674 | 0.033808 | 0.671653 | 0.632386 | 0.620793 |
| IMPROVE / HLA-C*06:02 | 225 | 25 | 0.136953 | 0.119758 | 0.122191 | 0.578600 | 0.527400 | 0.544200 |
| IMPROVE / HLA-C*07:01 | 556 | 15 | 0.053781 | 0.041243 | 0.059205 | 0.539741 | 0.495995 | 0.536537 |
| IMPROVE / HLA-C*07:02 | 275 | 14 | 0.055147 | 0.061158 | 0.069413 | 0.496716 | 0.483032 | 0.516147 |
| neoepitope / HLA-A*02:01 | 46 | 5 | 0.095287 | 0.095336 | 0.089775 | 0.346341 | 0.341463 | 0.302439 |
| neoepitope / HLA-B*07:02 | 20 | 5 | 0.299634 | 0.330733 | 0.357937 | 0.560000 | 0.626667 | 0.653333 |

Primary exact tied-score groups A/W/P: **38 / 39 / 38**, comprising **76 / 78 /
76** observations; secondary has **zero ties** in every arm. No top-10 or top-20
boundary crosses a tie. Every probability lies strictly between zero and one;
there is no sigmoid endpoint saturation. The raw logit and probability ranges,
quantiles and means are saved per source/arm, preserving raw FP32 output rather
than fitting a transformation.

| Dataset / arm | Mean EL probability | Median EL probability | Minimum raw logit | Maximum raw logit |
| --- | ---: | ---: | ---: | ---: |
| IMPROVE / A | 0.21532476088122898 | 0.06996020302176476 | -23.08500862121582 | 14.193541526794434 |
| IMPROVE / W | 0.23966004779235697 | 0.0877532847225666 | -23.1049861907959 | 13.465653419494629 |
| IMPROVE / P | 0.22540365846883323 | 0.07024835795164108 | -25.403593063354492 | 13.331039428710938 |
| neoepitope / A | 0.3174835940850716 | 0.19153666496276855 | -18.986976623535156 | 5.340961933135986 |
| neoepitope / W | 0.3412200570728321 | 0.2247379869222641 | -17.955989837646484 | 4.805234909057617 |
| neoepitope / P | 0.331540775165476 | 0.2254839986562729 | -21.60049057006836 | 4.628622531890869 |

W raises mean EL probability without improving IM AP. Higher EL confidence is
not improved T-cell recognition ranking or calibrated recognition probability.

## Comparison with previously IM-fine-tuned experiments

From existing documentation only, Task 2.27 primary IM-fine-tuned A/S/P AP was
**0.03449836644306334 / 0.03330451972805489 / 0.032810995993973115**; baseline
A again had the highest AP. Task 2.25 primary IM-fine-tuned A/S/P AP was
**0.2551935661411448 / 0.24661434811487393 / 0.23544913269789144**, likewise
with A highest. No historical predictions were reanalyzed or models reloaded.

The new direct-EL baseline A AP is numerically 0.03638362130144917 on IMPROVE
and 0.2564378062905638 on neoepitope, but these descriptive cross-task values
are not a causal test of whether IM fitting helps. S/P previously used auxiliary
stability supervision, not the present positive-upweighting W/P; their label
training histories and interventions differ. No matched cross-era interval or
combined effect was estimated. Both new and prior comparisons fail to establish
a useful stability-specific AP advantage over their original baseline.

The Task 2.31 developmental EL result also had W below both A and P in pooled
EL AP. This task directly tests the distinct **zero-shot recognition ranking**
question without any new IM fitting, rather than inferring it from EL accuracy.
Neither that EL result nor prior weak SHERPA/JY MS-detection associations select
a score/threshold here. Association evidence does not validate the weighting
function, its coefficient or EL-label correction.

## Execution chronology, focused checks and technical repair

Initial **nine focused tests passed before protocol commit/inference**. Tests
cover authentic EL checkpoint/cohort hashes without study scoring; absence of
optimizer, learning, calibration and transfer calls; constant-zero native
targets; retained repeated observations; source/HLA order mismatch rejection;
hand-calculated tied AP/AUROC; repeated-row top-K equivalence; paired local-RNG
resampling, undefined class metrics and single-component interval handling.
Actual GPU preflight strictly loaded all three EL checkpoints with finite
synthetic probes. All six study prediction passes then succeeded.

After the first IMPROVE point report was saved, an output-path branch attempted
to open its first bootstrap gzip stream without importing `gzip`. It raised
**NameError before any resampling draw or secondary point computation**. This
was an implementation I/O error, not a scientific-data/model blocker. The
original failure receipt/log and computed output remain unchanged.

Technical repair commit **`b4ca2f33b0af7237a6597b97797fe822663638e6`** adds the missing standard-library
import, an evidence-file test and a guarded explicit resume path. The protocol,
configuration, models, inputs, metrics, scores, seeds and eligibility are
unchanged. `reports/technical_io_repair.json` pins previous/corrected code hashes
and hashes of all six predictions plus the saved primary points/joined rows.
The primary points were **reused**, not recalculated; each primary bootstrap,
secondary point computation and secondary bootstrap executed once. No study
inference was repeated. Corrected **ten focused tests pass, no skips**.

The completion verifier passed without model calls, performance recalculation
or bootstrap rerun: 36 native keys in each of three EL checkpoints; both fixed
cohorts; **24,165 finite aligned logit/probability pairs**; exact preservation
of completed outputs across the repair; **20,000 paired draw records** with
correct component multiplicities/N; and no invented study interval. This is a
single scientific evaluation with a documented I/O continuation, not a repeated
experiment or modified protocol chosen from results.

Preflight completed **2026-10-22T03:19:53.214317+00:00**, all predictions froze
**03:20:33.587623+00:00**, and resumed completion was
**03:23:20.031574+00:00**. Measured preflight/inference/resumed-analysis wall times
were **6.191522467008326 / 11.792265418975148 / 14.421952723001596 seconds**;
these omit human inspection/repair gaps and the failed short I/O attempt.
Runtime: Python **3.13.5**, Torch **2.13.0+cu130**, NumPy **2.5.4**, CUDA **13.0**,
cuDNN **92000**, Linux WSL2, RTX 4090, four CPU threads. Deterministic algorithms
on, AMP/TF32 off. Peak inference GPU allocated/reserved:
**525,777,408 / 838,860,800 bytes**. Peak inference host RSS:
**1,927,979,008 bytes**; resumed metric process **88,535,040 bytes**. These are
process high-water/allocator measures, not kernel or system power profiling.
No dependencies, data, weights or RAW spectra were downloaded.

## Artifacts and stopping point

Resolved project runs / `task-2_32-el-only-zero-shot-im/` contains:

- `reports/scientific_configuration.json`, `cohort_references.json`,
  `EL_model_identities.json`: frozen source, model, common input and protocol refs.
- `cohorts/*_identities.jsonl`, `*_outcomes.jsonl`: immutable ordered input
  projections linked to complete authenticated original manifests, separate labels.
- `predictions/*_[AWP].jsonl`: all six once-only raw EL logits/probabilities with
  original source, peptide/HLA, patient/study and frozen component identities.
- `evaluation/*_joined.jsonl`, `*_point_metrics.json`, `point_metrics.json`:
  original outcomes joined after prediction freeze, full endpoints/contrasts,
  HLA and patient/study composition, raw/probability/tie diagnostics.
- `evaluation/*_paired_uncertainty.json`, `*_draws.jsonl.gz`: paired intervals,
  settings, undefined study sensitivity and complete resampling evidence.
- `reports/preflight.json`, `predictions_frozen.json`, technical-repair/failure
  records, `completion_verification.json`, and `logs/`: actual execution evidence.
- `figures/EL_only_zero_shot_IM.png` and `.pdf`: prevalence-relative AP, AUROC,
  both sources' paired AP contrasts and exploratory intervals from saved outputs.

The evidence does **not** support the original hypothesis for this exact frozen
weighting intervention and zero-shot scoring design. W fails primary AP over
both controls and falls below A on the second source. A secondary W−P point
advantage alone, favorable top-20 count or HLA subset cannot establish useful
stability-specific prediction. Uncertainty, one seed/permutation, low primary
prevalence, assay/source/HLA shifts, sparse allele counts, shared peptide/patient
structure, three connected studies and unknown neoepitope patient provenance
limit generalization. This remains a follow-up using previously evaluated
benchmarks, not independent confirmatory blindness.

EL presentation, T-cell recognition, kinetic half-life, MS repeat detection and
EL-label correctness are distinct. No result identifies low-stability positives
as erroneous or refutes the biological importance of stability. No IM/EL
training, EL→IM transfer, Teacher scoring/refitting, checkpoint selection,
calibration, tuning, outcome-driven eligibility change, benchmark substitution,
merge or push occurred. Stop here; no additional learning experiment follows.
