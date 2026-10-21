# Task 2.31 — Stability-based positive upweighting for BigMHC EL

Completed on Z790 WSL2 / RTX 4090, **2026-10-22 JST** (preparation and training
started 2026-10-21). Branch `task/2.31-el-stability-positive-upweighting`, directly
based on approved Task 2.30B commit `143aeea4189257eaa86b042f69559c2ec5dbadb6`.

**The fixed stability-based upweighting did not improve the primary EL endpoint.**
Epoch-10 pooled AP was **0.8787625285463306 for W**, below both original A
(**0.8800377430103999**) and matched permuted P (**0.8820574267974685**).
W−A = **−0.0012752144640693075**; W−P = **−0.0032948982511378233**.
The exploratory paired peptide-group interval includes zero for W−A and is
negative for W−P. This is a negative developmental result for this exact rule,
seed and schedule, not proof that stability has no biological role.

**Recommendation: NO-GO for advancing this weighting rule as an improved model
or to a confirmatory independent EL superiority test on the strength of these
results.** Preserve the negative result; do not tune the coefficient, choose
another epoch or select an HLA subset to rescue it. A separately approved
independent EL benchmark could address generalization, but this experiment
does not provide a positive predictive-utility justification for promoting W.
No subsequent experiment was started.

## Fixed specification and original source populations

The [execution protocol](BIGMHC_EL_POSITIVE_UPWEIGHTING_TASK2_31_PROTOCOL.md),
[configuration](../configs/bigmhc_el_positive_upweighting_task2_31.json),
implementation and focused tests were committed before scientific learning in
`a440d4cbda81fb6ac6dbf6781086ce8dca36d6d6`. Task 2.31 authorizes **EL only** and supersedes historical IM and
preparation-only instructions in reused Task 2.17/2.18 code/documentation.
No model search, early stopping, extra seeds, auxiliary heads or new data source.
All ten epochs are retained; **epoch 10** is final regardless of the curves.
W's higher epoch-9 AP does not replace its prescribed epoch-10 result.

Native BigMHC source commit: `199e890fa69a63646730bcecea0a520e08ca4f02`.
Reuse the exact Task 2.23 split manifest SHA256
`6b3a6a0c00f86c26e51b84a8df1dd7e81d545117baa871dabd0707edaf89ac00`
and authenticated original EL view/provenance. Source-row order, immutable row
IDs, exact peptide/HLA and original binary labels were joined and checked;
no split regeneration, new exclusion or data copying was needed.

| Frozen EL partition | Rows | Positive | Negative | Unique peptides | HLAs |
| --- | ---: | ---: | ---: | ---: | ---: |
| Training | 1,308,196 | 63,053 | 1,245,143 | 1,122,528 | 49 |
| Validation | 145,371 | 7,006 | 138,365 | 124,828 | 47 |

Peptide-sequence and peptide–HLA overlap between partitions are **zero**. The
historical 11 excluded rows (10 positive, one negative) remain excluded; none
were restored or newly removed. Exact peptide disjointness does not exclude
similar sequences or shared motifs. All original training observations remain
eligible. Native stochastic sampling consumes **63,053 positive anchors and
1,008,848 negative exposures per epoch** (1,071,901 row exposures, 63,053 updates
of 17 rows). This sampled negative subset differs from the full eligible
population, exactly as in A; it is not new row deletion or negative reweighting.
Validation scores every original held-out row without resampling.

Validation positive prevalence is **0.048193931389341756** (4.819393138934176%).
This is EL-positive prevalence in this construction, not T-cell recognition
prevalence, cell-surface frequency or repeat-MS detection probability.

## Reused A EL checkpoint and evaluation compatibility

A is **Task 2.23 `checkpoints/EL_epoch_10/`**, not its final IM model. Canonical
SHA256 of the sorted filename-to-file-SHA256 JSON map:
`d8e3d7d3ac5d08d7f420e00b8032fa875b8b6fec1cd9da6b36d35bca0bec04d1`.
All 36 complete tensor files authenticate to the original EL selection receipt.
A was **not retrained**.

All 145,371 saved A prediction identities/labels/order matched the frozen
validation cohort. Original input/evaluation implementation hashes match Task
2.23 byte for byte across the baseline runner, EL runner and shared evaluator.
Torch/NumPy/pandas/psutil versions and GPU runtime/device also match A. Strict
checkpoint reload matches its tensor hashes and a same-batch 16-validation-row
probe matches saved predictions **bitwise**. Consequently the authentic A
validation predictions and native logit-space BCE were reused; no additional
full A scoring was necessary. Compatibility evidence is saved separately.

## Original Teacher binding and training-only ranks

Use the authenticated Task 2.13 score-only sidecar, SHA256
`ab0473b669f61792ff63a926185a5e737544209537c5de938b30e519a232e884`,
with its manifest SHA256
`e79fb60b1c04f33889e9d3ecd6a7bd145255c156487cd4d4873a90c8ab715862`.
It binds original archive/member/source-row ID and raw-row hash, prepared
coordinate, original/resolved HLA, peptide and original positive label.
**All 63,053 training positives are covered**, finite and nonnegative. No
missing/ambiguous binding, unsupported allele or fallback occurred.

Teacher checkpoint SHA256:
`a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99`.
The recovered original per-HLA positional one-hot Ridge predicts log1p kinetic
half-life hours and deploys `expm1(max(0, linear prediction))`. It is not
SPEARMINT or a model of thermal melting or MS label errors. The sidecar's model
identity matches the recovered checkpoint. No new Teacher scoring or fitting
was required. Prior SHERPA/JY detection outcomes never enter model targets or
weights; their weak associations motivate the experiment without validating
this formula or coefficient.

Rank **only the 63,053 training-positive observations** within exact HLA,
using `(strictly below + tied/2)/n`, with original Decimal numeric ties and
exact rational arithmetic. Validation and excluded positives do not contribute
to these references. Repeated original observations, if present, each retain
their contribution. Ranks are fixed once, not per batch or epoch.

| Training-only rank summary | Value |
| --- | ---: |
| Minimum | 0.00012613521695257316 |
| Median | 0.5 |
| Mean | 0.5 |
| Maximum | 0.9999212970250275 |

All 49 per-HLA rank summaries, complete positive identity/rank ledgers and
source score strings are preserved outside Git. No validation rank population
is substituted for the training reference.

## W/P weights, exact invariants and loss semantics

W = `1 + 0.5*max(0,r-0.5)`, implemented as `max(1, historical_two_sided_weight)`.
This reverses Task 2.18's one-sided **downweighting** cap; it does not reuse that
older scientific intervention. Every negative has weight 1, every positive
has weight ≥1, and all labels remain original.

| Positive-weight statistic, identical for W/P | Value |
| --- | ---: |
| Observations | 63,053 |
| Minimum / median | 1.0 / 1.0 |
| Mean | 1.0624997331560029 |
| Maximum | 1.2499606485125139 |
| Exact-arithmetic total, displayed as float | 66993.79567468545 |
| FP32 total | 66993.79567742348 |
| Unit weight / increased weight | 31,541 / 31,512 |
| Decreased weight / removed observations / flipped labels | 0 / 0 / 0 |

The full exact rational total is saved in `reports/weight_permutation.json`.
Relative to A's 63,053 positive mass, W/P add about **6.25%** positive weight.
The maximum is below 1.25 because finite-sample midranks do not reach one.

P uses the original source-ID-ordered descending Fisher–Yates permutation,
with SHA256-domain-separated local per-HLA seed-42 streams. It does not draw
from model/sampler Python, NumPy, Torch CPU or CUDA RNGs. All **49 HLA exact
rational and FP32 weight multisets and masses match**; 47,227 assignments differ
and fixed/tied assignments are accepted without redraw. The number of increased
weights is identical. Per-HLA statistics and assignment hashes are frozen before
GPU training.

Reuse the tested per-example weighted BCE adapter: multiply only the original
positive-anchor term, then take the **actual batch-row mean**, preserving the
native denominator 17. Do not divide by total weight. Negative terms remain
unchanged. CUDA no-op tests confirmed equal native loss/gradients for unit
weights; a separate test confirmed positive-only gradient scaling and the
original denominator.

## Matched training and complete checkpoint reload

W and P each restart from A's original epoch-0 constructor, seed **42**, with
**all 36 initial parameter hashes and post-constructor RNG states equal to A**.
Neither starts from trained A. Both use authentic BigMHC EL, CUDA FP32,
deterministic algorithms, TF32/AMP disabled, four CPU threads and native
`makebats(16,shuffle=True,negfrac=.99)` / native DataLoader order.

AdamW remains persistent across each ten-epoch fit: lr **5e-5**, betas
**(.9,.999)**, eps **1e-8**, weight decay **.01**, amsgrad/maximize/capturable/
differentiable false, foreach/fused unset; native decoupled weight decay true.
These complete settings and updated-parameter order match A.

Before GPU learning all ten native CPU sampling schedules matched A. During
learning **every ordered batch fingerprint was checked before its update**;
per-epoch pre/post RNG boundaries and optimizer/skip schedules matched A.
Each arm executed exactly **630,530 updates**, with all 36 optimizer step
counters continuing through ten epochs. Evaluation/reload preserved all RNGs.
No auxiliary head, architecture change or transfer pathway was used.

Final complete EL checkpoints are new W/P `checkpoints/*_EL_epoch_10/`.
Both passed strict tensor reload and bitwise same-device probe prediction
comparison. Canonical checkpoint file-map hashes:

- W: `a6b24dad431f50f170e1945f7fe9ad366bee323890b9055830cd5e56078a6892`
- P: `53cb323e3e81137713a80a443cd40b8d7c574f6af31525ea3ff6f5d62d4294a9`

No checkpoint or scientific input was overwritten; A/Teacher remain intact.

## Fixed epoch-10 developmental endpoints

Non-interpolated AP groups exact score ties; AUROC gives ties half credit.
BCE uses native all-row logit-space loss divided by original validation N.
Macro AP averages the same 46 HLAs having both original classes. The remaining
validation HLA, B*44:05, has two negatives and no positive: its AP/AUROC are
**undefined**, with no cohort substitution. N and class balance are identical
for A/W/P.

| Arm | Pooled AP | AUROC | Validation BCE | Macro HLA AP |
| --- | ---: | ---: | ---: | ---: |
| A | 0.8800377430103999 | 0.9917155712890559 | 0.04589545446132882 | 0.8241491229223719 |
| W | 0.8787625285463306 | 0.9918610624740409 | 0.04612716631058239 | 0.8285236861350797 |
| P | 0.8820574267974685 | 0.9920737771948012 | 0.045394203876895634 | 0.8432761289703548 |

| Contrast | AP | AUROC | BCE | Macro HLA AP |
| --- | ---: | ---: | ---: | ---: |
| W-A | -0.0012752144640693075 | 0.0001454911849850804 | 0.00023171184925357274 | 0.004374563212707794 |
| W-P | -0.0032948982511378233 | -0.000212714720760232 | 0.0007329624336867568 | -0.014752442835275104 |
| P-A | 0.002019683787068516 | 0.0003582059057453124 | -0.0005012505844331841 | 0.019127006047982897 |

Positive AP/AUROC/macro differences favor the first arm; negative BCE differences
favor it. W's slight AUROC and macro-AP increase over A does not replace the
negative pooled-AP primary result; its BCE is also worse. P has better point
estimates than both on pooled AP, AUROC, BCE and macro AP.

## Paired exploratory uncertainty

The pretraining specification fixed 1,000 paired bootstrap draws, NumPy
`default_rng(23142)`, of the same **124,828 unique validation peptide groups**.
Every observation/HLA of a selected peptide retains the same multiplicity in
A/W/P. The existing exact tied-score integer-multiplicity metric primitive was
reused and validated against expanded synthetic tied observations. No new
predictions or seed/model variants enter resampling.

| Contrast | AP 95% percentile interval | AUROC 95% percentile interval |
| --- | --- | --- |
| W-A | [-0.003855523024050006, 0.0016900462259874817] | [-0.00016344395259077215, 0.00047392556247179694] |
| W-P | [-0.006271954157651041, -0.0004340178792122683] | [-0.00045725399829200377, 1.29447867294713e-05] |
| P-A | [-0.0008410947826295006, 0.005036206985603213] | [2.1357067802749152e-05, 0.0006848341329524277] |

All 1,000 draws were usable; zero undefined draws. W−A AP includes zero; W−P AP
lies below zero in this conditional analysis. P−A AP also includes zero.
No asymptotic p-value, independent-biological significance or across-seed
uncertainty is claimed. Peptide grouping handles exact repeated sequences
across HLA, not unrecorded study/patient dependence, broader sequence families,
training randomness, permutation variability or previous model selection.
This is exploratory internal-validation uncertainty, not an independent test.

## All ten EL epoch histories

All epoch histories and validation predictions are retained. These curves were
not used to select a new epoch; every final comparison uses epoch 10. Table
rounding is display only; full-precision histories remain in run JSON/CSV.

| Epoch | A AP | W AP | P AP | A AUROC | W AUROC | P AUROC |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.843953736 | 0.844273726 | 0.845921844 | 0.988740161 | 0.988756801 | 0.988932061 |
| 2 | 0.857329174 | 0.858423316 | 0.855807378 | 0.990233386 | 0.990153588 | 0.990073783 |
| 3 | 0.868599488 | 0.868471715 | 0.868141525 | 0.991050677 | 0.991107730 | 0.991017140 |
| 4 | 0.872537129 | 0.874212111 | 0.874317143 | 0.991326996 | 0.991580830 | 0.991661775 |
| 5 | 0.871759723 | 0.872930998 | 0.871335215 | 0.991672753 | 0.991775713 | 0.991512079 |
| 6 | 0.876875260 | 0.874248514 | 0.875427351 | 0.991742612 | 0.991585282 | 0.991714758 |
| 7 | 0.876002160 | 0.876348066 | 0.875739894 | 0.991773334 | 0.991893626 | 0.991849596 |
| 8 | 0.878240105 | 0.880214970 | 0.879812150 | 0.991799690 | 0.992254453 | 0.991989750 |
| 9 | 0.882767661 | 0.883833773 | 0.879664073 | 0.992163088 | 0.992232407 | 0.991909076 |
| 10 | 0.880037743 | 0.878762529 | 0.882057427 | 0.991715571 | 0.991861062 | 0.992073777 |

| Epoch | W weighted train-update BCE | P weighted train-update BCE | W validation BCE | P validation BCE |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.078345235 | 0.079305772 | 0.054671260 | 0.054184333 |
| 2 | 0.060247004 | 0.061018463 | 0.051116757 | 0.051766127 |
| 3 | 0.056270244 | 0.057058367 | 0.048715531 | 0.048783795 |
| 4 | 0.054346794 | 0.054979288 | 0.047361120 | 0.047383461 |
| 5 | 0.052760389 | 0.053453340 | 0.046962767 | 0.047524157 |
| 6 | 0.051833251 | 0.052512349 | 0.048072688 | 0.047634005 |
| 7 | 0.051231838 | 0.051765916 | 0.047655076 | 0.046987003 |
| 8 | 0.050472076 | 0.050861450 | 0.045737840 | 0.046266789 |
| 9 | 0.049773835 | 0.050441093 | 0.045883465 | 0.046447924 |
| 10 | 0.049227116 | 0.049610054 | 0.046127166 | 0.045394204 |

Weighted sampled update BCE differs in objective from A's unweighted update
loss; validation BCE is unweighted and directly comparable. Intermediate
validation results triggered no parameter, duration or checkpoint changes.

## Per-HLA consistency and fixed rank diagnostics

W−A per-HLA AP: **25 wins / 21 losses / 0 ties**. W−P: **22 / 24 / 0**.
P−A: **26 / 19 / 1**. These unselected 46-HLA results are mixed; there is no
consistent multi-HLA stability-specific advantage. Macro W−A is positive, but
macro W−P is negative; pooled and macro summaries have different weighting.
Sparse HLA estimates remain included and unstable; none become a new primary.

No established fixed-FPR recall implementation or fixed operating-point
convention exists in the reused EL evaluator. This conditional optional
endpoint is **unavailable/not computed**; no post-result threshold or new
interpolation rule was introduced.

For descriptive validation-positive strata, use the **training** score ECDF
midrank only, fixed r<=.5 versus r>.5. No validation score contributes to the
training rank distribution. Lower/upper counts are **3,541 / 3,465**. Mean
prediction percentile is relative to all 145,371 original validation rows.
Diagnostic positive BCE uses probabilities clipped below at 1e-15; it is
separate from the primary native logit-space validation BCE.

| Arm / training-reference stratum | N | Mean pooled prediction percentile | Mean probability | Diagnostic positive BCE |
| --- | ---: | ---: | ---: | ---: |
| A / lower | 3541 | 0.9589308844158637 | 0.6363629582343768 | 0.7735080364007185 |
| A / upper | 3465 | 0.9773041555425936 | 0.8306694042259138 | 0.26340968184812363 |
| W / lower | 3541 | 0.9588148047872472 | 0.6557952009946473 | 0.7271895722638483 |
| W / upper | 3465 | 0.9777027773581418 | 0.8496761870614578 | 0.22600965780244667 |
| P / lower | 3541 | 0.9592529304472518 | 0.6551761065971176 | 0.7250488789624348 |
| P / upper | 3465 | 0.9776644090902094 | 0.8434005863935747 | 0.23627448170554458 |

W increases the upper-half mean prediction percentile relative to A, while
the lower-half mean percentile declines slightly. Both groups' mean positive
probabilities rise and positive diagnostic BCE decreases, so positive score
fit and rank discrimination should not be conflated. These positive-only
summaries do not establish calibration.
Relative to P, W's upper-half mean percentile is only slightly higher, while
its lower-half mean percentile is lower. These are compatible with a ranking
tradeoff and nonspecific positive-score increases; no stratum test or optimized
cutoff was performed. They do not rescue W's negative primary contrasts.

P's point advantage over A shows that increased positive mass/reallocation or
optimization trajectory can yield changes without correct stability assignment.
It does not prove that mass alone caused the change: one seed and one permutation
cannot identify that mechanism, and P−A's AP interval includes zero. Genuine
stability ranks provide no added predictive utility here; W underperforms P.

## All validation HLA endpoints

Each row retains its original class counts. Rounded display below; full-precision
AP/AUROC and paired contrasts are in `reports/point_estimates.json`. Undefined
means no both-class metric, not an excluded observation.

| HLA | N | Positive | A AP | W AP | P AP | A AUROC | W AUROC | P AUROC |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| HLA-A*01:01 | 1473 | 218 | 0.955474 | 0.951955 | 0.951851 | 0.989799 | 0.988903 | 0.988428 |
| HLA-A*02:01 | 6204 | 730 | 0.839444 | 0.843287 | 0.852789 | 0.975657 | 0.976099 | 0.976300 |
| HLA-A*02:03 | 3028 | 154 | 0.793712 | 0.770351 | 0.826407 | 0.986229 | 0.985664 | 0.988159 |
| HLA-A*02:11 | 5216 | 12 | 0.224126 | 0.271118 | 0.360219 | 0.977373 | 0.982177 | 0.990232 |
| HLA-A*03:01 | 1477 | 187 | 0.914242 | 0.904240 | 0.916730 | 0.986731 | 0.985595 | 0.986610 |
| HLA-A*11:01 | 8734 | 215 | 0.726264 | 0.750013 | 0.732113 | 0.978138 | 0.980569 | 0.978221 |
| HLA-A*23:01 | 5073 | 62 | 0.794080 | 0.795654 | 0.839159 | 0.992716 | 0.992932 | 0.995709 |
| HLA-A*24:02 | 2145 | 303 | 0.914144 | 0.924162 | 0.919282 | 0.986749 | 0.987411 | 0.986856 |
| HLA-A*24:07 | 3272 | 102 | 0.842494 | 0.848186 | 0.846660 | 0.994504 | 0.993607 | 0.994727 |
| HLA-A*25:01 | 1230 | 45 | 0.963760 | 0.964797 | 0.969574 | 0.998425 | 0.998462 | 0.998612 |
| HLA-A*26:01 | 2944 | 75 | 0.929212 | 0.915079 | 0.926570 | 0.997602 | 0.997439 | 0.997820 |
| HLA-A*29:02 | 2915 | 455 | 0.925096 | 0.930436 | 0.926080 | 0.988070 | 0.987553 | 0.987163 |
| HLA-A*30:01 | 2379 | 22 | 0.631987 | 0.614228 | 0.627904 | 0.978169 | 0.991457 | 0.992440 |
| HLA-A*30:02 | 5438 | 7 | 0.320278 | 0.318461 | 0.617732 | 0.998080 | 0.995949 | 0.998080 |
| HLA-A*31:01 | 690 | 57 | 0.809353 | 0.825947 | 0.783045 | 0.977689 | 0.980239 | 0.976913 |
| HLA-A*32:01 | 5290 | 86 | 0.749401 | 0.784243 | 0.762423 | 0.993762 | 0.993835 | 0.993082 |
| HLA-A*33:03 | 6785 | 145 | 0.791251 | 0.796798 | 0.779372 | 0.990964 | 0.991387 | 0.989481 |
| HLA-A*66:01 | 4547 | 11 | 0.350296 | 0.448817 | 0.566623 | 0.996994 | 0.996372 | 0.997835 |
| HLA-A*68:01 | 2182 | 61 | 0.823420 | 0.834025 | 0.842987 | 0.994033 | 0.994110 | 0.994373 |
| HLA-A*74:01 | 5614 | 109 | 0.795519 | 0.803554 | 0.802805 | 0.990454 | 0.991331 | 0.991477 |
| HLA-B*07:02 | 4061 | 501 | 0.925464 | 0.922915 | 0.924985 | 0.990159 | 0.990577 | 0.990298 |
| HLA-B*08:01 | 2081 | 258 | 0.930302 | 0.926899 | 0.922358 | 0.989046 | 0.988814 | 0.988746 |
| HLA-B*15:01 | 5374 | 409 | 0.853944 | 0.852266 | 0.862757 | 0.989205 | 0.988666 | 0.989799 |
| HLA-B*15:02 | 2715 | 161 | 0.865557 | 0.854755 | 0.835406 | 0.990134 | 0.989316 | 0.987962 |
| HLA-B*15:10 | 3755 | 110 | 0.927406 | 0.925947 | 0.913956 | 0.996778 | 0.997271 | 0.996289 |
| HLA-B*15:17 | 4125 | 6 | 0.272645 | 0.329458 | 0.490540 | 0.867929 | 0.957150 | 0.965081 |
| HLA-B*18:01 | 2941 | 77 | 0.927542 | 0.914492 | 0.914405 | 0.997025 | 0.996227 | 0.995996 |
| HLA-B*27:02 | 687 | 92 | 0.977280 | 0.973953 | 0.976777 | 0.997132 | 0.996657 | 0.996949 |
| HLA-B*27:03 | 227 | 31 | 0.975742 | 0.974278 | 0.974031 | 0.984529 | 0.979921 | 0.978934 |
| HLA-B*27:05 | 1798 | 281 | 0.926643 | 0.928598 | 0.926843 | 0.985031 | 0.985620 | 0.985507 |
| HLA-B*35:01 | 1016 | 105 | 0.904169 | 0.906151 | 0.899880 | 0.986660 | 0.987758 | 0.985782 |
| HLA-B*35:03 | 2604 | 103 | 0.934375 | 0.936288 | 0.936972 | 0.996165 | 0.995718 | 0.996200 |
| HLA-B*35:08 | 55 | 6 | 0.905556 | 0.933333 | 0.905556 | 0.982993 | 0.986395 | 0.982993 |
| HLA-B*39:01 | 370 | 54 | 0.996965 | 0.987907 | 0.992230 | 0.999473 | 0.997714 | 0.998652 |
| HLA-B*40:01 | 4405 | 143 | 0.875052 | 0.859433 | 0.846799 | 0.994845 | 0.993905 | 0.993750 |
| HLA-B*41:01 | 168 | 32 | 0.974329 | 0.978280 | 0.976096 | 0.988281 | 0.990809 | 0.990349 |
| HLA-B*42:01 | 7720 | 185 | 0.795394 | 0.801005 | 0.783605 | 0.993488 | 0.993893 | 0.993696 |
| HLA-B*44:05 | 2 | 0 | undefined | undefined | undefined | undefined | undefined | undefined |
| HLA-B*45:01 | 3213 | 70 | 0.856944 | 0.849662 | 0.857886 | 0.993687 | 0.993359 | 0.992596 |
| HLA-B*46:01 | 2150 | 111 | 0.920630 | 0.905436 | 0.919382 | 0.994813 | 0.994185 | 0.994884 |
| HLA-B*51:01 | 1621 | 174 | 0.898468 | 0.906475 | 0.909220 | 0.984327 | 0.985185 | 0.985781 |
| HLA-B*54:01 | 994 | 65 | 0.868507 | 0.862651 | 0.877459 | 0.983257 | 0.983920 | 0.985278 |
| HLA-B*55:01 | 3235 | 71 | 0.836052 | 0.805623 | 0.812628 | 0.995290 | 0.994017 | 0.994453 |
| HLA-B*56:01 | 3328 | 92 | 0.863853 | 0.877911 | 0.873457 | 0.973132 | 0.971516 | 0.972279 |
| HLA-B*57:01 | 2912 | 407 | 0.921462 | 0.922291 | 0.928362 | 0.988999 | 0.989284 | 0.989052 |
| HLA-B*57:03 | 4116 | 239 | 0.800759 | 0.791043 | 0.794813 | 0.985626 | 0.986893 | 0.985913 |
| HLA-B*58:01 | 3062 | 167 | 0.882270 | 0.889689 | 0.883974 | 0.992620 | 0.993234 | 0.992382 |

## Execution, resources, tests and artifacts

Training elapsed **23,597.150765093975 seconds (6.554764101414993 hours)**;
W stage **11,763.70936790196 s**, P **11,826.696208860958 s**. W/P each have
10 ordered histories, 630,530 optimizer updates, complete final checkpoint and
identical reload probe. Bootstrap computation took **6.696137192018796 s**.
Stage wall times include validation and checkpoint work; per-epoch training-loop
times are retained separately. A had no new training and only the 16-row
compatibility probe; Teacher had no new study inference or training.

Peak allocated GPU bytes W/P: **1,963,223,552 / 1,962,152,960**; peak reserved
**2,275,409,920** for both. Process high-water host RSS W/P:
**3,382,403,072 / 3,416,666,112 bytes** (cumulative high-water, not isolated
stage increments). **787** 30-second nvidia-smi samples, zero failures:
mean/max utilization **68.6277001270648 / 82%**, maximum system VRAM
**3,241 MiB**, mean/max power **236.57036848792885 / 249.29 W**, maximum
GPU temperature **60 C**. System VRAM includes non-Torch/display usage and is
distinct from allocator metrics.

Runtime matches historical A: Python **3.13.5**, Torch **2.13.0+cu130**, NumPy
**2.5.4**, pandas **3.0.6**, psutil **7.2.2**, CUDA **13.0**, cuDNN **92000**,
RTX 4090 on Linux WSL2. No dependency installs or downloads. Existing isolated
Matplotlib **3.10.7** generated standalone PNG/PDF figures from saved results,
without model inference or new statistics.

**Seven focused CUDA/unit tests passed**, no skips: training-only exact
ranks/formula/ties, per-HLA permutation and untouched global RNG, invalid/missing
score failure, EL-only configuration, native unit-weight loss/gradient equality,
positive-only scaling with native denominator, and exact weighted tie metrics
against expanded synthetic observations. A benign synthetic-test warning about
conversion of an autograd tensor to scalar is retained in the log; comparisons
passed and it did not affect scientific training. No broad suite/audit was run.

The separate completion verifier passed: all **20** scientific EL epochs,
initial **36** tensors, 49 exact/FP32 HLA multisets, 63,053 weight assignments,
**21 ordered validation prediction files** (145,371 rows each), and final
checkpoint identities/reload receipts. It made no model calls. The unchanged
scientific source/configuration hashes still match preflight. A temporary
console-log move encountered a cross-filesystem rename error; the log was copied
into the run, without rerunning evaluation or changing results.

Run root: resolved project runs /
`task-2_31-el-stability-positive-upweighting/`.

- `processed/training_positive_weights.csv.gz`: source identity, Teacher score,
  exact training-only percentile, W/P exact rational and FP32 assignments.
- `reports/preflight.json`, `cohort_binding.json`, `weight_permutation.json`,
  `sampler_preflight.json`, `initialization.json`: pre-update safeguards.
- `reports/A_EL_checkpoint.json`, `A_inference_pathway_compatibility.json`:
  explicit original EL model and compatible reused prediction references.
- `reports/[WP]_EL_epoch_*.json`, `*_EL_metrics_*.json`, `*_EL_learning_curve.json`:
  all epochs, every ordered batch/skip fingerprint, losses and RNG/optimizer state.
- `checkpoints/[WP]_EL_epoch_10/` and corresponding final receipts: complete
  frozen EL-only models and strict reload evidence.
- `predictions/`: original A epoch-10 and all ten W/P original-coordinate
  validation predictions, with unchanged labels and exact source binding.
- `reports/point_estimates.json`, `paired_peptide_bootstrap.json`,
  `bootstrap_draws.json`: full-precision endpoints, contrasts, all HLA values,
  strata, interval settings and draw statistics.
- `reports/resource_summary.json`, `completion_verification.json`, `logs/`:
  actual execution, focused checks, training console and GPU samples.
- `figures/EL_positive_upweighting.png` and `.pdf`: all-epoch AP/AUROC curves,
  paired AP intervals and all-evaluable-HLA contrast scatter.

## Scientific interpretation and stopping point

This developmental experiment does **not** support the primary claim that the
fixed high-stability-positive upweighting improves EL prediction. W fails both
pooled-AP comparisons, with mixed HLA directions. Secondary AUROC/macro gains
relative to A and upper-half rank changes do not justify promoting another
endpoint, subset, epoch or coefficient. P's stronger point estimates caution
against attributing generic positive-weight effects to true stability ranking.

A's ten-epoch duration was previously selected on this very validation set;
there is prior model-selection exposure even though W/P duration was fixed
prospectively here. Constructed decoys, sequence-only disjointness, shared HLA/
motif/source structure, uncertain Teacher generalization, one seed/permutation
and unobserved study/patient dependence limit inference. Excellent EL AP against
these decoys does not establish accuracy on independent natural presentation,
MS replicate detection or T-cell recognition. Paired peptide intervals do not
eliminate these limitations.

The preceding SHERPA and JY associations concern weak predicted-stability/MS
repeat-detection associations, not correctness of EL labels or validation of
this optimization rule. Their positive direction can coexist with a negative
learning intervention result. Low-stability EL-positive observations remain
experimental positives; none were labeled false, removed or turned negative.

No IM training, EL→IM transfer, immunogenicity benchmark evaluation, Teacher
retraining, label flipping, positive downweighting, extra seed/epoch, calibration,
checkpoint selection, outcome-based hyperparameter/subgroup change, merge or
push occurred. Stop after this controlled EL-only comparison; no independent
benchmark, alternative coefficient or follow-up learning experiment is started.
