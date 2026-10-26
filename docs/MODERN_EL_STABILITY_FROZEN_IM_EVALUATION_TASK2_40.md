# Frozen modern EL/stability IM evaluation — Task 2.40

**The fixed fusion did not improve the prespecified primary AP endpoint.** Its observed AP was lower than the same-scale Mix EL rank comparator; the paired component-bootstrap interval includes both negative and positive effects. No claim of a useful incremental kinetic-stability ranking benefit is supported by this exploratory run. This does not establish biological irrelevance of kinetic stability.

## Isolation, frozen design and execution order

- Branch: `task/2.40-frozen-el-stability-im-evaluation`; separate worktree `~/codex/repos/stability-label-curation-task240`. Exact base: `eb681b8504dc3ce73c1471e8cb14c411618a6bf2`.
- Scientific implementation/protocol commit: `a22833977d0bb6cba3d463580676126aa5b4ca41`.
- **Pre-evaluation prediction-seal commit: `282e4d5e09a92bc8d82db3880fa9dd38ebf731a9`.** Final documentation commit is identified by Git HEAD and the external final receipt.
- No Task 2.39 transformation discrepancy: unchanged observation-weighted within-HLA midrank `(less + 0.5 * equal) / N`; fixed fusion is the arithmetic mean of EL/stability ranks. Native pooled comparisons remain separate. Ranks and fusion are cohort-relative scores, not calibrated immunogenicity/presentation probabilities or clinical thresholds.
- Bootstrap uses the already frozen `random.Random(24040).choices` stream, not fallback seed 202640 or the older BigMHC `randrange` stream. Original sorted patient/peptide units are retained.
- No new public-model discovery/download, model fitting, IM calibration, checkpoint/head/temperature selection, thresholds, alternate fusion weights or cohort optimization. Neoepitope was not evaluated. Other branches, historical BigMHC results and checkpoints were preserved; no merge or push.

| Event | UTC |
|---|---|
| input_receipt.json | 2026-10-26T08:34:38.904393+00:00 |
| mix_started.json | 2026-10-26T08:35:03.762174+00:00 |
| spearmint_started.json | 2026-10-26T08:35:07.162287+00:00 |
| prediction_freeze.json | 2026-10-26T08:40:27.420996+00:00 |
| pre_evaluation_receipt.json | 2026-10-26T08:41:13.782643+00:00 |
| evaluation_started.json | 2026-10-26T08:41:13.783029+00:00 |
| evaluation_complete.json | 2026-10-26T08:41:29.155961+00:00 |

The Stage A module imports no outcome/evaluation loader. Its file-access guard denies other historical run and biological-data files; verified Mix child processes receive only local per-HLA peptide/input-output paths. Both complete native vectors, all ranks, fusion, the sensitivity mask and scientific code hashes were sealed before the pre-evaluation Git commit. Only the subsequent Stage B gate opened the original outcome sidecar. The scored identity population had not changed after outcome inspection.

## Model authentication and prediction integrity

| Model | Revision | Artifact SHA256 |
|---|---|---|
| MixMHCpred v3.0 | `0a7f9b9e20d1cf02236f4a0a90d16735be879b38` | archive `ebd8f2b6e582909d4dc8cb2ab7da19f867b5cd3b3cf7502917ca12fecc4bc1b9` |
| SPEARMINT Stage 3 | `93e8e3e640e49e5a373f0dc432b122df19e4b969` | safetensors `5b842af0c8b41fdf7a0ab329fe2bc76b92de0bf559dcede1501493fdf68cff8f` |

All runtime-source hashes and dependency versions were checked against authenticated Task 2.39 receipts/locks before inference. Full-length HLA sequences and their hashes were reused for all 36 alleles; no pseudosequence/nearest-allele substitution. Mix selected `Score_<designated HLA>`, including C0304 despite its tied C0303 nearest-reference metadata, and retained native six-decimal ties. No best-allele or PRIME score was substituted.

SPEARMINT used original full-chain tokenization and explicit chain-ID/CLS/EOS checks, Stage 3, SPA index 0, raw 37.0°C, batch size 4, FP32, eval/inference mode, no gradients, deterministic algorithms and disabled TF32. Remote snapshot and pickle fallbacks were blocked; only local safetensors were loaded. Parameter version counters were unchanged, and the on-disk checkpoint hash remained unchanged. Outputs are unconstrained native predicted log1p(hours), not measured lifetimes; finite negative outputs were retained without clipping.

- mix: **7788 successful predictions; 0 failed**. No missing/duplicate/misaligned or nonfinite rows. Elapsed scoring/load time 15.049264768953435 s; recorded self peak RSS 487220 KiB.
- spearmint: **7788 successful predictions; 0 failed**. No missing/duplicate/misaligned or nonfinite rows. Elapsed scoring/load time 235.89774612593465 s; recorded self peak RSS 7067392 KiB.
  Fixed first-four-row repeated batch was exactly equal; single/batch maximum absolute difference 2.6226043701171875e-06, inside fixed atol=1e-4/rtol=1e-5. Peak GPU allocation/reservation 3823994368 / 3969908736 bytes.

Z790/WSL2 Ubuntu 26.04.1 LTS; RTX 4090, driver 610.88; Python 3.13.5. SPEARMINT uses the existing PyTorch 2.13.0+cu130/CUDA 13.0 build with Transformers 4.57.1 and safetensors 0.6.2. Mix/evaluation use the isolated NumPy 2.2.6 environment. No shared environment, driver or CUDA libraries were changed. `runtime_environment.json` and execution receipts retain complete dependency versions and resource evidence. Aggregate evaluation plus all three 10,000-attempt resamplings took 15.372918789973482 s.

## Sealed score identities

Original Task 2.32 identity SHA256: `33fbad5f142a93d0803b39800fa3dcb71437320c4134e92594080830b6f26986`. Task 2.39 allowlisted identity SHA256: `3d34aa3e1ab42fb31b05ce447cbd8c1f8484335a10f7a964bfb0dedd1278fff1`. Common-coverage manifest SHA256: `d8e47c8178b038677ac5de503b0e536bd559794dd143a9124f70ea364ecbb126`. Ordered row-key hash: `8118663ebf5c23de8f36a7a7c15aa0247a0609e04ade927657528d2986f6fee9`.

| Frozen score artifact | SHA256 |
|---|---|
| mix_native.jsonl | `c7420d76bbb6263c5c999dcc9bbef18521f07b9a1f35bca72c679bc94fc8d86a` |
| spearmint_native.jsonl | `994e3677885da4cd96faa0042e866fd5ad5a45b681554b6a0cb0d7404cc4e3e3` |
| rank_scores.jsonl | `0586d97f488357ed1b2e9a2ae00f7346a2849c9a01b7a0e368dc521e9b7ae5b2` |
| fusion_scores.jsonl | `3709c485adf566d544b471d8cf4a3d2b2a401a039bd076e7dcc0aacf98a2fbe5` |
| frozen_scores.jsonl | `0d2fe405bec9c249e4d55eba29bbeb3614c7c4048fcfda1359f36c904a13d451` |

Prediction-freeze receipt SHA256 is `e67c82c78790dedd1a3914ab70c14142c2eeb9fd7fa856d0d9a1b1e5909b4675`. Private row keys, peptides, patient-level data, scores and weights stay outside Git. No score table was overwritten or rerun after unblinding.

## Primary full-cohort result

All **7,788** frozen observations were retained: **227 positive, 7,561 negative**, prevalence/random-ranking reference **0.029147406266050335**, 6,576 unique peptides, 7,750 peptide–HLA pairs, 36 HLAs, 70 patients, three studies and 38 original patient/peptide dependence components. Repeated original biological observations were not deduplicated. The labels matched the authenticated original Task 2.26 sidecar SHA256 `64ed767d65e4e5f9895b1062f9ff160054d1d29b9b460d7bd3e8037279e31709` and its original curation receipt; every ordered source key matched.

| Score | Non-interpolated AP | AUROC | Precision@10 | Precision@20 | AP / prevalence |
|---|---:|---:|---:|---:|---:|
| Mix native | 0.04240844678691356 | 0.5612615048122553 | 0.2 | 0.15 | 1.4549646853589548 |
| SPEARMINT native | 0.03340928510048086 | 0.5396321373242124 | 0.0 | 0.05 | 1.146218116134559 |
| Mix EL rank | 0.042279817701160134 | 0.574875593338643 | 0.1 | 0.05 | 1.4505516310864983 |
| Stability rank | 0.035606505376531594 | 0.5473680438745778 | 0.0 | 0.05 | 1.2216011624336036 |
| Fixed 50:50 fusion | 0.0397950431023211 | 0.570306004555023 | 0.1 | 0.1 | 1.3653030646734656 |

**Primary fusion minus EL-rank AP: -0.002484774598839036**, paired 95% percentile interval **[-0.011700514831894897, 0.005813159441208066]**. Secondary relative AP change: **-5.8769756681587%**. The interval spans zero; these results neither demonstrate benefit nor establish a precise harmful effect.

Fusion minus EL-rank AUROC: -0.0045695887836200155, paired interval [-0.02383397349397791, 0.0199296532404083]. Precision@20 improved descriptively from 0.05 to 0.1 while Precision@10 stayed 0.1; neither replaces the failed primary AP comparison. Native Mix achieved AP 0.04240844678691356 and Precision@10/20 0.2/0.15. Do not attribute differences from native Mix to stability alone, because HLA rank normalization changes that comparator.

## Paired uncertainty and prespecified secondary/sensitivity analyses

| Population | N / positive / negative | Units | EL-rank AP | Fusion AP | Fusion minus EL-rank AP | 95% paired interval | Valid / attempts |
|---|---|---:|---:|---:|---:|---|---|
| full_IMPROVE | 7788 / 227 / 7561 | 38 | 0.042279817701160134 | 0.0397950431023211 | -0.002484774598839036 | [-0.011700514831894897, 0.005813159441208066] | 10000 / 10000 |
| A0201 | 616 / 21 / 595 | 16 | 0.06598569088186262 | 0.05520768432324642 | -0.010778006558616202 | [-0.10648172379170215, 0.026383917942102434] | 9999 / 10000 |
| training_neighbor_excluded | 7780 / 227 / 7553 | 38 | 0.042381427056919885 | 0.04027847022004643 | -0.0021029568368734555 | [-0.011711933326666478, 0.006729403830251213] | 10000 / 10000 |

Exactly 10,000 attempts were made per planned population. Full and sensitivity analyses had no invalid attempts; A*02:01 had one no-positive draw (9,999 valid), retained in the audit log and not replaced. All score conditions used identical component multiplicities. Original full-cohort ranks were fixed throughout. Sensitivity reused the original 38-unit universe; A*02:01 retained its original 16 component keys. No row bootstrap or study-bootstrap interval was substituted.

Full-cohort component sizes ranged from 19 to 2,475 observations; A*02:01 ranged from 3 to 262. Large components and only 38/16 units limit precision. Shared study/acquisition effects and incomplete donor ancestry need not be captured fully by patient/peptide components; all studies connect in one study/peptide component, so a study-bootstrap interval is not identifiable. These are conditional exploratory uncertainty summaries, not 7,788 independent biological experiments or population-level clinical guarantees.

| Secondary paired contrast (full cohort) | AP difference | 95% paired AP interval | AUROC difference | 95% paired AUROC interval |
|---|---:|---|---:|---|
| native_stability_minus_native_EL | -0.008999161686432701 | [-0.019093180161662514, 0.0025864043714458745] | -0.021629367488042894 | [-0.06353572339895325, 0.04883537732446254] |
| stability_rank_minus_EL_rank | -0.00667331232462854 | [-0.018306889125180418, 0.0014222912758912888] | -0.027507549464065195 | [-0.06149160142316693, 0.019854694277203995] |

A*02:01 is secondary: 616 observations, 21 positives, 595 negatives, prevalence 0.03409090909090909.

| A*02:01 score | AP | AUROC | Precision@10 | Precision@20 |
|---|---:|---:|---:|---:|
| Mix native | 0.06598569088186262 | 0.5831132452981193 | 0.2 | 0.1 |
| SPEARMINT native | 0.05141117687198956 | 0.6128851540616247 | 0.0 | 0.05 |
| Mix EL rank | 0.06598569088186262 | 0.5831132452981193 | 0.2 | 0.1 |
| Stability rank | 0.05141117687198956 | 0.6128851540616247 | 0.0 | 0.05 |
| Fixed 50:50 fusion | 0.05520768432324642 | 0.6139655862344938 | 0.1 | 0.05 |

A*02:01 AUROC difference is 0.030852340936374567 with interval [-0.027834202976787036, 0.14782278888967978]. Its positive AUROC direction does not override its negative AP direction, lower top-K precision or its secondary status. There are only 21 positives and 16 dependence units.

The label-blind eight-observation sensitivity mask was hashed before predictions and sealed before labels. All eight excluded observations were subsequently found to be negative; the retained set is 7,780/227/7,553. No transformation was recomputed. The AP contrast remained negative and its interval still crossed zero. This exclusion does not resolve unverified Mix EL or MINT Stage 1/PPI ancestry.

## All-HLA descriptions

All alleles are listed alphabetically, without a favorable-subset gate. For a single HLA, native and within-HLA rank AP coincide because ordering/ties are preserved; the table uses the same-scale rank comparator. Full native/rank AP/AUROC and top-K values are retained in `aggregate_metrics.json`. Missing-class AP/AUROC are explicitly undefined, not replaced by another cohort.

| HLA | N | Positive | Negative | Mix EL AP | Stability AP | Fusion AP | Fusion minus EL-rank AP |
|---|---:|---:|---:|---:|---:|---:|---:|
| HLA-A*01:01 | 251 | 14 | 237 | 0.2012612178829318 | 0.27112786360211677 | 0.25418597050984676 | 0.052924752626914956 |
| HLA-A*02:01 | 616 | 21 | 595 | 0.06598569088186262 | 0.05141117687198956 | 0.05520768432324642 | -0.010778006558616202 |
| HLA-A*02:05 | 41 | 1 | 40 | 0.0625 | 0.038461538461538464 | 0.047619047619047616 | -0.014880952380952384 |
| HLA-A*03:01 | 474 | 6 | 468 | 0.01855259872085514 | 0.010842941950395443 | 0.013481607740430427 | -0.005070990980424713 |
| HLA-A*11:01 | 153 | 6 | 147 | 0.2771969469706539 | 0.06457004954541899 | 0.1068941587851979 | -0.170302788185456 |
| HLA-A*24:02 | 379 | 12 | 367 | 0.0438362784755768 | 0.05892112849320896 | 0.051986876967789766 | 0.008150598492212967 |
| HLA-A*26:01 | 243 | 6 | 237 | 0.03274655458762016 | 0.025415207417985555 | 0.029260640871643366 | -0.003485913715976792 |
| HLA-A*30:01 | 163 | 6 | 157 | 0.09159783306124769 | 0.0855049359291646 | 0.1453169006135108 | 0.053719067552263106 |
| HLA-A*30:02 | 27 | 0 | 27 | undefined | undefined | undefined | undefined |
| HLA-A*31:01 | 235 | 3 | 232 | 0.04131787165713151 | 0.044560455733901265 | 0.040965223298621775 | -0.00035264835850973286 |
| HLA-A*32:01 | 239 | 6 | 233 | 0.028166898618284683 | 0.025328673742745646 | 0.025689056493726943 | -0.00247784212455774 |
| HLA-A*68:01 | 88 | 3 | 85 | 0.0641549595572584 | 0.06549103162730253 | 0.06753712237583205 | 0.0033821628185736474 |
| HLA-B*07:02 | 555 | 8 | 547 | 0.014651604212497915 | 0.01903647621591356 | 0.013935554554799003 | -0.0007160496576989125 |
| HLA-B*08:01 | 402 | 7 | 395 | 0.04234770924616027 | 0.02637065955439813 | 0.02122954589750785 | -0.021118163348652418 |
| HLA-B*13:02 | 64 | 1 | 63 | 0.02 | 0.06666666666666667 | 0.029411764705882353 | 0.009411764705882352 |
| HLA-B*15:01 | 111 | 4 | 107 | 0.12024193157588679 | 0.11843172840824169 | 0.15113185425685427 | 0.030889922680967477 |
| HLA-B*18:01 | 116 | 2 | 114 | 0.043154761904761904 | 0.017551892551892552 | 0.026765188834154352 | -0.016389573070607552 |
| HLA-B*27:05 | 119 | 5 | 114 | 0.054755134542368585 | 0.10736893979090252 | 0.0654873951875017 | 0.010732260645133114 |
| HLA-B*35:01 | 225 | 8 | 217 | 0.050170642304631585 | 0.037892463948337424 | 0.041793785853663806 | -0.008376856450967779 |
| HLA-B*35:03 | 91 | 6 | 85 | 0.08417719142967178 | 0.08644615282546315 | 0.07851937721308694 | -0.005657814216584844 |
| HLA-B*37:01 | 12 | 0 | 12 | undefined | undefined | undefined | undefined |
| HLA-B*38:01 | 390 | 10 | 380 | 0.04448620958402233 | 0.07176663280356381 | 0.12486010750803875 | 0.08037389792401642 |
| HLA-B*40:01 | 276 | 13 | 263 | 0.04657538706061297 | 0.042356290541253075 | 0.044464812362157775 | -0.0021105746984551935 |
| HLA-B*40:02 | 80 | 3 | 77 | 0.08888888888888888 | 0.05849420849420849 | 0.0805728088336784 | -0.008316080055210479 |
| HLA-B*44:02 | 174 | 1 | 173 | 0.25 | 0.05 | 0.14285714285714285 | -0.10714285714285715 |
| HLA-B*44:03 | 85 | 2 | 83 | 0.029647435897435896 | 0.029230769230769234 | 0.030416666666666668 | 0.000769230769230772 |
| HLA-B*44:05 | 17 | 0 | 17 | undefined | undefined | undefined | undefined |
| HLA-B*51:01 | 87 | 2 | 85 | 0.28846153846153844 | 0.3 | 0.3 | 0.011538461538461553 |
| HLA-B*57:01 | 22 | 0 | 22 | undefined | undefined | undefined | undefined |
| HLA-C*02:02 | 310 | 0 | 310 | undefined | undefined | undefined | undefined |
| HLA-C*03:04 | 288 | 10 | 278 | 0.20990525007807104 | 0.04612535989970495 | 0.08548358923567118 | -0.12442166084239986 |
| HLA-C*04:01 | 389 | 7 | 382 | 0.04134610288184683 | 0.025091325435811343 | 0.04595832690283266 | 0.004612224020985829 |
| HLA-C*05:01 | 10 | 0 | 10 | undefined | undefined | undefined | undefined |
| HLA-C*06:02 | 225 | 25 | 200 | 0.14905877033917975 | 0.17003689920121948 | 0.17991148796515838 | 0.030852717625978632 |
| HLA-C*07:01 | 556 | 15 | 541 | 0.09857802432390687 | 0.02723323896048051 | 0.033181068046603396 | -0.06539695627730348 |
| HLA-C*07:02 | 275 | 14 | 261 | 0.06587019162747472 | 0.10616641640643198 | 0.09912327536606977 | 0.03325308373859505 |

Among 30 alleles with both classes, 13 improved and 17 deteriorated descriptively; six alleles have no positives and undefined AP/AUROC. Many class counts are very small. This heterogeneity does not support a general stability-fusion advantage, and no allele is promoted as a new primary target.

## Label-free score relationships

Overall native-score Spearman correlation: **0.3862906064508086**. Pooled correlation of the two within-HLA percentile ranks: **0.4766925434129913**. Full per-HLA correlations are saved. These show partially shared rankings, not causally independent biology.

Fusion-induced within-HLA percentile displacement diagnostics: `{"decreased": 3848, "increased": 3838, "maximum": 0.5036231884057971, "mean": 2.280889624294107e-19, "minimum": -0.5499999999999999, "quantiles": {"0": -0.5499999999999999, "10": -0.20454545454545459, "100": 0.5036231884057971, "25": -0.09644849848095349, "50": 0.0, "75": 0.09583230587977429, "90": 0.2062747035573123}, "unchanged": 102}`. This re-ranking is diagnostic only; the evaluated fusion remains the original arithmetic mean. Native SPEARMINT score range was -0.308062344789505 to 4.340307235717773; values were not clipped or converted into supposed measured hours.

## Scientific interpretation and limits

1. Adding the fixed 50:50 stability rank did **not** improve primary AP beyond the same-scale modern EL rank. The primary difference is negative and exploratory uncertainty spans zero. No strong directional benefit is supported.
2. A*02:01 AP and the fixed eight-neighbor sensitivity analysis also have negative observed AP differences. Mixed AUROC/top-K and HLA-specific effects do not rescue the primary hypothesis.
3. No exact peptide or peptide–HLA match to published S2/S3 split indexes was found in Task 2.39, but eight training-neighbor observations were known. These facts do not establish complete novelty or zero leakage.
4. Complete MINT Stage 1 BA, MINT PPI and MixMHCpred EL training identities remain unknown. Full source-publication/donor overlap and upstream IM-blind architecture/model-selection history remain unverified. Stability-only fitting objectives and this task's lack of IM fitting are distinct from complete development-history independence. SPEARMINT also inherits BA/PPI representations, so even a fusion benefit could not isolate causal kinetic-stability information.
5. IMPROVE has prior exploratory use in the project; this is not untouched confirmation or prospective clinical validation. Patient-context assay negatives are not universal biological non-immunogenicity. Assigned HLA identities were preserved rather than reinterpreted as new experimental restriction evidence.
6. Predicted kinetic half-life differs from Jappe measured thermal melting temperature, natural surface pMHC persistence and patient-derived T-cell recognition. This result says nothing definitive about stability's biological relevance or correctness of low-stability EL-positive labels.
7. **NO-GO for advancing this fixed fusion as an improved predictor on the present evidence.** Independent confirmation would be required before any improvement claim, but this result provides no positive efficacy signal that warrants prioritizing adoption/confirmation of this exact fusion over EL alone. A future independently specified replication could still be scientifically informative; no further optimization or experiment is initiated here.

## Tests, reproduction and artifact boundaries

Twenty-six focused tests passed before predictions: 12 new Task 2.40 cases and 14 reused Task 2.39 cases. They cover identity/hash/alignment, designated HLA, full chains, fixed assay/offline contract, finite/sign-preserving scores, midranks/fusion, tie-aware AP/AUROC against brute-force weighted oracles, fractional top-K ties, paired fixed-rank component resampling, no-positive invalid draws/no rerolls, exact eight-row masks, scoring-file access restrictions and deterministic/no-overwrite serialization.

Saved-score aggregate tables were reproduced exactly against original authenticated labels, without running a model or recomputing ranks. All saved bootstrap multiplicities were reproduced with the frozen RNG, and percentile intervals were regenerated from the saved paired contrasts. `reproduction_verification.json` is PASS. No scientific scoring, metric, resampling, population or configuration code changed after unblinding. Reporting/plot rendering only reads completed result artifacts.

Run root: `~/codex/runs/stability-label-curation/task-2_40-frozen-el-stability-im-evaluation/`. Key outputs: `prediction_freeze.json`, `pre_evaluation_receipt.json`, `frozen_scores.jsonl`, `aggregate_metrics.json`, `paired_uncertainty.json`, three full bootstrap logs, `label_free_score_relationships.json`, model execution/environment logs, `reproduction_verification.json`, and `final_execution_receipt.json`. Large/private data and external weights are not in Git. Standalone figures are `figures/AP_comparison.png/.svg` and `figures/paired_AP_contrasts.png/.svg`.

No BigMHC/IM training, model fitting, calibration, coefficient or head search, threshold optimization, model selection, favorable cohort/HLA selection, historical-results revision, merge or push occurred. Stop after this single frozen evaluation; Task 2.41 has not started.
