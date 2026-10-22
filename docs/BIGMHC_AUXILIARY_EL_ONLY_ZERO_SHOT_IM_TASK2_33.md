# Task 2.33 — Stability-auxiliary EL-only zero-shot immunogenicity evaluation

Completed on Z790 WSL2 / RTX 4090, **2026-10-22 JST**. Branch
`task/2.33-auxiliary-el-only-zero-shot-im`, directly based on approved Task 2.32
commit `be644fd3a09a1f5a2cdd320f8f6be1fae7a08869`.

**Genuine stability-auxiliary EL training did not improve zero-shot IM AP over
ordinary EL training.** Primary IMPROVE A/S/P AP is
**0.03638362130144917 / 0.03543918286237654 / 0.03376717826224673**.
S−A = **−0.0009444384390726313**, S−P = **0.0016720046001298047**;
both exploratory paired intervals include zero. On neoepitope, S also falls
below A; its very small S−P advantage again has an interval including zero.
A remains the best AP arm in both sources. An advantage over P alone does not
establish practical improvement, and these data do not demonstrate a useful
stability-specific zero-shot benefit.

**Recommendation: NO-GO for promoting the existing auxiliary EL intervention as
an improved zero-shot immunogenicity predictor.** The final planned evaluation
of existing stability-modified EL checkpoints is complete. No coefficient
search, new variants, model fitting or further benchmark evaluation followed.

## Prospective freeze and scientific distinction

The [protocol](BIGMHC_AUXILIARY_EL_ONLY_ZERO_SHOT_IM_TASK2_33_PROTOCOL.md),
[configuration](../configs/bigmhc_auxiliary_el_only_zero_shot_im_task2_33.json),
[implementation](../src/stability_label_curation/auxiliary_el_only_zero_shot_im.py)
and twelve focused tests were committed as
**`4ed6230`** before any new S/P benchmark prediction or comparison.
This is **EL training → frozen EL classifier → direct immunogenicity ranking**.
No EL→IM transfer, IM fitting/head, learned postprocessing or calibration.
Experimental IM labels are used only for evaluation, not learning or selection.
Both benchmarks were examined with earlier models, including Task 2.32 EL-only
positive weighting. Thus this is **exploratory follow-up, not an untouched blind
confirmatory test**. Existing outcomes/results did not choose these checkpoints,
score transforms, populations, endpoints, coefficient or uncertainty procedure.

S/P here are **Task 2.24 auxiliary-supervised models**, different from Task 2.32's
Task 2.31 positive-weighted W/permuted-weight P models. The historical auxiliary
objective was native EL batch-mean BCE + **0.1 × positive-anchor stability-rank
MSE**. Genuine training-only within-HLA Teacher ranks versus within-HLA-permuted
targets are the intended intervention/control. All original EL labels were
preserved. The auxiliary regression head is **excluded from inference**; only
the original BigMHC EL classification logit and sigmoid are used.

## Exact frozen EL models and matched training evidence

| Arm | Checkpoint under resolved project runs | Canonical filename→SHA256 map digest |
| --- | --- | --- |
| A | `task-2_23-el-multiepoch-baseline/checkpoints/EL_epoch_10` | `d8e3d7d3ac5d08d7f420e00b8032fa875b8b6fec1cd9da6b36d35bca0bec04d1` |
| S | `task-2_24-fully-trained-stability-auxiliary/checkpoints/S_EL_epoch_10` | `48550b057e2ccd1fef2f0ad8a181f34de074da8400bfb8cc74ca67a8f038c089` |
| P | `task-2_24-fully-trained-stability-auxiliary/checkpoints/P_EL_epoch_10` | `3d36692a4514154790a478a783ec665b9cf8d421d4a1268bbdd5917a4a3811c1` |

Maps hash canonical sorted JSON with compact separators. Each of 36 complete EL
backbone tensors is authenticated against its receipt and manifest, strictly
reloaded, checked FP32 and free of forward hooks. Explicit EL paths and
`lineage=None` forbid an IM overlay/fallback. No auxiliary head file is loaded.
Synthetic HLA-A*02:01 `AAAAAAAAA` inference is finite for all arms, and A's
synthetic logit exactly matches Task 2.32. Checkpoint tensors remain unchanged.

The targeted EL-only compatibility receipt authenticates:

- The same **1,308,196 training rows: 63,053 positive, 1,245,143 negative**;
  Task 2.23 validation **145,371: 7,006 positive, 138,365 negative**; eleven original
  exclusion rows remain excluded. No fitting or validation data were rebuilt.
- Original Task 2.23 fitting partition SHA256
  `6b3a6a0c00f86c26e51b84a8df1dd7e81d545117baa871dabd0707edaf89ac00`,
  and ordered fitting binding
  `e8c54a96e82a4add61790a7cbcfad993b33b252a2fc95331746fdd521f3ee12a`.
- Identical initial 36-tensor backbone, seed42, native 1-positive/16-negative
  batches, all ten ordered sampled-batch hashes and full RNG boundaries,
  AdamW defaults/lr5e-5, **63,053 updates per epoch**, ten epochs. S/P add the
  intended auxiliary optimization; native BCE denominator is unchanged.
- Same original BigMHC source `199e890fa69a63646730bcecea0a520e08ca4f02`, native
  peptide preprocessing and exact 414-feature HLA mapping, SHA256
  `cd1fa24fb4c9fc0ee592a3d753458c4e3abed0d5cc4ca76e325aa274df8e900a`.

Only relevant EL receipts were checked. No broad historical audit, training
reexecution, IM training payload access, Teacher scoring or downloads occurred.
Historical A's epoch10 was EL-validation-selected; this evaluation does not
reselect it. Same source populations, backbone and schedules make the intended
auxiliary comparison scientifically compatible.

## Exact fixed evaluation populations

Reuse Task 2.32 ordered identity and separately bound outcome files byte for
byte. No new source extraction, split construction, distance search, deduplication
or eligibility changes. Original Task 2.26/2.25 references remain attached.

| Cohort | N | Positive | Negative | Prevalence / random-ranking AP reference | Unique peptides | Unique peptide–HLA | HLA alleles | Patients | Studies |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| IMPROVE Hamming >=3 | 7788 | 227 | 7561 | 0.029147406266050335 | 6576 | 7750 | 36 | 70 | 3 |
| Published neoepitope primary | 267 | 57 | 210 | 0.21348314606741572 | 265 | 267 | 46 | Unknown | Unknown |

IMPROVE: Borch et al. 2024, DOI `10.3389/fimmu.2024.1360281`, author repository
`SRHgroup/IMPROVE_paper` at `c67094276b52358b5202ad9e5597acd87888ea1d`,
`data.zip` member `data/01_data/01_Validated_neoepitopes.txt`. It measures screened
pMHC multimer T-cell recognition in patient context. Preserve Hamming >=3 to the
frozen fitting/selection sequence union and prior Mendeley exact-peptide exclusion.
The IM-fitting/selection sequence identities are eligibility references only;
these EL models never receive IM-supervised fitting in this task.

Original Task 2.26 freeze SHA256:
`20e45f3740beebc39fd78581afd5da7ff49c59798bfcd505cd3ddfcf2c763557`.
Neoepitope: published BigMHC Mendeley Version4, DOI `10.17632/dvmz6pkzvb.4`,
`im_test.csv`, Task 2.25 **267-row globally EL/IM-fitting-unseen primary cohort**,
not its less restrictive IM-novel cohort. Exact peptide-disjointness is retained;
this source is not a sequence-similarity hard split. Original eligibility freeze:
`663c7dedb42432e1efaebbd151daa9fc8ed4d263430e652505fd83244e72d79a`.
Assay/patient linkage remains unavailable; published prediction columns are never
model inputs. Multi-patient repeated observations are not collapsed.


| Cohort | Ordered source-ID digest | Task 2.32 compact identity-file SHA256 | Outcome-file SHA256 |
| --- | --- | --- | --- |
| IMPROVE | `8118663ebf5c23de8f36a7a7c15aa0247a0609e04ade927657528d2986f6fee9` | `33fbad5f142a93d0803b39800fa3dcb71437320c4134e92594080830b6f26986` | `64ed767d65e4e5f9895b1062f9ff160054d1d29b9b460d7bd3e8037279e31709` |
| neoepitope | `9199c11b764c5e4913068125027c382d8229efc0020af743b37ed75bf6673bf7` | `1927116dc37d0cce108f2ebe852e59562fd35a3a4938644e5f7f54faf8efe71a` | `b109ac92fa243466503dfbd159ed8cce2d8036e128478f9c7509922745c263c4` |

IMPROVE contributing studies: DOI `10.1038/s41467-022-29342-0` (3255 rows,
84 positive,24 patients), `10.1101/2024.03.17.585416` (2034,51,20),
`10.1172/JCI150535` (2499,92,26). Full HLA/patient/study class counts are retained
in the point-metric artifact. HLA-C sequences remain exactly encodable but are
outside the A/B-only EL-fitting allele scope; encoding support does not imply
allele-specific supervised coverage. No allele is removed.

## Inference and complete point results

A's predictions are byte-identical copies from Task 2.32, authenticated through
its pinned output manifest
`e040730097c92b23546533aa3bc8a60739301b6c386c3007bb75778786ccf4c1`.
Exact ordered row identities, input transformation, source, score, FP32 runtime
versions, batch16 and synthetic probe all match. A benchmark inference is not
repeated. The historical Task 2.32 gzip-I/O repair is authenticated through its
completion record; it preserved inference/eligibility/predictions unchanged.

S/P each score 7788 +267 original rows once (487 +17 native batches). Four new
passes produce **16,110** raw-logit/probability pairs; together with reused A,
**24,165** aligned finite pairs in six files. All six were frozen at
**2026-10-22T04:09:28.773434+00:00**, before comparisons. No auxiliary regression
prediction enters a score. Constant-zero schema targets exclude outcomes from
native model inputs. Eval/no-grad, deterministic CUDA FP32, TF32/AMP off.

Every ranking metric uses the same native FP32 sigmoid EL probability; raw logits
are preserved for diagnostics, not alternative performance selection. AP groups
exact ties at one threshold; AUROC gives half-credit to ties. Top-K ordering is
probability descending, then peptide, HLA, study DOI, patient, immutable source ID.
Neoepitope unknown study/patient fields remain empty metadata.


### IMPROVE: N=7788, positive=227, negative=7561

| Metric | A | S | P | S−A | S−P | P−A |
| --- | --- | --- | --- | --- | --- | --- |
| AP | 0.03638362130144917 | 0.03543918286237654 | 0.03376717826224673 | -0.0009444384390726313 | 0.0016720046001298047 | -0.002616443039202436 |
| AUROC | 0.5024228783573484 | 0.49664024815494767 | 0.491435007023638 | -0.005782630202400774 | 0.005205241131309657 | -0.01098787133371043 |
| Precision@10 | 0.1 | 0.0 | 0.0 | -0.1 | 0.0 | -0.1 |
| Precision@20 | 0.05 | 0.05 | 0.0 | 0.0 | 0.05 | -0.05 |
| Prevalence / AP reference | 0.029147406266050335 | 0.029147406266050335 | 0.029147406266050335 | 0.0 | 0.0 | 0.0 |
| AP minus prevalence | 0.007236215035398834 | 0.006291776596326203 | 0.004619771996196398 | -0.0009444384390726313 | 0.0016720046001298047 | -0.002616443039202436 |
| AP / prevalence | 1.2482627431528022 | 1.2158605997012708 | 1.1584968471646588 | -0.03240214345153136 | 0.05736375253661197 | -0.08976589598814333 |

### neoepitope: N=267, positive=57, negative=210

| Metric | A | S | P | S−A | S−P | P−A |
| --- | --- | --- | --- | --- | --- | --- |
| AP | 0.2564378062905638 | 0.24205847026284813 | 0.24099672063653865 | -0.014379336027715656 | 0.0010617496263094772 | -0.015441085654025133 |
| AUROC | 0.5375104427736007 | 0.5336675020885547 | 0.5426065162907269 | -0.0038429406850459813 | -0.008939014202172135 | 0.005096073517126154 |
| Precision@10 | 0.3 | 0.3 | 0.2 | 0.0 | 0.09999999999999998 | -0.09999999999999998 |
| Precision@20 | 0.3 | 0.35 | 0.25 | 0.04999999999999999 | 0.09999999999999998 | -0.04999999999999999 |
| Prevalence / AP reference | 0.21348314606741572 | 0.21348314606741572 | 0.21348314606741572 | 0.0 | 0.0 | 0.0 |
| AP minus prevalence | 0.04295466022314806 | 0.028575324195432406 | 0.02751357456912293 | -0.014379336027715656 | 0.0010617496263094772 | -0.015441085654025133 |
| AP / prevalence | 1.2012086715715884 | 1.1338528343891308 | 1.12887937561326 | -0.06735583718245763 | 0.004973458775870743 | -0.07232929595832838 |

Primary S−A AP is negative, and S's AUROC is also below A on both sources.
S−P AP is weakly positive on both, but S remains below baseline and paired
intervals include zero. This is insufficient evidence for practical benefit or
for a stability-specific predictive effect beyond generic auxiliary learning.

Primary recognized candidates: A **1/10,1/20**, S **0/10,1/20**, P **0/10,0/20**.
Neoepitope: A **3/10,6/20**, S **3/10,7/20**, P **2/10,5/20**. The secondary S
Precision@20 increase does not replace failed primary AP; top-K counts are small.
No point-data K=10/20 boundary tie crosses a cutoff in any arm/source.
No probabilities saturate to exactly0 or1. IMPROVE A/S/P have38/39/41 tied-score
groups involving76/78/82 observations; neoepitope has no exact probability ties.
Full raw/probability distributions and boundary evidence are saved.

## Paired exploratory uncertainty

IMPROVE: **38 frozen patient/peptide connected components**, largest2475 rows and
21 patients. Sample38 components with replacement per draw, retain full original
observation multiplicity paired across A/S/P,10000 draws, local Random(262742),
sorted component IDs. Shared peptides connect all three studies into **one**
study/peptide component: study-level interval **undefined**, zero draws; no
manufactured three-study bootstrap. Neoepitope: **265 peptide clusters**,10000
paired draws, Random(24242). The verifier confirms **all20,000 component
multiplicity streams exactly match Task 2.32** without reanalyzing its old scores.

95% percentile intervals use linear interpolation at(n−1)q. All reported paired
endpoints have10000 usable draws and zero undefined draws in these two streams.
Component count alone does not guarantee that biological dependence is adequately
represented. Known patient/peptide dependence is retained; unknown assay/patient
links and large components limit interpretation. These are exploratory intervals,
not untouched confirmatory significance tests or proof of population generality.


### IMPROVE: paired 95% intervals

| Metric | S−A | S−P | P−A |
| --- | --- | --- | --- |
| AP | [-0.004983567798537955, 0.002885986496589098] | [-0.0006022847156294553, 0.00524406724606626] | [-0.007001796442072671, -0.0002206499983020654] |
| AUROC | [-0.02223584965214637, 0.009528575416211556] | [-0.007653303871524437, 0.018370225816925285] | [-0.025509914478301348, 0.0017619030450497972] |
| Precision@10 | [-0.2, 0.1] | [0.0, 0.1] | [-0.2, 0.0] |
| Precision@20 | [-0.15, 0.1] | [0.0, 0.15] | [-0.19999999999999998, 0.0] |
| Prevalence / AP reference | [0.0, 0.0] | [0.0, 0.0] | [0.0, 0.0] |
| AP minus prevalence | [-0.004983567798537955, 0.002885986496589098] | [-0.0006022847156294553, 0.00524406724606626] | [-0.007001796442072671, -0.0002206499983020654] |
| AP / prevalence | [-0.1865879576179612, 0.0910815792266859] | [-0.021973213583270847, 0.1703222099389388] | [-0.25566721285772, -0.007348462354787048] |

### neoepitope: paired 95% intervals

| Metric | S−A | S−P | P−A |
| --- | --- | --- | --- |
| AP | [-0.060127637669662094, 0.031739084075531505] | [-0.03514546986623497, 0.03657823169148683] | [-0.041851283104257696, 0.010539475662491528] |
| AUROC | [-0.042048488680300596, 0.034980731225296456] | [-0.03908775113694588, 0.022826933612242174] | [-0.020918663977218824, 0.03118212163169536] |
| Precision@10 | [-0.3, 0.2] | [-0.2, 0.30000000000000004] | [-0.30000000000000004, 0.1] |
| Precision@20 | [-0.10000000000000003, 0.2] | [-0.04999999999999999, 0.25] | [-0.15000000000000002, 0.05000000000000002] |
| Prevalence / AP reference | [0.0, 0.0] | [0.0, 0.0] | [0.0, 0.0] |
| AP minus prevalence | [-0.060127637669662094, 0.031739084075531505] | [-0.03514546986623497, 0.03657823169148683] | [-0.041851283104257696, 0.010539475662491528] |
| AP / prevalence | [-0.2938431247922981, 0.1549467877578787] | [-0.17167453160293683, 0.1779648129226452] | [-0.2050678740283628, 0.04954500082995496] |

The S−A and S−P AP/AUROC intervals include zero in both sources. Primary P−A AP's
exploratory interval lies below zero; this does not establish S superiority over
A or a general stability mechanism. No p-value search or biological-row-independent
interval was introduced. Undefined sparse per-HLA endpoints remain explicitly
null and never trigger a changed cohort.

## Descriptive per-HLA results

Exactly Task 2.32's predeclared rule: N>=20,>=5 positive,>=5 negative. IMPROVE has
**20/36** evaluable alleles; S−A AP is positive in10 and negative in10, S−P in11
and negative in9, P−A in7 and negative in13. Neoepitope has **2/46** evaluable
alleles; S−A AP positive in2, S−P positive in1/negative in1. Those two alleles
do not represent the complete pooled cohort. No HLA subset is promoted.
All allele counts, AP/AUROC and predefined contrasts, including null sparse
strata, are preserved in `evaluation/point_metrics.json`.


### IMPROVE: adequately evaluable HLA descriptions

| HLA | N | Positive | A AP | S AP | P AP | A AUROC | S AUROC | P AUROC |
| --- | ---: | ---: | --- | --- | --- | --- | --- | --- |
| HLA-A*01:01 | 251 | 14 | 0.24873022826034774 | 0.24777903817679273 | 0.21856003142809502 | 0.6754068716094033 | 0.6175406871609403 | 0.5907172995780591 |
| HLA-A*02:01 | 616 | 21 | 0.06929166598181923 | 0.05236242208690556 | 0.059599639805389286 | 0.5430172068827531 | 0.5491796718687475 | 0.5583833533413365 |
| HLA-A*03:01 | 474 | 6 | 0.04540146865059447 | 0.09484050883809338 | 0.17807893844679934 | 0.5274216524216524 | 0.5017806267806267 | 0.49928774928774927 |
| HLA-A*11:01 | 153 | 6 | 0.2583597123495256 | 0.29812979418242574 | 0.3138412426148275 | 0.6643990929705216 | 0.7165532879818595 | 0.7528344671201814 |
| HLA-A*24:02 | 379 | 12 | 0.05768313353091577 | 0.051817107818113765 | 0.05991887476848177 | 0.5944595821980018 | 0.5837874659400545 | 0.6085376930063578 |
| HLA-A*26:01 | 243 | 6 | 0.0414011081148827 | 0.03854996860994361 | 0.0363775018045427 | 0.3621659634317862 | 0.510548523206751 | 0.4289732770745429 |
| HLA-A*30:01 | 163 | 6 | 0.1826370273189117 | 0.2254779942279942 | 0.27604789390503676 | 0.8354564755838642 | 0.9182590233545648 | 0.9171974522292994 |
| HLA-A*32:01 | 239 | 6 | 0.032907430224428096 | 0.03343415087937599 | 0.028123602076538527 | 0.4670958512160229 | 0.4792560801144492 | 0.36909871244635195 |
| HLA-B*07:02 | 555 | 8 | 0.016544720423775784 | 0.016563091103362536 | 0.01509029678942891 | 0.5082266910420475 | 0.5139396709323584 | 0.45955210237659966 |
| HLA-B*08:01 | 402 | 7 | 0.129219942676558 | 0.04840945371890916 | 0.05232460796014754 | 0.5301989150090416 | 0.5182640144665461 | 0.5095840867992767 |
| HLA-B*27:05 | 119 | 5 | 0.09002720705507083 | 0.07069917525111519 | 0.07792255789509377 | 0.5456140350877193 | 0.543859649122807 | 0.5035087719298246 |
| HLA-B*35:01 | 225 | 8 | 0.03578027731268153 | 0.03549688422401435 | 0.03251377725003045 | 0.45506912442396313 | 0.42338709677419356 | 0.4084101382488479 |
| HLA-B*35:03 | 91 | 6 | 0.10937077575402654 | 0.11685303946139859 | 0.11615548728451953 | 0.6215686274509804 | 0.6078431372549019 | 0.6411764705882353 |
| HLA-B*38:01 | 390 | 10 | 0.05421426664004987 | 0.053945549580496466 | 0.047173848077712 | 0.5868421052631579 | 0.6013157894736842 | 0.5963157894736842 |
| HLA-B*40:01 | 276 | 13 | 0.0520136713704973 | 0.04924544682082657 | 0.04440835605756879 | 0.4647557765428488 | 0.4521789997075168 | 0.415326118748172 |
| HLA-C*03:04 | 288 | 10 | 0.0883740597996097 | 0.10648560698950367 | 0.08746132502566298 | 0.7039568345323741 | 0.6884892086330935 | 0.6845323741007194 |
| HLA-C*04:01 | 389 | 7 | 0.05313697453120951 | 0.09485328690023817 | 0.04389381454217791 | 0.6716529543754675 | 0.5983545250560958 | 0.6600598354525056 |
| HLA-C*06:02 | 225 | 25 | 0.13695268426453108 | 0.119119141700459 | 0.11611225758734586 | 0.5786 | 0.5216 | 0.5222 |
| HLA-C*07:01 | 556 | 15 | 0.05378140791449566 | 0.09902552354968433 | 0.10488943462205465 | 0.5397412199630314 | 0.5377695625385089 | 0.5599507085643869 |
| HLA-C*07:02 | 275 | 14 | 0.05514664529240518 | 0.0697795978881252 | 0.08410816799322092 | 0.4967159277504105 | 0.48084291187739464 | 0.4480021893814997 |

### neoepitope: adequately evaluable HLA descriptions

| HLA | N | Positive | A AP | S AP | P AP | A AUROC | S AUROC | P AUROC |
| --- | ---: | ---: | --- | --- | --- | --- | --- | --- |
| HLA-A*02:01 | 46 | 5 | 0.09528679653679653 | 0.0973015873015873 | 0.09147727272727274 | 0.3463414634146341 | 0.35609756097560974 | 0.3170731707317073 |
| HLA-B*07:02 | 20 | 5 | 0.2996336996336997 | 0.3376984126984127 | 0.37103174603174605 | 0.56 | 0.6266666666666667 | 0.6933333333333334 |

## Interpretation alongside Task 2.32

Task 2.32's fixed positive weighting gave IMPROVE W−A AP
−0.0022127311472500064 and W−permuted-weight-P AP −0.0018697994365573858;
neoepitope W−A −0.033787140153501344 and W−P0.004885523798472596.
Here auxiliary S−A is also negative in both populations, while S−auxiliary-P is
weakly positive with intervals spanning zero. These are different previously
frozen learning interventions, not interchangeable controls. We did not rerun
Task 2.32 or select the better intervention/subset based on these comparisons.
Neither fixed intervention shows useful zero-shot AP superiority over A.

The known previous Task 2.25/2.27 full-IM analyses used different, subsequently
IM-fitted checkpoint tensors. Their results are not this experiment: no IM
weights, IM head or labels for fitting are present here. The current conclusion
is specifically about direct presentation-score ranking of T-cell recognition.
No historical prediction/result was revised or reanalyzed for model selection.

All A/S/P APs exceed their source's positive-prevalence reference descriptively,
but S AP/prevalence is only1.2158605997012708 on IMPROVE and1.1338528343891308 on
neoepitope, below A1.2482627431528022 and1.2012086715715884. These benchmarks have
very different prevalences and experimental contexts, so absolute AP values are
not a common measure of task difficulty or generalization.

The small S−P AP advantages do not demonstrate useful stability information when
S does not beat A. Secondary top-K/per-HLA patterns are mixed and small-sample.
EL classification estimates presentation-related patterns, not T-cell recognition
or measured pMHC lifetime. Stability auxiliary learning is not a correction of
EL labels; Teacher stability does not measure EL-label error or repeated detection.
Failure here does not prove kinetic stability biologically irrelevant, and the
previous MS association studies do not validate this auxiliary coefficient.

Limitations include previously examined sources, one frozen seed/coefficient,
low primary prevalence, limited effective resampling units, shared peptides and
patient dependence, sparse HLA outcomes, HLA representation outside fitting
alleles, unknown neoepitope assay/patient links, and source/assay differences.
The hard split addresses predefined sequence exposure, not full assay/patient
independence. No broad generalization or confirmatory significance is claimed.
There is no basis to adopt these weights/auxiliary targets as improved zero-shot
IM scoring or to tune them post hoc. Stop after the authorized final evaluation.

## Tests, execution evidence and artifacts

**12/12 focused tests pass**, zero skipped,3.398 seconds on the actual WSL2
GPU environment (unit statistical examples run on CPU). They cover tied-score
AP/AUROC, integer cluster multiplicity versus literal expansion, deterministic
paired streams, gzip draw evidence, classless/one-component undefined handling,
contrast signs, identity/HLA order mismatch, constant-zero native targets,
36-file model/cohort bindings, no optimizer/transfer/auxiliary inference calls,
and stable exclusive serialization. **Preflight PASS**: three strict EL reloads,
finite synthetic forwards, exact A synthetic consistency, training schedule and
encoding compatibility, and both frozen cohorts. No real benchmark endpoint is
calculated by tests.

The first inference launch stopped at `shutil.copyfile` because its output
`predictions/` directory had not been prepared. This occurred **before any real
benchmark model forward, new prediction file or performance calculation**.
The failed start/log/telemetry/failure receipt are preserved. An empty output
directory was created, then the unchanged committed implementation executed the
first four study passes. No scientific code, model, cohort, score or protocol
changed; no benchmark inference or endpoint was repeated. Operational replay
requires preparing the resolved run's empty `predictions/` directory after
preflight and before inference. Evidence: `reports/output_directory_recovery.json`.
This report discloses the setup error rather than claiming an error-free launch.

The read-only [completion verifier](../scripts/verify_auxiliary_el_only_zero_shot_im.py)
passes: exact model files and cohort/outcome associations,24165 finite aligned
pairs, four new/two reused files,20000 correct paired draws matching Task 2.32,
and undefined study-component interval. It invokes no model forward, metric
recalculation or new resampling. The [figure script](../scripts/plot_auxiliary_el_only_zero_shot_im.py)
uses saved endpoints only; PNG/PDF were inspected, with no new scientific test.


| Stage | Elapsed seconds | Peak host RSS bytes |
| --- | --- | --- |
| preflight | 8.645475063007325 | 2203639808 |
| predictions_frozen | 10.326977363030892 | 1918676992 |
| evaluation_completed | 14.674596366006881 | 133914624 |

Inference Torch peak GPU allocation **525777408 bytes**,
reservation **838860800 bytes**. Eleven 1-second device samples
show max used1837MiB, utilization47%, power191.73W; sampled device memory includes
CUDA context/other allocations and is not a process-exclusive peak. Stage times
exclude the initial directory failure and orchestration/idle time.
Python3.13.5, Torch2.13.0+cu130, CUDA13.0, cuDNN92000, NumPy2.5.4,
Linux6.18.33.2-microsoft-standard-WSL2, NVIDIA GeForce RTX4090; deterministic
FP32, CPU threads4, TF32/AMP disabled. Matplotlib3.10.7 runs only in the existing
figure environment. Nothing was installed or downloaded.

All scientific data/checkpoints/outputs remain outside Git under the resolved
project run **`task-2_33-auxiliary-el-only-zero-shot-im/`**:

- `cohorts/`: exact reused identities and bound outcomes.
- `reports/`: original source/model references, matched EL lineage, A compatibility,
  scientific freeze, synthetic reloads, focused checks, prediction receipt,
  completion verifier, resources and the preserved output-directory failure.
- `predictions/`: all six source-associated raw-logit/probability files.
- `evaluation/`: full-precision pooled/per-HLA metrics, contrasts, distributions,
  joined evaluation rows, paired percentile intervals and compressed draw evidence.
- `figures/`: PNG/PDF AP-relative-to-prevalence, AUROC and paired AP intervals.
- `logs/`: focused test log, inference/evaluation output and GPU telemetry.

An output hash manifest and small committed completion receipt authenticate the
final artifacts. Existing model files, prior data and published results are
unchanged. **No training, IM transfer, Teacher retraining/rescoring, tuning,
calibration, alternative epoch/model selection, outcome-based eligibility changes,
new data acquisition, merge or push occurred.** No subsequent experiment started.
