# Task 2.35 — Measured-Tm eligibility and zero-shot IM cohort preflight

Completed on **Z790 WSL2, CPU only, 2026-10-23 JST**. Branch
`task/2.35-measured-tm-eligibility-preflight`, directly based on approved Task 2.33
`127d99c63c72c1511f751e0102ddd04536d1900e`. The separate Mac Task 2.34 commit
`cf749a43d7c7ba5d66d9e893d28cb31629fef707` was a reference for expected counts;
it was not fetched and no historical CapsNet code, checkpoints or prediction
artifacts were accessed or transferred.

**NO-GO for the intended two-HLA transfer/IM evaluation.** Authentic source data,
mathematically valid targets, label-blind leakage exclusion and matched decoys
are feasible. The blocker is **insufficient HLA-B*07:02 positive IM support**:
IMPROVE has **8**, below the predeclared minimum **10**. A*02:01 passes the minimum
exploratory gate, but is not substituted as the primary. The neoepitope benchmark
fails support for both alleles. Removing observations cannot increase these
positive counts. No training experiment or IM performance evaluation followed.

## Frozen rules and separation of labels

Read the existing Task 2.23,2.31,2.32,2.33 reports and authoritative manifests.
The [data-only protocol](MEASURED_TM_ELIGIBILITY_TASK2_35_PROTOCOL.md) was committed
as **`e59fe3d81b3d1ad489285999f94639003aed08e9`**, before this task opened IM outcome manifests or
computed candidate HLA class counts. The parser/filter and focused tests were
committed as **`77a8b509b0c8f8912e92db75a8f748e1f23ccddb`**, also before outcome tabulation.

Preferred policy: **protect every observation in both frozen external cohorts**;
remove prospective Tm training sequences within Hamming<=2 of ANY equal-length
external IM peptide, across all HLAs. Apply the same exclusion to prospective
adaptation decoys. The alternative retains all Tm candidates and excludes near
IM rows only in diagnostic masks. It was specified before outcome counts and
cannot replace the preferred policy because of a favorable class balance.

Minimum gate: **>=10 positives,>=30 negatives,>=5 frozen dependence components
per HLA**, both A*02:01 and B*07:02 required. Prior per-HLA descriptive-reporting
criteria (>=5 per class) were weaker and do not override this gate. Original
patient/peptide components are retained, never split to inflate counts. Minimum
support is a feasibility threshold, not proof of power or biological independence.
Previously known outcomes/results in project reports mean this is computational
label separation, not a claim that the researcher was historically blinded.

All sequence-only identities, witnesses, masks and provisional decoy selections
were hash-frozen at **2026-10-23T13:23:53.166112+00:00**. Only after that receipt was sealed were
outcome files opened, at **2026-10-23T13:24:50.798521+00:00**.
No IM outcome or model score influenced eligibility. Prior predictions were not
loaded or reanalyzed. No AP, AUROC, top-K, model fit, feature extraction or GPU
operation was executed.

## Original Jappe public source and parser checks

Jappe et al., *Thermostability profiling of MHC-bound peptides: a new dimension
in immunopeptidomics and aid for immunotherapy design*, Nature Communications 2020,
[DOI 10.1038/s41467-020-20166-4](https://doi.org/10.1038/s41467-020-20166-4),
[PMC7726561](https://pmc.ncbi.nlm.nih.gov/articles/PMC7726561/).
Original article XML from Europe PMC maps **Supplementary Data 3→MOESM6** and
**Data 4→MOESM7**. Both workbooks were downloaded directly from the journal's
`static-content.springer.com` attachment endpoint, not reconstructed from models
or historical exports. Only the article XML and two small measurement workbooks
were acquired; no MS RAW data or historical weights. HTTP headers, URL, byte size,
UTC retrieval time and SHA256 are preserved with the source files.

| Supplement | Assigned HLA | Workbook | Bytes | SHA256 |
| --- | --- | --- | ---: | --- |
| Data 3 | HLA-A*02:01 | `41467_2020_20166_MOESM6_ESM.xlsx` | 59092 | `c15cdee1454aaeafc73574ebd456919e88a15acdc3d3e58cfabb0e44df6361aa` |
| Data 4 | HLA-B*07:02 | `41467_2020_20166_MOESM7_ESM.xlsx` | 68951 | `0b1b160265ae060a6fc353feb2290706c009628f9182ade778a9f2575bb619de` |

Raw sources: resolved project data / `jappe2020_measured_tm_task2_35/`.
Native OOXML parsing preserves physical worksheet/row/cell IDs, original peptide
text, numeric Celsius Tm text, source formatting attributes, published transformed
Tm text and explicit/derived quality status. No spreadsheet formula is evaluated,
no missing value is imputed, and no numerical Tm is clipped. The eligibility
parser does not decode/use the workbook's published predicted-affinity column.
The original published transformed-Tm column is retained for provenance but is
not the requested new common target.


| HLA | Physical rows incl. header | Finite distinct measured peptides | 8-mers | Canonical9-mers | 10-mers | 11-mers | Duplicate/conflicting identities |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| HLA-A*02:01 | 1095 | 1094 | 4 | 711 | 216 | 163 | 0 / 0 |
| HLA-B*07:02 | 1356 | 1354 | 92 | 782 | 318 | 162 | 0 / 0 |

Counts reproduce the Mac references exactly: **2448 finite distinct source
peptides; 1493 canonical9-mers**. B0702 contains one auxiliary blank physical row,
which is not a measurement. The **955 other-length source peptides** are preserved
descriptively, not converted into 9-mer cores. No nine-mer was removed because of
duplicate or contradictory identity.

These are author-released A/B ligand assignments in transfected C1R contexts,
with residual endogenous HLA expression and author motif/background processing.
They are not individual purified-complex restriction experiments for every row.
No new HLA prediction or reassignment is performed. The source measures a thermal
melt midpoint in Celsius, **not kinetic half-life**, and does not establish a
conversion to hours. Measurement provenance does not certify every underlying
curve/assay trace; these remain source limitations.

## Common quantitative target and quality flags

Use **y=0.5+(Tm_C−37)/72**, computed directly from the stored measured Tm at
Decimal precision 50, retaining decimal text and a finite floating representation.
Every canonical9-mer target is within **[0,1]**, without clipping or imputation.


| HLA | Tm°C range, all lengths | Tm°C range,9-mers | Derived y range,9-mers |
| --- | --- | --- | --- |
| HLA-A*02:01 | [40.10564, 65.43171] | [40.10564, 65.43171] | [0.5431338888888889, 0.8948848611111111] |
| HLA-B*07:02 | [40.10564, 67.12476] | [40.10564, 66.57984] | [0.5431338888888889, 0.9108311111111111] |

The combined 9-mer range is **40.10564–66.57984°C**, target
**0.5431338888888889–0.9108311111111111**. The B0702 all-length maximum 67.12476°C
belongs outside the 9-mer cohort and is not silently substituted as its maximum.

No explicit original QC-flag column is present. The unresolved repeated-minimum
flag is derived from repeated stored Tm minima, not interpreted as censoring.
Seven source rows at all lengths share the minimum; **five are 9-mers**. All five
remain in the preferred panel:

| HLA | Peptide | Original source row | Tm°C |
| --- | --- | ---: | --- |
| A*02:01 | FQTDLIYNL | 197 | 40.10564 |
| A*02:01 | QLGPDNPNV | 535 | 40.10564 |
| A*02:01 | ILLKALTNL | 611 | 40.10564 |
| A*02:01 | VIAEQLAKL | 694 | 40.10564 |
| B*07:02 | IPNSPFTVM | 859 | 40.10564 |

The reason for those repeated minima is unresolved. They are neither discarded
nor relabeled as censored observations. Original numeric text and flags remain
available for review, independent of any future model outputs.

## Authentic BigMHC and external identities

Task 2.23 actual authoritative split manifest
`processed/el_split_manifest_v1.csv.gz` SHA256
`6b3a6a0c00f86c26e51b84a8df1dd7e81d545117baa871dabd0707edaf89ac00`
was authenticated to its original preflight receipt and streamed in lockstep
against original EL data SHA256
`5bf7fb7c25845aa171baae289a1bb8f00b185f1d5cce99c05609eabaca929fdf`.
Every prepared source index, peptide, HLA and EL label matched; no split was
recreated or approximated. Source IDs/provenance remain linked to that manifest.

| EL partition | Rows / unique pMHC keys | Positive | Negative | Unique peptides | HLAs |
| --- | ---: | ---: | ---: | ---: | ---: |
| Fitting | 1308196 | 63053 | 1245143 | 1122528 | 49 |
| Validation / prior epoch selection | 145371 | 7006 | 138365 | 124828 | 47 |

The historical11 excluded rows remain excluded. Baseline reference is approved
Task 2.23 `checkpoints/EL_epoch_10`, map digest
`d8e3d7d3ac5d08d7f420e00b8032fa875b8b6fec1cd9da6b36d35bca0bec04d1`.
This task does not load or rehash model tensors; baseline lineage is preserved
from its approved identity record. Fitting exposure and validation/model-selection
exposure are reported separately and must not be conflated.

The exact Task 2.32 compact identity files authenticate through its committed
completion receipt/output manifest. Canonical sequences, HLA, original source
locators, patient/study links and row order are unchanged. Only separate outcome
files are opened during the later support phase; no prediction file is opened.

| Cohort | N | Positive | Negative | Unique peptides | HLAs | Ordered source-ID SHA256 |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| IMPROVE>=3 | 7788 | 227 | 7561 | 6576 | 36 | `8118663ebf5c23de8f36a7a7c15aa0247a0609e04ade927657528d2986f6fee9` |
| Neoepitope primary | 267 | 57 | 210 | 265 | 46 | `9199c11b764c5e4913068125027c382d8229efc0020af743b37ed75bf6673bf7` |

IMPROVE retains its Task 2.26 hard split and prior-benchmark exclusion,70 patients,
three studies and 38 frozen patient/peptide components. Neoepitope retains its
Task 2.25 globally EL/IM-fitting-unseen primary identities and 265 peptide clusters;
patient/assay provenance is incompletely known. It is not a Hamming hard split.
Both sources are previously evaluated exploratory resources, not untouched
confirmatory datasets. All their frozen source eligibility is preserved.

## Measured-Tm sequence exposure and exact Hamming distances

All reference observations and all candidate queries are canonical9-mers.
The other 955 Tm source sequences have incompatible lengths and are not compared
by padding, truncation or artificial Hamming distances. Hamming uses literal
amino-acid equality, exact nearest witnesses, and the existing indexed search;
no full all-pairs matrix or learned similarity. Synthetic brute force validates
both close and distant queries and empty references.

The following counts use all 1493 Tm candidate observations. Pair overlap requires
the same exact HLA; peptide overlap and the first distance table ignore HLA.


| Reference | Exact pMHC | Exact peptide | d=0 | d=1 | d=2 | d>=3 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| EL_train | 1049 | 1181 | 1181 | 15 | 73 | 224 |
| EL_validation | 113 | 121 | 121 | 7 | 56 | 1309 |
| IMPROVE | 1 | 1 | 1 | 0 | 0 | 1492 |
| neoepitope | 0 | 0 | 0 | 1 | 1 | 1491 |

Same-HLA minimum-distance comparison, retaining the same 1493 queries:

| Reference | d=0 | d=1 | d=2 | d>=3 |
| --- | ---: | ---: | ---: | ---: |
| EL_train | 1049 | 16 | 53 | 375 |
| EL_validation | 113 | 5 | 27 | 1348 |
| IMPROVE | 1 | 0 | 0 | 1492 |
| neoepitope | 0 | 0 | 0 | 1493 |

The cross-HLA neoepitope neighbors are missed by a same-HLA-only rule, supporting
the prespecified conservative allele-agnostic exclusion. Full exact distance
histograms, per-HLA summaries and original nearest-sequence witnesses are saved.

After preferred exclusion, the 1490 retained Tm rows still have **1047 exact EL
fitting pairs/1179 exact fitting peptides**, and **113 exact validation pairs/
121 exact validation peptides**. These are baseline EL exposures, not IM-outcome
leakage. Any future adaptation exposes part of historical EL validation, so that
validation must not be presented as independent or used for adaptation selection.
The retained Tm panel has **zero distance<=2 neighbors of either IM cohort**.

## Preferred and alternative leakage policies

The preferred panel retains **710 A0201 + 780 B0702 = 1490** measured9-mers; **all
five flagged minima remain**. It removes exactly:

| Tm HLA | Peptide | Source row | Protected cohort | Minimum distance |
| --- | --- | ---: | --- | ---: |
| A*02:01 | FLPPAQVTV | Data 3 row 238 | IMPROVE | 0 |
| B*07:02 | SPQKVTLYL | Data 4 row 401 | Neoepitope | 1 |
| B*07:02 | APKPGGLSL | Data 4 row 539 | Neoepitope | 2 |

Both complete IM cohorts remain unchanged. The alternative was computed with the
same sequence-only threshold before outcome loading, but is not selected:

| Fixed policy | Tm retained / excluded | IMPROVE retained / excluded | Neoepitope retained / excluded |
| --- | --- | --- | --- |
| Preferred: protect evaluation | 1490 /3 | 7788 /0 | 267 /0 |
| Alternative: protect full Tm panel | 1493 /0 | 7787 /1 | 265 /2 |

After masks were frozen, descriptive class counts showed the alternative retains
IMPROVE **227 positive/7560 negative**, neoepitope **56 positive/209 negative**.
It would not solve the HLA-support blocker. Original manifests were not modified;
only separate alternative masks were written. The preference preserves useful Tm
supervision and directly comparable evaluation populations with minimal loss,
and was not chosen by outcome class balance.

## HLA-specific IM feasibility

The preferred policy retains 100% of every original IM row, including all rows
below. Every observation is a canonical9-mer. Dependence counts use original
whole-cohort patient/peptide components, even within HLA subsets, rather than
rebuilding smaller components that could inflate apparent independence.


| Cohort / HLA | N | Positive | Negative | Prevalence | Distinct peptides | Patients | Studies | Components | Positive-bearing components | Gate |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| IMPROVE /HLA-A*02:01 | 616 | 21 | 595 | 0.03409090909090909 | 610 | 26 | 3 | 16 | 7 | PASS minimum only |
| IMPROVE /HLA-B*07:02 | 555 | 8 | 547 | 0.014414414414414415 | 535 | 20 | 3 | 10 | 4 | FAIL |
| neoepitope /HLA-A*02:01 | 46 | 5 | 41 | 0.10869565217391304 | 46 | Unknown | Unknown | 46 | 5 | FAIL |
| neoepitope /HLA-B*07:02 | 20 | 5 | 15 | 0.25 | 20 | Unknown | Unknown | 20 | 5 | FAIL |

The intended IMPROVE two-HLA population has **1171 rows, 29 positives, 1142
negatives, 1137 unique peptides and 20 shared/global components in its union**.
A0201/B0702 component counts must not simply be added because some components
are shared. A0201's largest component contains 262/616 observations; B0702's
contains 382/555. B0702 has only four positive-bearing components descriptively;
no new positive-component threshold was invented after observing that number.
The component gate alone does not establish adequate precision or independence.

The alternative retains A0201 IMPROVE 615 rows (**21/594**), B0702 unchanged 555
(**8/547**); neoepitope A0201 becomes 45 (**5/40**), B0702 remains 20 (**5/15**).
Its HLA gate conclusions are identical. Both neoepitope HLAs have only 5 positives;
B0702 also has fewer than 30 negatives. The original two-HLA neoepitope subset
is 66 rows,10 positives,56 negatives; pooling cannot replace the per-HLA gate.

**A0201-only IMPROVE meets the minimum exploratory support** (21/595,16 known
components,26 patients / three studies), but it is a separate possible question,
not the intended primary and not authorized here as a replacement experiment.
No source/HLA expansion or threshold relaxation was performed. Full IMPROVE
cannot be promoted as primary to mask sparse B0702 support: only two HLAs have
quantitative Tm supervision.

## Prospective authenticated EL-decoy feasibility

Use actual Task 2.23 TRAIN-partition EL negatives only. Both pools are canonical
9-mers and have **zero duplicate pair identities/excess observations**. Resolve
any representative deterministically by earliest original prepared index.
Original source row/hash, peptide/HLA and binary label0 are preserved; the pool
contains constructed EL decoys, **not measured unstable pMHC observations**.
No decoy is assigned a Tm or a measured thermal label.


| HLA | Original unique EL negatives | Duplicate excess | Exact Tm peptide conflicts | Other authenticated EL-positive peptide conflicts | IM<=2 exclusions | Eligible unique decoys | Fixed proposed selection |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| HLA-A*02:01 | 48487 | 0 | 2 | 216 | 4 | 48267 | 11360 |
| HLA-B*07:02 | 31628 | 0 | 0 | 128 | 1 | 31499 | 12480 |

Conflict reason counts are nonexclusive. The two A0201 decoy sequence conflicts
are FPRPVTVEP and QPLARPNTL, published B0702 Tm ligands; there is **no exact
same-HLA measured-Tm pair conflict**. They are still excluded under the conservative
peptide-only policy. EL-positive conflicts are also peptide-only across all
HLAs; they do not prove that a synthetic negative at another HLA is erroneous.
Neither baseline EL labels nor historical results were altered.

All 80,115 source-negative comparisons are reported as separate actual counts below;
no pooled/approximate decoy reconstruction is used.


| Decoy HLA / benchmark | Exact pair | Exact peptide | d=0 | d=1 | d=2 | d>=3 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| HLA-A*02:01 /IMPROVE | 0 | 0 | 0 | 0 | 0 | 48487 |
| HLA-A*02:01 /neoepitope | 0 | 0 | 0 | 0 | 4 | 48483 |
| HLA-B*07:02 /IMPROVE | 0 | 0 | 0 | 0 | 0 | 31628 |
| HLA-B*07:02 /neoepitope | 0 | 0 | 0 | 1 | 0 | 31627 |

Same-HLA neoepitope distances find one A0201 d=2 neighbor and no B0702 d<=2
neighbors; the allele-agnostic rule additionally removes the cross-HLA ones.
All decoys have minimum distance>=3 to IMPROVE, consistent with its existing
hard split against EL fitting data. Five negative identities are excluded for
neoepitope proximity. Final eligible decoys have zero exact or distance<=2 IM
neighbors; baseline's pre-existing fitting exposure is unchanged.

Fixed provisional selection: **16 unique eligible decoys per retained ligand**,
per HLA, ordered by `SHA256(Task2.35-decoy-v1|HLA|PEPTIDE)` with deterministic
collision tie keys. Select 11360 A0201 and 12480 B0702, 23840 total; more eligible
identities are available than required. All D/P/T would share exactly those
identities and exposure order. No batches were materialized or optimized.
Selected per-HLA ordered identity digests:


- HLA-A*02:01: `0f7fe52a5842eb963eb22e54a254d295e0063673e19a3dc3f1e4dd49e568fdba`

- HLA-B*07:02: `73582c383d2aef6c02e4c51b698c7831bc14d262c1e165bdbc4b5e7ac0770cf0`

## Conditional A/D/P/T design and authentic structural feasibility

The proposed comparison is conceptually specifiable, but the support gate blocks
its execution as the intended two-HLA study. These settings are frozen
conditional specifications, not permission to train:

| Arm | Measured ligands | Same selected EL decoys | Adaptation |
| --- | --- | --- | --- |
| A | Existing original EL supervision | Existing original EL supervision | None; unchanged EL10 |
| D | Binary target1 | Target0 | Additional ligand/decoy control |
| P | Within-HLA permuted continuous-Tm targets | Target0 | Quantitative target-distribution control |
| T | Genuine common continuous-Tm targets | Target0 | Quantitative measured-Tm intervention |

Main contrast **T−P**, practical **T−A**, descriptive **T−D**. All adapted arms start
from identical A tensors, use exactly the same 1490 measured identities and 23840
negative identities, initial output parameters and 20-pass exposure budget.
Within-HLA permutation stream 235002 preserves full target multisets, including
flagged records. Ordering stream 235001 is independent; source IDs sorted first,
one shuffle each pass, ordinary batch 64 including a partial final batch and
all-negative batches. The provisional panel would total 25330 rows, 396 batches
per pass, 7920 updates over 20 passes. No such batches/updates were executed.
AdamW lr 0.001/native defaults and 20 complete passes are unchanged from the
provisional design, with no epoch/learning-rate search, early stopping or IM
selection. This fixed adaptation batching differs deliberately from the original
EL positive-anchor sampling; no false historical schedule equivalence is claimed.

Authenticated original BigMHC source
`199e890fa69a63646730bcecea0a520e08ca4f02`, `src/bigmhc.py` SHA256
`d3db4ac31abc478c7427295826ac2788d9cafc06e8e301fd2feb53fedb85fc8f`,
was inspected **as text/AST only**. No model was imported, instantiated or loaded.
Only `condenser.out.weight` (1×414) and `.bias` (1) may update: **two parameter
objects, 415 scalar values**. All other backbone parameters and dropout/stochastic
modules must stay frozen, with whole-model eval mode retaining autograd for the
last parameters. The native logit applies an HLA boolean mask to
`out.weight * attention`, sums selected terms and adds the bias.

Technical conditions: native forward reads output weights directly and does not
call `out.forward`, so an ordinary out-module hook will not expose features.
Do not use the historical four-parameter IM transfer list (it also updates the
attention projection). Do not wrap the full optimization forward in `no_grad`.
Do not use native positive-anchor batching or silently skip all-negative batches.
These are implementation objections to an unsafe shortcut, not new architecture
or hyperparameter variants. They can be addressed without model changes, if a
scientifically adequate future protocol is independently authorized.
The final coefficients are shared across HLA input encodings. AdamW decay can
also change output coefficients without A/B data gradients; backbone freezing
does not guarantee absence of unsupported-HLA negative transfer. That is a
reason to retain the full-cohort secondary check, not to tune decay using IM results.

If support were adequate, the proposed primary would be **equal-weight macro
non-interpolated within-HLA IM AP for A0201/B0702 on unchanged IMPROVE>=3**.
HLA AP/AUROC, AP relative to HLA prevalence, fixed top-K, supported neoepitope,
and full IMPROVE negative-transfer checks would remain secondary. Paired
uncertainty must resample original global patient/peptide components jointly
across both HLA contributions; unknown patient links/one-class resamples cannot
be repaired by choosing favorable rows. No metric was calculated in this task.

## Final feasibility decision and limitations

Source counts, target validity, unambiguous identities, conservative adaptation
leakage control, fixed decoys and structural last-layer adaptation all pass.
**The intended two-HLA primary fails the prospectively frozen support gate.**
Switching leakage policies cannot create the missing B0702 positives. Accordingly
**NO-GO for the subsequent intended training experiment**, with the original
external manifests preserved. A0201-only support is described transparently and
is not promoted to a replacement primary. No new HLA, benchmark, label, relaxed
threshold or favorable subset was introduced.

Measured Tm and kinetic half-life remain distinct. The source's author HLA
assignments, repeated minima, residual C1R expression and lack of per-row raw
curve traceability remain limitations. Baseline EL fitting/selection exposure,
synthetic-decoy semantics, large dependence components, sparse positives and
previous benchmark use further limit generalization. Feasible source curation
does not establish that Tm adaptation improves IM ranking, that poor Tm means
EL-label error, or that any training result would be confirmatory.

## Focused checks, runtime and persisted evidence

**11/11 focused unittest checks pass**, zero skipped, 0.106 seconds on actual
WSL2 Python 3.13.5. Tests cover original workbook counts, numeric units/target,
nonfinite/out-of-range/duplicate rejection, repeated-minimum retention, source
row/HLA alignment, label-blind cross-HLA leakage exclusion, exact indexed Hamming
against a small brute-force reference including distant/empty cases, support
gate boundaries, source-only architecture inspection and exclusive serialization.
An initial synthetic Decimal comparison used default 28-digit precision against
the parser's50 digits; the test was corrected to the same exact precision before
execution. No source parsing discrepancy or scientific eligibility change occurred.

The [saved-evidence verifier](../scripts/verify_measured_tm_preflight.py) passes:
1493 source candidates / 1490 eligible, 11944 literal witness-distance checks,
23840 exact deterministic selected negatives, original cohort preservation,
pre-outcome identity freeze and unchanged NO-GO gate. It checks saved identities
and witnesses without model or IM performance calls. A completion log and all
source/identity/class-count execution logs are preserved.

Identity/overlap/decoy phase: **85.74323269596789 seconds**, CPU user 85.162297s,
peak RSS 468893696 bytes. Outcome support phase: **0.16912050091195852 seconds**,
peak RSS 63688704 bytes. Platform
`Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.43`.
No GPU or ML-library execution, training, inference, feature extraction, tuning,
calibration or IM-performance calculation. No raw MS download, CapsNet access,
new backup archive, historical-result revision, merge or push.

Scientific artifacts are outside Git under resolved project runs /
`task-2_35-measured-tm-eligibility-preflight/`: source provenance/counts, compact
all-length and9-mer manifests, preferred inclusion flags/reasons, original cohort
references, exact/same-HLA/allele-agnostic distance witnesses and summaries,
alternative identity masks, supported-HLA class/dependence tables, candidate and
provisional selected decoy identities, static implementation specification,
NO-GO decision, tests and execution evidence. Raw data stay under project data.
The preferred manifest retains all 1493 candidate rows with explicit eligibility
flags, preserving all three exclusions rather than silently dropping records.


Final output manifest: **35 files**, SHA256
`e3f6702a2900393372dc5ba99c031bcba44130dbbc02a0c2679ce9113f742e73`. This Git report pins that manifest; the manifest excludes its
own hash and the final report to avoid a circular hash. No further experiment
was started. The task stops at this completed data-only feasibility assessment.
