# Task 2.27 — Frozen IMPROVE hard-split A/S/P evaluation

**Completed once on Z790 WSL2 / RTX 4090, 2026-10-20.** Stability-supervised S
has lower primary AP than baseline A and slightly higher AP than permuted P.
Both principal paired AP intervals include zero. This benchmark provides no
evidence of a useful stability-specific improvement over the original BigMHC.

Branch: `task/2.27-third-party-hard-split-evaluation`, based directly on approved
Task 2.26 commit `ee57cb89a3311b1bc7b736d69770be192085c5d1`, regardless of main.
The evaluation implementation and synthetic tests were committed as
`7ce877b` before preflight, inference and outcome association. The final report
commit is recorded by `reports/finalization_manifest.json` outside Git.
No previous result, checkpoint or locked protocol was modified.

## Authority and immutable benchmark

The [locked Task 2.27 protocol](BIGMHC_THIRD_PARTY_EVALUATION_TASK2_27_PROTOCOL.md)
remains authoritative, SHA256
`6139b8a850224781d71768949f6a138ebdfdc111547222cd4ba1c935649df0c9`.
The researcher explicitly authorized GPU inference and evaluation, with no training.

Source: Borch et al., [IMPROVE, Frontiers in Immunology (2024)](https://doi.org/10.3389/fimmu.2024.1360281),
authors' repository at `c67094276b52358b5202ad9e5597acd87888ea1d`.
The already acquired archive is
`improve_paper/data.zip` under resolved project data; member
`data/01_data/01_Validated_neoepitopes.txt`.
[Original archive URL](https://raw.githubusercontent.com/SRHgroup/IMPROVE_paper/c67094276b52358b5202ad9e5597acd87888ea1d/data.zip).
Archive SHA256: `adf02eb5054a8aa4b6eccd3b6e0ff1200889d41ae05655fd6e55c5c347f720d9`;
member SHA256: `b27854c98a34b6bb83af248979cc3ea121534fa2e8d9e97415654dc0c0a95c95`.
Task 2.26 authenticated the archive and experimental interpretation; Task 2.27
reused its provenance and completed distance-witness verification, without
redownloading, rebuilding the split or auditing unrelated historical artifacts.

The endpoint is experimentally measured DNA-barcoded pMHC multimer **T-cell
recognition**, summarized by the authors across available patient materials.
The actual assayed mutant peptide and associated folded HLA are retained; no
predicted core or genotype-imputed restriction is substituted. Screen negatives
mean not recognized in the tested patient context. They are neither untested
synthetic negatives nor evidence of universal absence of immunogenicity. The
endpoint does not directly establish cytokine function or endogenous presentation.

Task 2.26's `reports/benchmark_freeze.json` SHA256 is
`20e45f3740beebc39fd78581afd5da7ff49c59798bfcd505cd3ddfcf2c763557`.
Primary identity-manifest SHA256 is
`bd555e21e3ce16ea0aafe9b4dbc8f5ed88548cc366d07c8160ba222ba9fb74ed`.
Its separate outcome-manifest SHA256 is
`64ed767d65e4e5f9895b1062f9ff160054d1d29b9b460d7bd3e8037279e31709`.
Every original row locator, raw-row hash, peptide/HLA, patient/study, outcome and
threshold-specific component membership is unchanged. Original observations
remain distinct; repeated patient-specific measurements are not deduplicated.

The original source contains 17,520 rows (467 positive, 17,053 negative).
There are 10,561 compatible assayed 9-mers (308 positive, 10,253 negative);
6,959 non-9-mers were excluded in Task 2.26. The primary excludes 2,773 candidates
at minimum distance <3, with zero further primary exclusions from prior-test
exact matches. The ≥2 diagnostic has one additional prior-test exclusion.
No eligibility was reconsidered during Task 2.27.

## Populations and sequence exposure

| Frozen population | N | Positive | Negative | Prevalence / AP reference | Unique peptides | Unique pMHC | HLAs | Patients | Studies |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| Hamming ≥3 — PRIMARY | 7788 | 227 | 7561 | 0.029147406266050335 | 6576 | 7750 | 36 | 70 | 3 |
| Hamming ≥2 — diagnostic | 9303 | 266 | 9037 | 0.028592927012791574 | 7828 | 9238 | 36 | 70 | 3 |
| Hamming ≥4 — diagnostic | 892 | 29 | 863 | 0.032511210762331835 | 757 | 889 | 35 | 70 | 3 |

Primary prevalence is **2.9147406266050335%**. Its minimum-distance distribution
is 6,896 observations at distance 3 and 892 at distance 4. The distance rule
uses the frozen union of actual fitting and selection/development sequences:
1,308,196 EL fitting rows, all 3,428 IM fitting rows, 145,371 EL validation rows,
and historical IM development/epoch-selection identities. The fitting/selection
9-mer union contains 1,250,989 unique sequences. No primary peptide is an exact,
one-substitution or two-substitution neighbor of that union. Exact peptide and
peptide–HLA overlaps with those fitting/selection sets are consequently zero.
All thresholds exclude exact peptide overlaps with the original published
Mendeley benchmark; prior benchmark exposure remains distinct from fitting.

This is the specified ungapped nine-position Hamming split, not a guarantee of
all biological independence. Primary still has 109 rows sharing a shifted
contiguous 8-mer with EL fitting, one with IM fitting and 18 with EL selection;
four primary rows are distance 2 from the prior benchmark. These frozen
descriptive characteristics do not create additional exclusions.

## Models and common IM inference

| Arm | Frozen final IM checkpoint under resolved project runs | Canonical file-map SHA256 |
| --- | --- | --- |
| A | `task-2_23-el-multiepoch-baseline/checkpoints/final_all_IM` | `b92308ab3e35d02530867053ada7e29ee18076bf653df26458f5c3728a2be3a0` |
| S | `task-2_24-fully-trained-stability-auxiliary/checkpoints/S_IM_epoch_20` | `9d5a5012d38b0f7f7203c35769a5a29e35572ced3b8f708a525c03a99996862a` |
| P | `task-2_24-fully-trained-stability-auxiliary/checkpoints/P_IM_epoch_20` | `01014a37c3a4101f90d7765e48420a463a7094169a8c0163fc5994dc4a0c903b` |

Every model is EL-10 / full-IM-20, with 36 native backbone tensors. S uses genuine
Teacher-derived within-HLA rank auxiliary supervision and P its within-HLA
permutation, both coefficient 0.1 during the already completed training. No
auxiliary regression head or hook was loaded during this inference.

All checkpoint files and expected tensor hashes authenticated before use;
strictly reloaded states matched exactly and were unchanged after inference.
All arms shared the pinned authentic BigMHC source, identical exact HLA encoding,
native input transformation, batch16, eval mode, original sigmoid IM outputs,
deterministic CUDA FP32, AMP/TF32 off. All 36 union HLAs have exact mappings;
there was no nearest-HLA fallback. Target input was a constant zero placeholder.

As prescribed, **each arm ran once on the same ordered 9,303-row ≥2 union**, in
582 native batches. Primary ≥3 and diagnostic ≥4 use their frozen source-ID
memberships, without rescoring. All scores were finite full-FP32 probabilities;
native emitted source order and peptide/HLA identities matched the frozen inputs.
The common ordered-source-ID digest is
`c379412d78916c957ece4d3a36a1022d483dcbf571b5cea447b338100d6d97f7`.
The primary subset order digest is
`8118663ebf5c23de8f36a7a7c15aa0247a0609e04ade927657528d2986f6fee9`.

All three prediction files were frozen at **2026-10-20T04:50:50.277627+00:00**.
Outcome association began at **2026-10-20T04:50:56.103799+00:00**, after authenticating all
three prediction hashes. No outcome values were parsed by preflight or inference.


## Full-precision point estimates

AP is non-interpolated, grouping exactly tied scores at one threshold; AUROC
gives half credit to positive/negative score ties. Top-K ties use canonical
peptide, canonical HLA, study DOI, patient ID, then immutable source locator.
Prevalence is the prespecified descriptive random-ranking AP reference, not a
finite-sample randomization test or a claim of statistically above-random ranking.
All contrasts are paired on identical observations.

### Primary Hamming ≥3: N=7,788; 227 positive, 7,561 negative

| Endpoint | A | S | P | S−A | S−P | P−A |
| --- | --- | --- | --- | --- | --- | --- |
| AP | 0.03449836644306334 | 0.03330451972805489 | 0.032810995993973115 | -0.0011938467150084467 | 0.0004935237340817772 | -0.0016873704490902239 |
| AUROC | 0.5166507705027014 | 0.5074684781107783 | 0.5031290292697222 | -0.00918229239192303 | 0.004339448841056082 | -0.013521741232979112 |
| Prevalence / random-ranking AP reference | 0.029147406266050335 | 0.029147406266050335 | 0.029147406266050335 | 0.0 | 0.0 | 0.0 |
| AP minus prevalence | 0.005350960177013003 | 0.004157113462004557 | 0.0036635897279227794 | -0.0011938467150084467 | 0.0004935237340817772 | -0.0016873704490902239 |
| AP / prevalence | 1.1835827218439527 | 1.1426237869695661 | 1.1256917920751657 | -0.04095893487438662 | 0.01693199489440045 | -0.05789092976878707 |
| Precision@10 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| Precision@20 | 0.0 | 0.0 | 0.05 | 0.0 | -0.05 | 0.05 |

### Diagnostic Hamming ≥2: N=9,303; 266 positive, 9,037 negative

| Endpoint | A | S | P | S−A | S−P | P−A |
| --- | --- | --- | --- | --- | --- | --- |
| AP | 0.033519291531807736 | 0.03254371254483161 | 0.03233972212127895 | -0.0009755789869761236 | 0.00020399042355265934 | -0.001179569410528783 |
| AUROC | 0.5125890137538157 | 0.5046479760317025 | 0.5014813785598221 | -0.007941037722113187 | 0.003166597471880417 | -0.011107635193993604 |
| Prevalence / random-ranking AP reference | 0.028592927012791574 | 0.028592927012791574 | 0.028592927012791574 | 0.0 | 0.0 | 0.0 |
| AP minus prevalence | 0.004926364519016162 | 0.003950785532040039 | 0.0037467951084873795 | -0.0009755789869761236 | 0.00020399042355265934 | -0.001179569410528783 |
| AP / prevalence | 1.1722931169940127 | 1.1381735255810845 | 1.1310392289257822 | -0.034119591412928196 | 0.007134296655302297 | -0.04125388806823049 |

### Diagnostic Hamming ≥4: N=892; 29 positive, 863 negative

| Endpoint | A | S | P | S−A | S−P | P−A |
| --- | --- | --- | --- | --- | --- | --- |
| AP | 0.04686472453951235 | 0.041693252268613715 | 0.03517651362041012 | -0.005171472270898633 | 0.006516738648203596 | -0.01168821091910223 |
| AUROC | 0.5121668597914253 | 0.47692492108522794 | 0.4679745874455588 | -0.03524193870619735 | 0.008950333639669128 | -0.04419227234586648 |
| Prevalence / random-ranking AP reference | 0.032511210762331835 | 0.032511210762331835 | 0.032511210762331835 | 0.0 | 0.0 | 0.0 |
| AP minus prevalence | 0.014353513777180513 | 0.00918204150628188 | 0.0026653028580782834 | -0.005171472270898633 | 0.006516738648203596 | -0.01168821091910223 |
| AP / prevalence | 1.4414942858360351 | 1.2824269318483943 | 1.0819810396346838 | -0.15906735398764082 | 0.20044589221371045 | -0.3595132462013513 |

These overlapping diagnostics do not replace the primary. No diagnostic
Precision@K, new HLA subset endpoint or patient/study performance subset was added.
All point endpoints are defined; no cohort was altered to obtain a defined value.
None has N<20 or fewer than five observations in either class.

### Score ties

| Threshold | A tied groups / observations | S tied groups / observations | P tied groups / observations |
| --- | --- | --- | --- |
| ≥3 | 39 / 78 | 39 / 78 | 38 / 76 |
| ≥2 | 67 / 135 | 65 / 131 | 64 / 129 |
| ≥4 | 3 / 6 | 3 / 6 | 3 / 6 |

No primary Precision@10 or Precision@20 boundary crosses a tied-score group in
any arm. Exact tie-group and boundary-score metadata are retained in point metrics.

## Prescribed paired uncertainty

The primary analysis used exactly 10,000 paired component draws and local
`Random(262742)`, draw-major cohort order ≥3, ≥2, ≥4. Components are the frozen
connected components sharing patient (namespaced by study) OR canonical peptide.
Within each cohort its fixed number of components was sampled with replacement,
retaining every observation with multiplicity and identical resampled rows for
all arms, endpoints and contrasts. IDs were ordered lexicographically before
sampling. Integer row multiplicities implement literal expanded samples, as
validated by synthetic brute-expansion tests. Every draw's component
multiplicities is saved; no bootstrap rerun or alternative seed was used.

95% percentile intervals use sorted linear interpolation at `(n−1)q`, q=.025/.975.
Patient/peptide component counts are **38 primary, 28 at ≥2, 65 at ≥4**. All
10,000 draws were usable for every prescribed endpoint in these analyses;
undefined draws were zero. They meet the protocol's 20-unit/1,000-usable-draw
rule, but uneven component sizes, sparse outcomes and only three studies remain
substantial limitations. Primary's largest unit has 2,475 observations from 21
patients, so 7,788 observations do not represent 7,788 independent units.

### Primary patient/peptide 95% intervals

| Endpoint | A | S | P | S−A | S−P | P−A |
| --- | --- | --- | --- | --- | --- | --- |
| AP | [0.02685354346376892, 0.04224231163968397] | [0.026274312694082952, 0.04122338280307754] | [0.025817162586100388, 0.039693077626995296] | [-0.004234143925364701, 0.002984451260674441] | [-0.0017819622356873071, 0.0033598924037263563] | [-0.00433915756218162, 0.0010275843754027232] |
| AUROC | [0.4549857535822895, 0.5649003704106501] | [0.4420871200623085, 0.5562697075017783] | [0.4388327190052143, 0.551992996466078] | [-0.0278454997478673, 0.008494554546891539] | [-0.008470173647708412, 0.015129188898725965] | [-0.02734698629369455, 0.0008679351994541635] |
| Prevalence / random-ranking AP reference | [0.023924055795010155, 0.03743470382479529] | [0.023924055795010155, 0.03743470382479529] | [0.023924055795010155, 0.03743470382479529] | [0.0, 0.0] | [0.0, 0.0] | [0.0, 0.0] |
| AP minus prevalence | [-0.0016468126289841318, 0.013871084026832032] | [-0.0022781115637306036, 0.011772562357647044] | [-0.00269978433581082, 0.010318903480678477] | [-0.004234143925364701, 0.002984451260674441] | [-0.0017819622356873071, 0.0033598924037263563] | [-0.00433915756218162, 0.0010275843754027232] |
| AP / prevalence | [0.9500328087942784, 1.5235436083635348] | [0.9308696622818853, 1.4343877809528844] | [0.9169846260467132, 1.3888275843197262] | [-0.14822392779140184, 0.09744575118018414] | [-0.05989274774367154, 0.11209627987485188] | [-0.15965548133440866, 0.03381778561408927] |
| Precision@10 | [0.0, 0.1] | [0.0, 0.1] | [0.0, 0.1] | [-0.1, 0.0] | [-0.1, 0.0] | [0.0, 0.0] |
| Precision@20 | [0.0, 0.1] | [0.0, 0.15] | [0.0, 0.1] | [-0.1, 0.1] | [-0.1, 0.1] | [0.0, 0.1] |

### Diagnostic ≥2 patient/peptide 95% intervals

| Endpoint | A | S | P | S−A | S−P | P−A |
| --- | --- | --- | --- | --- | --- | --- |
| AP | [0.030190495666710445, 0.0479702537393273] | [0.02894460793806897, 0.04783317535496289] | [0.028732480979625327, 0.04683959439755117] | [-0.004027772195549061, 0.0036381230552316323] | [-0.0024379963180984495, 0.0032447400756945247] | [-0.003529992276773386, 0.0023396443319624277] |
| AUROC | [0.46111689428622826, 0.5400529268540244] | [0.44099514650508526, 0.5345534861521685] | [0.4368993638951112, 0.5313606739130797] | [-0.03472431327097587, 0.005430774184839666] | [-0.009832025773154063, 0.017762096726865833] | [-0.03469656223966714, -0.0015367429038128707] |
| Prevalence / random-ranking AP reference | [0.023856939580268292, 0.04688389994157757] | [0.023856939580268292, 0.04688389994157757] | [0.023856939580268292, 0.04688389994157757] | [0.0, 0.0] | [0.0, 0.0] | [0.0, 0.0] |
| AP minus prevalence | [-0.0024503231729737997, 0.008869468731009989] | [-0.004281334647236557, 0.008146907015231904] | [-0.004544861435866734, 0.007618885580388116] | [-0.004027772195549061, 0.0036381230552316323] | [-0.0024379963180984495, 0.0032447400756945247] | [-0.003529992276773386, 0.0023396443319624277] |
| AP / prevalence | [0.9364898606616058, 1.360554211442073] | [0.8938344304524208, 1.3129938899907814] | [0.8888855992854316, 1.2995081430955513] | [-0.10854401637367855, 0.09712508104701799] | [-0.06697785552450716, 0.08888051974525037] | [-0.10014808030453479, 0.06552548433240009] |

### Diagnostic ≥4 patient/peptide 95% intervals

| Endpoint | A | S | P | S−A | S−P | P−A |
| --- | --- | --- | --- | --- | --- | --- |
| AP | [0.028349720987736433, 0.09542484395794719] | [0.02464736876062021, 0.08549655224210143] | [0.02280684569434034, 0.06145285587820733] | [-0.020558009159720565, 0.005930063067796529] | [-0.004578308108681543, 0.03356434819582661] | [-0.042823849924806826, -0.0009340357771265594] |
| AUROC | [0.40703292623544435, 0.6532258674315508] | [0.36774128917802035, 0.6227295548889987] | [0.36109836265473866, 0.6110280614367122] | [-0.0770723026215805, 0.01623478740210312] | [-0.018770480084961155, 0.04977495472829722] | [-0.0827695673099262, -0.008921693147837416] |
| Prevalence / random-ranking AP reference | [0.01920728897619654, 0.050143189547163035] | [0.01920728897619654, 0.050143189547163035] | [0.01920728897619654, 0.050143189547163035] | [0.0, 0.0] | [0.0, 0.0] | [0.0, 0.0] |
| AP minus prevalence | [-0.00236700520655731, 0.06483431936835951] | [-0.007254111504418211, 0.05802565300843143] | [-0.007308100663255975, 0.029935067692883954] | [-0.020558009159720565, 0.005930063067796529] | [-0.004578308108681543, 0.03356434819582661] | [-0.042823849924806826, -0.0009340357771265594] |
| AP / prevalence | [0.9346714699535222, 3.526683003558286] | [0.8222228941949414, 3.357717352348937] | [0.8141564704234193, 2.1978420826503084] | [-0.6566913073714601, 0.2236698741855815] | [-0.13887493707254697, 1.359108215634608] | [-1.5511699076334156, -0.029214627247912805] |

### Study/peptide sensitivity

Exactly 10,000 paired draws used the separate `Random(262743)` stream and the
same fixed cohort order and frozen study-OR-peptide components. Single-unit
cohorts still consumed their fixed-order RNG draws; **no interval was computed**
for primary or ≥2, each with only one connected study component. Shared peptides
connect all three studies. A row-level or ordinary three-study bootstrap was
not substituted.

At ≥4 there are just two components: bladder, 374 observations / 14 positive,
and connected Basket+melanoma, 518 observations / 15 positive. Both contain
both outcome classes; all 10,000 draws were usable, zero undefined. Every ≥4
study interval is explicitly **unreliable** because two units are fewer than 20.
They are descriptive sensitivity evidence and cannot support generalization
across studies or replace patient/peptide uncertainty.

### Diagnostic ≥4 study/peptide 95% intervals — unreliable

| Endpoint | A | S | P | S−A | S−P | P−A |
| --- | --- | --- | --- | --- | --- | --- |
| AP | [0.03616167522214014, 0.08618983762802863] | [0.03440276094204485, 0.07270079920468896] | [0.031049033419952136, 0.050799075181204065] | [-0.013489038423339678, -0.0017589142800952876] | [0.0033537275220927136, 0.021901724023484892] | [-0.03539076244682457, -0.005112641802188001] |
| AUROC | [0.3678571428571429, 0.655533465871438] | [0.35575396825396827, 0.6006626905235255] | [0.3476190476190476, 0.5878064943671305] | [-0.054870775347912515, -0.012103174603174616] | [0.008134920634920662, 0.012856196156394994] | [-0.06772697150430751, -0.020238095238095277] |
| Prevalence / random-ranking AP reference | [0.02895752895752896, 0.0374331550802139] | [0.02895752895752896, 0.0374331550802139] | [0.02895752895752896, 0.0374331550802139] | [0.0, 0.0] | [0.0, 0.0] | [0.0, 0.0] |
| AP minus prevalence | [-0.0012714798580737638, 0.05723230867049968] | [-0.0030303941381690513, 0.04374327024716] | [-0.006384121660261765, 0.021841546223675106] | [-0.013489038423339678, -0.0017589142800952876] | [0.0033537275220927136, 0.021901724023484895] | [-0.03539076244682457, -0.005112641802188001] |
| AP / prevalence | [0.966033323791458, 2.9764223927545888] | [0.9190451851660554, 2.5106009325352585] | [0.8294527499330071, 1.7542613962575804] | [-0.46582146021933024, -0.04698813862540263] | [0.08959243523304827, 0.7563395362776781] | [-1.2221609964970084, -0.1365805738584509] |

## Patient, study and HLA composition

| Primary source study | DOI | Patients | N | Positive | Negative |
| --- | --- | ---: | ---: | ---: | ---: |
| Basket | `10.1101/2024.03.17.585416` | 20 | 2034 | 51 | 1983 |
| bladder | `10.1038/s41467-022-29342-0` | 24 | 3255 | 84 | 3171 |
| melanoma | `10.1172/JCI150535` | 26 | 2499 | 92 | 2407 |

The primary spans 81 released Sample identifiers and all 70 patients. Primary
HLA-A/B/C counts are 2,909 / 2,826 / 2,053; exact representation is distinct from
training support, because fitting views were A/B restricted. HLA-C and sparse
allele-specific positive counts are material distribution differences. Exact
HLA and patient/study class summaries for every stratum are in point metrics.

There are 38 repeated primary pMHC groups / 38 excess rows across distinct
patients and 950 repeated-peptide groups / 1,212 excess rows. Fifty-two peptide
groups have differing outcomes across HLA/patient contexts. No same-patient
pMHC duplicate, mixed-outcome same-pMHC group or conflicting original ID occurs
in primary. These original observations were retained, with shared peptide and
patient dependence addressed by the prescribed connected-component bootstrap.

The source has screened candidate selection, PBMC/TIL and infusion-product
context differences and an authors' any-sample response summary. Complete
upstream assay/patient linkage against BigMHC fitting and previous external data
is unavailable. Third-party release provenance and verified sequence separation
do not establish strict assay-level or patient-level independence. Mutation
families and shifted cores can remain despite the specified Hamming split.

## Scientific interpretation

1. **S does not exceed A on primary AP:** S−A is
   −0.0011938467150084467 (−0.11938467150084467 percentage points).
   The paired 95% interval [−0.004234143925364701, 0.002984451260674441]
   includes zero; neither superiority nor inferiority is established.
2. **S exceeds P only in its point estimate:** S−P is
   0.0004935237340817772 (+0.04935237340817772 percentage points), with
   interval [−0.0017819622356873071, 0.0033598924037263563]. This does not
   establish a directional stability-specific effect or practical improvement
   when S does not outperform A.
3. With prevalence 0.029147406266050335, S AP is 1.1426237869695661 times
   prevalence and 0.004157113462004557 above it. A is 1.1835827218439527
   times prevalence and has the largest AP. These modest descriptive lifts and
   near-0.5 AUROCs indicate limited ranking separation in this screened context.
   A/S retrieve zero positives among the first 10 and 20 observations; P retrieves
   one among the first 20. Top-K outcomes are highly discrete at this prevalence.
4. AP ordering **A>S>P** persists at predefined ≥2 and ≥4. Both diagnostic S−A
   and S−P patient/peptide AP intervals include zero. The ≥4 cohort has only 29
   positives and wide intervals; its larger S−P point difference cannot promote
   that threshold to primary. Some diagnostic P−A intervals exclude zero
   (≥4 AP/AUROC and ≥2 AUROC); these are prespecified descriptive comparisons,
   without a multiplicity-adjusted superiority claim.
5. This agrees in direction with the already documented
   [Task 2.25 result](BIGMHC_INDEPENDENT_NEOEPITOPE_TASK2_25.md):
   primary AP A=0.2551935661411448, S=0.24661434811487393,
   P=0.23544913269789144; S−A=−0.008579218026270874,
   S−P=0.011165215416982482, both principal AP intervals spanning zero.
   Those historical values are quoted from its committed report, without opening
   or reanalyzing historical predictions. Different assay/candidate populations
   and positive prevalences prevent comparing raw AP as if it were the same test.
6. Dependence and composition are addressed by the frozen paired component
   analysis and descriptive summaries, not additional performance subsets.
   These results cannot establish that patient/study composition explains the
   small S−P difference: primary study uncertainty is unavailable, and repeated
   observations and uneven components leave limited independent information.
   No new subset analysis was introduced to find an explanation.

The evidence does not show a useful stability-specific benefit, or a beneficial
generic auxiliary-learning effect over A, on this benchmark. It measures model
ranking of observed pMHC recognition in screened patient contexts, not universal
T-cell immunogenicity or kinetic half-life itself. Teacher supervision does not
turn this screen into a kinetic-stability measurement, a thermal-melting
measurement, a test of EL-label errors or a measure of repeated mass-spectrometry
detection. No broad generalization, statistical significance of a stability
benefit, or equivalence of the three arms is claimed.

## Execution, tests and resources

The [evaluation implementation](../src/stability_label_curation/third_party_evaluation.py)
uses the existing authenticated native inference pathway. Its stages require a
clean committed task branch and exclusive stage-start/output files, preventing
accidental repeated inference/evaluation. Imports and path resolution do not
create files. Existing NumPy is used for equivalent multiplicity arithmetic;
no dependency was added.

**16 focused unittest cases passed, zero failures/skips**, including seven new
synthetic tests and nine existing ranking/cluster tests. Coverage includes exact
ties, AP/AUROC agreement with independent code, top-K study/patient/source order,
weighted-vs-expanded samples, fixed seeded paired draws, entire-component
multiplicity, unavailable one-unit study intervals and undefined single-class
draws. No scientific artifact is read by these test cases.

Focused preflight passed; live strict reload, unchanged tensors, common native
ordered inputs, 36 exact HLAs and finite outputs passed for all three arms.
The completion verifier passed using saved hashes/order/chronology and model
identities, **without repeating inference, metrics, bootstrap, distance search or
historical evaluation**. It reused Task 2.26's 62,139 distance-witness checks.

Runtime: Python 3.13.5, Torch 2.13.0+cu130, CUDA 13.0, cuDNN 92000, NumPy 2.5.4,
Linux 6.18.33.2 Microsoft WSL2, NVIDIA GeForce RTX 4090. Deterministic FP32,
four CPU threads, AMP and both TF32 modes disabled.

| Resource | Observed value |
| --- | --- |
| Focused preflight wall time | 1.4551784369978122 s |
| Inference stage wall time, including all three arms and freeze | 15.136093848966993 s |
| A / S / P arm wall times | 3.6975326699903235 / 3.536817834014073 / 3.219013528956566 s |
| Evaluation plus both 10,000-draw analyses | 14.409203471965156 s |
| Sum of stage wall times, excluding orchestration/reporting | 31.000475757929962 s |
| Peak Torch GPU allocated / reserved | 525777408 / 765460480 bytes |
| Peak inference / evaluation host RSS | 2093821952 / 271192064 bytes |
| 1-second GPU telemetry sample count | 16 |
| Sampled device memory / power / temperature / GPU utilization maxima | 1741.0 MiB / 205.81 W / 61.0 °C / 51.0% |

Telemetry covers whole-device allocations and can miss transients. Torch memory
values are process allocator peaks; host RSS is each process's high-water mark.


## Persisted evidence and stop

All generated outputs are outside Git, under resolved project runs /
`task-2_27-third-party-hard-split-evaluation/`:

- `reports/source_and_cohort_references.json`, `preflight.json`,
  `frozen_models.json` and stage-start receipts preserve frozen source/cohort/model
  identities, scientific hashes, execution commit and chronology.
- `predictions/A.jsonl`, `S.jsonl`, `P.jsonl` preserve full-FP32 probabilities
  and original source coordinates; `reports/predictions_frozen.json` authenticates
  their complete identical coverage and outcome-blind inference.
- `evaluation/hamming_ge_{2,3,4}_joined.jsonl` preserve frozen outcome joins,
  source coordinates, paired scores and each threshold's component memberships.
- `evaluation/point_metrics.json` contains all full-precision A/S/P endpoints,
  paired contrasts, class counts, ties and HLA/patient/study summaries.
- `evaluation/patient_peptide_uncertainty.json` and
  `study_peptide_uncertainty.json` contain all prescribed endpoint/contrast
  intervals, units, seeds and usable/undefined/unreliable metadata.
- `evaluation/{patient,study}_component_draws.jsonl.gz` retain every draw's
  fixed-order component multiplicities. `reports/component_composition.json`
  supplies component sizes, class balance, patient and study membership summaries.
- `reports/software_configuration.json`, `resource_summary.json`,
  `evaluation_complete.json`, `completion_verification.json`,
  `logs/focused_tests.log`, `inference.log`, `evaluation.log` and
  `gpu_telemetry.csv` preserve actual execution evidence.
- `reports/scientific_interpretation.md` is an exact copy of this report;
  `reports/finalization_manifest.json` seals the final commit, clean worktree,
  source references and closed run artifacts.

The one-time frozen evaluation is complete. **No training, tuning, calibration,
new model variant, new benchmark search, outcome-driven eligibility change,
repeated independent experiment or historical result revision occurred.** No
follow-up experiment is triggered. The branch is not merged or pushed.
