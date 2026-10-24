# Task 2.37 — Frozen A*02:01 measured-Tm direct-transfer experiment

2026-10-24 JST. This is a newly authorized exploratory A*02:01 study. The two-HLA
NO-GO decisions in Tasks 2.35/2.36 remain unchanged. Commit this protocol,
configuration, executable implementation and tests before scientific updates or
IM scoring. No IM label may enter optimization, calibration, early stopping,
epoch/hyperparameter selection or model selection. Previous benchmark results
are known: no claim of an untouched confirmatory test.

Authenticate Task2.23 complete EL epoch10 A, canonical map SHA256
`d8e3d7d3ac5d08d7f420e00b8032fa875b8b6fec1cd9da6b36d35bca0bec04d1`.
Never load IM/W/S/P model weights. Authenticate Task2.35 final output manifest,
its retained A0201 Tm identities and provisional A0201 negative selection. Exactly
710 measured canonical9-mers,11360 unique EL-fitting decoys,12070 rows total.
No source search, download, Mac/CapsNet transfer or new decoy generator.
Retain original Tm°C and y=.5+(Tm_C-37)/72 without clipping/imputation/censoring.
Preserve all four A0201 unresolved repeated-minimum flags. Confirm exact EL
negative provenance and no measured-ligand/EL-positive sequence conflicts. Check
both exact pMHC and allele-agnostic minimum equal-length Hamming distance against
both whole frozen external sources; require distance>=3 for every adaptation
row. Keep all original evaluation observations. Stop on unresolved leakage or
invalid binding. If a saved decoy is invalid, apply only Task2.35's deterministic
eligible-pool/hash ordering replacement and seal any changed selection before
training; never use outcomes/scores to replace identities.

Arms: A unchanged EL10; D measured ligands1/decoys0; P the complete genuine
continuous-target multiset permuted across the710 measured ligands/decoys0;
T genuine continuous targets/decoys0. For each seed in [123,456,789], all D/P/T
start from identical A, and use identical ordered minibatches and settings.
Permutation: local Random(2370000+seed), shuffle original measured-index list in
sorted source-ID order; assign its original y values to destination measured
indices, preserving exact decimal and FP32 multisets. Sample ordering uses a
separate local Random(seed), shuffling an index list once per pass; the same
20 saved full orders feed all three arms. No global RNG coupling with permutation.

Only `condenser.out.weight` and `.bias` receive gradients:415 scalar values.
All other parameters frozen; whole model eval throughout, dropout disabled and
BatchNorm buffers fixed. Exact original BigMHC forward, native414-feature HLA
encoding and canonical peptide transformation. No extra head, learned feature,
architecture change or IM transfer list. Do not use a whole-forward no_grad in
training: native forward reads out.weight directly before HLA-masked sum/bias.
Encoded input tensors may be reused after bitwise native-input/forward agreement
checks. **No learned feature cache**: every adaptation batch executes the native
frozen backbone, avoiding batch-shape numerical assumptions about feature caching.

AdamW lr.001, weight_decay.01, betas(.9,.999), eps1e-8, amsgrad=False,
foreach=False, fused=False; persistent optimizer for20 passes, batch64, keep
last38 rows, no skipped all-negative batch. Exactly189 updates/pass,3780/fit,
nine fits. CUDA FP32, deterministic algorithms, TF32/AMP off,4 CPU threads.
Set torch/NumPy/Python seed to the prescribed seed before each fit. No extra seeds,
intermediate evaluation, schedules, stopping or epoch selection. Use pass20.

Prospective class-imbalance refinement of Task2.35: measured-row weight16,
decoy weight1, identical for D/P/T regardless of target value. Each batch loss is
sum(w_i * BCEWithLogits(z_i,y_i)) / sum(w_i), **not batch-size normalization**.
Groups each contribute11360 total weight per full pass. Save per-pass normalized
update loss and whole-pass weighted numerator/denominator, source-order hashes,
optimizer steps, parameter/gradient/buffer/frozen checks. This fixed refinement
uses known1:16 training imbalance; it is not an IM-result-driven search.

Store each adapted checkpoint as the exact two FP32 output tensors plus an
explicit authenticated complete-A parent/file-map and complete36-state hash
receipt. Reconstruct by strictly loading A with no IM overlay and replacing only
the two allowed tensors; strict-check all36 tensor hashes and reload predictions
on a fixed training probe. No full backbone duplication needed. Never overwrite A.

Evaluation populations sealed before updates: primary IMPROVE A0201 source-order
subset616 rows,21 positive/595 negative,16 original patient/peptide components;
secondary complete IMPROVE>=3 (7788,227/7561,38 components); additional descriptive
complete neoepitope primary267 (57/210,265 peptide clusters), plus its predeclared
A0201 descriptive subset46 (5/41). Include the optional neoepitope evaluation
prospectively, not after selecting a favorable source. Also describe B0702
IMPROVE555 and remaining other-HLA IMPROVE6617; these cannot replace the primary.
Use original globally defined components in subsets, no component splitting.

Score extraction: native FP32 sigmoid(logit), larger always positive; save raw
logit and score. D/P/T outputs are adapted discrimination scores, not calibrated
EL or IM probabilities, measured Tm or surface lifetimes. All native IM inference
uses batch16, eval/no-grad and zero placeholder targets. A's exact compatible
Task2.32 raw/logit-probability files may be reused byte-for-byte after checkpoint,
preprocessing/source/runtime/order/synthetic-probe compatibility checks; A is
not refit. Freeze all20 source/model prediction files (A plus nine adaptations
on both sources) before any new IM performance comparison. Never average score
vectors into an ensemble or invert orientation after results.

Primary metric non-interpolated AP, exact equal-score threshold groups. AUROC
half credit to ties; Precision@10/20 descending score then canonical peptide,HLA,
study DOI,patient,source-ID. Save prevalence, AP/prevalence and AP−prevalence.
Report A and D/P/T per seed, and descriptive seed means of metrics. Main statistic
is mean_s[AP(T_s)−AP(P_s)]; practical mean_s[T_s−A], descriptive mean_s[T_s−D_s].
A is the same score vector for all seeds. Seed means are not ensemble metrics or
independent biological experiments. Report all seeds, not the best one.

Paired10000 component bootstrap draws, sorted frozen IDs, fixed local streams:
primary A0201 Random(237001), full IMPROVE Random(262742), neoepitope full
Random(24242). Same row multiplicities in every seed/arm; each draw computes all
per-seed metrics and then seed-averaged contrasts. Percentile95% intervals at
q=.025/.975, linear(n−1)q. No row-wise bootstrap, seed bootstrap or p-value search.
Any contrast with an undefined constituent is undefined, not a reduced-seed mean;
record invalid draws. Fewer than20 components flags unreliable exploratory
uncertainty, including primary16. Shared peptides connect studies into one unit;
study-level interval undefined, no fabricated study bootstrap. Report component
and positive-bearing-unit sizes and sparse-positive limitations.

B0702/other-HLA and HLA-specific breakdowns are descriptive point metrics only.
Per-HLA adequacy: N>=20,positive>=5,negative>=5, fixed prior reporting rule, not
a new support gate replacing the explicit A0201 authorization. Neoepitope A0201
is descriptive without an added uncertainty experiment. Full-cohort uncertainty
remains secondary and includes deterioration/negative transfer. No further
cohorts, Hamming thresholds, conditions, coefficient or backbone searches.

Interpret T-P alongside T-A and T-D and all seeds. Extra ligand/decoy learning or
target-mass differences cannot establish a genuine Tm-pairing effect. Effects at
other HLAs through shared output coefficients/AdamW decay are not learned
allele-specific thermostability. Distinguish measured Tm from prior Teacher
kinetic ranks, EL loss weighting, auxiliary heads and calibrated probabilities.
The January2024 CapsNet pilot is historical motivation only, with different
architecture/evaluation; no artifact access, reproduction or formal superiority
comparison.21 positives,16 known components,710 measured ligands, constructed
decoys, output-only adaptation, repeated benchmark inspection and unverified
assay/patient independence limit interpretation. Stop after the nine frozen fits
and planned evaluation; no automatic new variant, tuning or follow-up experiment.
