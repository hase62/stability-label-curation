# Task 2.33 — Frozen auxiliary EL-only zero-shot immunogenicity protocol

2026-10-22 JST. Commit this protocol, configuration, implementation and focused
checks before any new S/P benchmark prediction or performance calculation.
Task 2.33 authorizes this final evaluation of existing modified EL checkpoints.
The benchmarks and earlier IM-fine-tuned and positive-weighted results are known;
this is exploratory follow-up, **not an untouched confirmatory blind test**.
They cannot choose epochs, coefficients, scores, populations or statistical rules.

Use exactly A Task 2.23 EL epoch10, S/P Task 2.24 EL epoch10, with canonical
file-map hashes in the machine-readable configuration. S/P used native EL BCE
plus 0.1 times training-positive within-HLA rank auxiliary MSE; P permuted those
targets within HLA. This differs from Task 2.32 positive-loss reweighting.
Authenticate complete 36-tensor EL checkpoints, common source, exact HLA mapping,
preprocessing, training population, initialization and all ten native training
batch/RNG/optimizer schedules. No IM checkpoint, transfer overlay, auxiliary
head/hook or regression output is loaded. No optimizer, fitting, calibration,
Teacher scoring, new variants or model selection is authorized.

Reuse exactly Task 2.32 identity and separately bound outcome manifests:
IMPROVE Hamming >=3: 7788 original rows, 227 positive, 7561 negative, 6576 peptides,
36 HLA alleles, 70 patients, three studies. Neoepitope globally EL/IM-fitting-unseen
primary: 267 rows, 57 positive, 210 negative, 265 peptides, 46 HLAs. Authenticate
consumed files through the pinned Task 2.32 output manifest; retain its original
Task 2.26/2.25 freeze references. No downloads, new splits, distance searches,
deduplication, different Hamming strata, IM-novel secondary cohort, or eligibility
changes. Outcome confirmation cannot alter these populations. Published model
prediction columns and historical S/P IM predictions are never inference inputs.

Reuse A's two Task 2.32 prediction files byte for byte only after exact ordered
identity, checkpoint, input/encoding, source implementation, score, runtime and
batch compatibility verification. Trace the Task 2.32 narrow gzip-I/O repair and
preserved predictions through its authenticated completion record; it changed
no inference, score or eligibility definitions. Strictly reload A without
rescoring benchmark observations; its synthetic probe must match Task 2.32.
Run S/P once per source, four new passes, then freeze all six prediction files
before comparisons. Save every source-row locator, raw FP32 EL logit and native
FP32 sigmoid probability. Use probabilities for every endpoint, preserving
saturation ties; no raw-logit alternative analysis or HLA score normalization.

All arms use authentic BigMHC source 199e890fa69a63646730bcecea0a520e08ca4f02,
exact 414-feature HLA encodings, canonical 9-mers, original native EL forward,
batch16, eval/no-grad, deterministic CUDA FP32, TF32/AMP disabled. Schema targets
are constant zeros, never the experimental outcomes. Check native emitted row
alignment, finite outputs, unchanged tensors and no auxiliary hooks/heads.

Primary: pooled **non-interpolated IM AP on IMPROVE >=3**, grouping exactly tied
probabilities at one threshold. Secondary: AUROC (half credit for score ties),
Precision@10/20, prevalence as descriptive random-ranking AP reference, AP minus
prevalence and AP/prevalence; same endpoints on neoepitope. Top-K deterministic
tie ordering: peptide, HLA, study DOI, patient, immutable source ID. Unknown
neoepitope study/patient fields remain empty metadata. Each metric reports A/S/P
and S-A, S-P, P-A. Undefined metrics stay undefined. No endpoint substitution.

Descriptive per-HLA AP/AUROC requires N>=20, >=5 positive and >=5 negative,
exactly Task 2.32's prespecified adequacy rule; keep all rows in pooled metrics.
Save all HLA class counts, explicit undefined sparse results, logit/probability
summaries and top-K boundary ties. Patient/study composition is descriptive;
no new subgroup-performance hypotheses or favorable subset primary endpoints.

Use Task 2.32's exact paired uncertainty procedure and dataset-local streams:
IMPROVE frozen patient/peptide components (38 units), sorted IDs, Random(262742),
10000 draws of 38 units with replacement; preserve every observation with its
component multiplicity, common to all arms/metrics. Shared peptides connect all
studies into one study/peptide component: study sensitivity interval undefined,
zero draws (seed262743 recorded), no fabricated three-study bootstrap.
Neoepitope: 265 canonical-peptide clusters, sorted IDs, Random(24242), 10000 draws
of 265 clusters with replacement. Same cohorts, algorithms, seeds and iteration
order yield the same component multiplicity streams as Task 2.32; verify this
without reanalyzing its old model results. Preserve draw evidence and metadata.

Use the existing weighted-ranking integer-multiplicity metric implementation,
including deterministic expanded-row top-K. Paired 95% percentile intervals
use linear interpolation at (n-1)q, q=.025/.975, for all three contrasts and all
endpoints. Record usable/undefined draws. Fewer than two components gives no
interval; fewer than20 units or1000 usable draws flags unreliability. No row-wise
biological interval, p-value search, cross-dataset pooled effect or bootstrap
selection. Patient/assay dependence not represented by known identifiers remains
a limitation; large components reduce effective independent information.

Interpret S's primary AP against both A and P. A favorable AUROC, top-K, HLA or
secondary result cannot replace the primary conclusion. Compare descriptively
with Task 2.32's documented negative fixed-weighting result, while distinguishing
auxiliary regression from positive-loss weighting. EL scores are presentation
proxies, not calibrated T-cell-recognition probabilities; neither intervention
corrects EL labels. Different assay contexts and prevalences limit absolute AP
comparisons. No result triggers coefficient tuning or additional experiments.
Stop after this single frozen evaluation; do not train or launch new variants.
