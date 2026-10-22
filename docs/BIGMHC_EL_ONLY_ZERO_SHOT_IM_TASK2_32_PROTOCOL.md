# Task 2.32 — Frozen direct EL-only zero-shot immunogenicity protocol

2026-10-22 JST. Freeze and commit before any new external EL-model predictions
or performance calculation. This replaces the proposed external-EL experiment.
Task 2.32 explicitly authorizes this evaluation. Both benchmarks' IM-fine-tuned
results are previously known; this is a prespecified follow-up of already frozen
EL models, **not an untouched confirmatory blind test**. Known results may not
choose checkpoints, scores, cohorts, cutoffs or statistical methods.

Use only A Task 2.23 EL epoch 10 and W/P Task 2.31 EL epoch 10, with exact paths,
complete 36-file identities, tensor states and lineage in the machine-readable
configuration. Explicitly reject IM directories/overlays. W/P positive weights
and all training are historical frozen artifacts; no optimizer is constructed.
Do not access IM training payloads, refit/recalibrate, score/refit Teacher,
introduce an IM head or modify model tensors.

Use exactly the Task 2.26 IMPROVE Hamming >=3 identities/outcomes (7788, 227/7561,
6576 peptides, 36 HLAs, 70 patients, 3 studies) and Task 2.25 globally EL/IM-unseen
primary identities (267, 57/210, 265 peptides, 46 HLAs). Authenticate original
freeze receipts and consumed cohort files, not historical predictions. Reuse
curation/distance witnesses without rebuilding the split. Keep original order,
patient associations, duplicates, HLA mappings and source-row locators. No >=2,
>=4, broader IM-novel, reverse-eligibility or new-source analysis.

Neoepitope outcomes come only from the authenticated original `im_test.csv`
first three fields, joined by original row/peptide/HLA. Published prediction
columns are discarded and never model inputs. Benchmark labels were already
known historically; confirming their frozen counts during preflight is allowed,
but cannot alter eligibility. Save outcomes separately from identity-only
inference inputs. All six new prediction files must be fixed before comparisons.

Authenticate the same original BigMHC source and exact HLA pseudosequences for
all arms. Canonical uppercase nine-mers and exact frozen normalized HLA IDs,
no HLA approximation or outcome normalization. CUDA FP32, batch16, eval mode,
no-grad, deterministic algorithms, TF32/AMP off; constant-zero schema targets.
Direct native forward produces **EL logits**; save those and native FP32
`torch.sigmoid(logit)` probabilities. **Use those probabilities for every ranking
endpoint**, preserving exact sigmoid saturation ties. No logit-based alternative
performance analysis, calibration, HLA standardization, ensembling or fitted
transformation. A synthetic non-benchmark probe verifies finite original EL
forward outputs before study inference. Each model scores each authorized
cohort once; source indices and unchanged tensor identities are checked.

Primary: IMPROVE pooled non-interpolated average precision, grouping exactly
tied probabilities at one threshold. AUROC gives ties half credit. Secondary
on both fixed cohorts: AP/AUROC, Precision@10/20, positive prevalence (descriptive
random-ranking AP reference), AP minus prevalence, AP divided by prevalence.
All arms/contrasts W-A, W-P, P-A use identical original observations/outcomes.
Top-K ties: canonical peptide, HLA, study DOI, patient, immutable source ID;
neoepitope missing study/patient fields are empty tie-key components, yielding
its prior peptide/HLA/source rule. Report ties, boundary ties, score/logit
ranges and saturation counts. No score thresholds are optimized.

Descriptive per-HLA AP/AUROC requires **N>=20, >=5 positive and >=5 negative**,
fixed before scoring; retain all cohort rows regardless of allele evaluability.
Save all HLA class counts and explicit undefined values for sparse/one-class
strata. No favorable HLA replaces the primary, no new patient/study performance
hypotheses. Patient/study sample/class/component compositions are descriptive.

Reuse exact frozen Task 2.26 connected components sharing patient (namespaced
by study) OR peptide for IMPROVE (38 units). 10,000 paired draws, local
Random(262742), sorted component IDs; draw the fixed number of units with
replacement and retain every original row with multiplicity, paired across all
arms/metrics. Prespecified study/peptide dependence sensitivity uses frozen
components and Random(262743), but with one connected component the interval
is **undefined, zero draws**, not an invented three-study bootstrap.
Neoepitope uses 265 canonical-peptide clusters, local Random(24242), 10,000
paired draws. These single-population streams reuse the prior rules/seeds,
not exact old draw sequences that interleaved now-unauthorized populations.
No other cohorts are scored/resampled merely to advance a historical RNG.

Use existing exact integer-multiplicity/tied-score metric implementation;
bootstrap top-K consumes repeated rows in the fixed deterministic ordering.
95% percentile intervals use linear interpolation at `(n-1)q`, .025/.975.
Save paired W-A/W-P/P-A intervals for all endpoints, draw statistics and component
multiplicities. Fewer than two components gives no interval; fewer than 20 units
or 1000 jointly usable draws is unreliable. Undefined/one-class metrics stay
undefined. No row-independent biological intervals, p-value search or pooled
cross-study effect. Unknown neoepitope patient/assay dependence remains a limit.

Interpret W's primary AP against **both** A and P. A favorable AUROC, per-HLA
subset or secondary source cannot rescue failed primary AP. Different prevalences
and assay contexts preclude comparing absolute AP as a common difficulty scale.
Historical Task 2.25/2.27 A/S/P included full IM fitting and a different auxiliary
S/P intervention; compare their documented findings descriptively, without
reloading/rescoring them or claiming W equals S. EL-positive scores are presentation
proxies, not calibrated T-cell recognition probabilities. Neither success nor
failure validates EL-label correction or disproves a stability mechanism.
Stop after this one-time evaluation; no training, tuning or new benchmark follows.
