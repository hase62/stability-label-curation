# Task 2.29A — Monoallelic replicate rescue

Completed on Z790 WSL2, 2026-10-20, from approved Task 2.28 commit
`837e4eeed9f3debf1dd253f8a9a50c6b865892f9`, on
`task/2.29a-monoallelic-replicate-rescue`.

**GO for dataset construction: an authentic, run-resolved monoallelic biological
triplicate has been recovered and frozen. NO-GO for executing the association
now: the original frozen Teacher checkpoint and fitting/validation metadata are
still unavailable.** The primary candidate is HLA-A*02:01, with 1,536 unmodified
9-mers in its three-run union and 671 peptides in its predefined index run.
One cell-line/HLA context cannot support generalization across biological
contexts. Task 2.28's results, multi-HLA restriction blocker, and historical
conditional protocol have not been changed.

## Authenticated acquisition and immediate gate

Source: SHERPA, *Precision Neoantigen Discovery Using Large-scale
Immunopeptidomes and Composite Modeling of MHC Peptide Presentation*,
[DOI 10.1016/j.mcpro.2021.100111](https://doi.org/10.1016/j.mcpro.2021.100111),
[original full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC8318994/),
[PRIDE PXD023064](https://www.ebi.ac.uk/pride/archive/projects/PXD023064).
Only its in-house experimentally transfected K562 monoallelic observations are
used. Tumor deconvolution, public reaggregated training data, synthetic negatives,
and SHERPA predictions are outside this curation.

The PRIDE API project and complete 65-file inventory were saved. The original
processed outputs were acquired from the deposited
[PRIDE directory](https://ftp.pride.ebi.ac.uk/pride/data/archive/2021/06/PXD023064/):

| File | Bytes | SHA256 |
| --- | ---: | --- |
| `PMS_ions.mono-allelic.csv` | 499,814,735 | `bb135c0e32717428105e033f47f16385a98144ac3da924abd4a529288b34fdf6` |
| `metadata.xlsx` | 49,125 | `b5685e10d6771a755ff54a90968f281c5b465f73a87e1a456042105dacb26d1b` |
| `peptides_filtered.xlsx` | 5,460,756 | `132770c39a9e08ffb97afdec4fa77bb2cbf83fb6bc6fad2826d6c886056480f0` |
| `PXD023064_community_annotated.sdrf.tsv` | 51,639 | `6bd4b41deec1f129c8606ec0699ee6deddc46452abc72500fd310c90dde756e9` |

The first three files also passed PRIDE's deposited SHA1 checksums, respectively
`424881b5d4b2d62ed4199d73787015fab91395e2`,
`da015a62f6a2222d46aab590d5325d7104224bae`, and
`86a6cdab95ba67362b6d5e29ffa44749c42ce4e2`.
Each acquisition has a sidecar containing original/resolved URL, retrieval time,
HTTP headers, byte count and SHA256. The large CSV was streamed with bounded
range requests and verified as one complete original file; no RAW files were
downloaded. A 65,536-byte range was inspected and retained as the immediate-gate
witness before acquiring the complete processed CSV.

The authentic paper XML and the 10,270,040-byte Europe PMC supplementary archive
were also saved. The latter was needed to read the small original supplementary
postprocessing script, nested inside `mmc7.zip`; the other supplemental files
were not used to generate additional cohorts. The original script was inspected,
not executed. No additional Python dependency was installed.

The immediate gate passed before full CSV acquisition: its fields include
`Peptide`, `pepSeq`, `Source File`, `scan`, `fileID`, `ion`, `modification`,
retention time, charge, precursor m/z and protein accession. Author metadata
joins each raw filename to its transfected HLA. The deposited community SDRF
adds biological sample, biological/technical replicate labels, instrument,
dissociation method, enrichment and search parameters. Original Excel/CSV row
numbers and complete SDRF header/value arrays are preserved, including repeated
SDRF modification-column names. An aggregated filtered peptide list alone was
not used to infer run detections. The fallback MassIVE source was unnecessary
and was not searched or downloaded.

## Identification and chemical-state policy

The paper describes PEAKS Studio 10.0 searches against the 2019-03-20 SwissProt
human proteome, unspecific cleavage, 10-ppm precursor and 0.02-Da fragment
tolerances, and 1% decoy-estimated PSM FDR. Individual PSM q values/PEPs are not
in the released ion table. We do not assign q=.01 to each PSM or claim a newly
estimated 1% FDR for this restricted cohort.

The frozen source parser ports the original supplementary script's grouping:
modified peptide, base sequence, scan, raw filename and fileID define a PSM.
At least ten nonempty fragment-ion rows and at most two candidate peptides per
scan/raw/fileID are required. Fragment rows, repeated scans and protein mappings
never become separate replicate detections. A peptide–HLA pair must additionally
appear in the released `Mono-allelic peptides` worksheet; this retains the
authors' accepted peptide identity set after background/polymer/motif QC.
Manual motif and background filtering are not re-estimated from our cohort.
All excluded PSMs and their reasons remain in the observation manifest.

Only canonical uppercase 9-mers enter candidate matrices. The source searched
fixed cysteine carbamidomethylation, variable methionine oxidation and N-terminal
acetylation. Unmodified eligibility requires raw `Peptide == pepSeq`, no
modification annotation, and no cysteine under that fixed-CAM search. Cysteine
and other modified molecular species remain in separate modified-species
matrices, with the original sequence annotations. No modified-only detection
is converted into an unmodified detection or silently given a Teacher score.

Every retained detection has original run/scan fragment-ion evidence; no
transfer-only or intensity-only detections were added. The publication does
not explicitly state an MBR setting. Direct-versus-transfer status is therefore
established by the evidence used here, rather than a claim that every upstream
software option is known. An unobserved peptide in a performed run is a **direct
identification nondetection**, not cell-surface absence or a false EL positive.
The union remains conditioned on discovery in at least one run.

## Run identities and replicate interpretation

Author metadata contain 60 meaningful raw-file assignments: 46 monoallelic
runs, two null/GFP controls and 12 tumor runs. The monoallelic table contains
48 source runs, including those two controls; no tumor PSMs enter it. All 46
monoallelic runs have original PSM evidence. They span 29 deposited biological
sample identities and 25 exactly normalized HLA-A/B alleles.

The source reports stable single-HLA/B2M transfection of K562, surface W6/32 flow
confirmation and W6/32 immunoprecipitation, with mock-transfection background
removal. HLA attribution here is experimentally defined by this source system,
not by binding predictions, genotype deconvolution or Teacher output. W6/32 is
pan-HLA-I: individual ligands do not each have an independent allele-specific
restriction assay, and residual/background presentation cannot be proved zero.

The manuscript's aggregate design counts (28 cell lines, one biological
triplicate, 20 split acquisitions) do not completely reconcile with the released
run mapping. Counts here follow the deposited identities. The three A*02:01
biological labels come from the **community-annotated SDRF**, supported by three
distinct sample IDs in the author mapping and the manuscript's stated biological
triplicate. No laboratory notebook or culture-date table establishes additional
independence. A*31:01 and B*35:01 have two SDRF-labeled biological samples each;
they are retained descriptively and do not meet the three-unit primary gate.
The paper also describes both 5e9-cell processing and expansion to 500 million
cells, without per-run input amounts. Exact equality of input, culture batch,
recovery and injection amount cannot be verified.

The primary biological group uses the **first CID injection** per sample, fixed
by SDRF technical label 1 and author worksheet order before processing detections:

| Order | Biological sample | Run | Direct unmodified 9-mers |
| --- | --- | --- | ---: |
| 1, index | `K562-HLA-A02:01-37882` | `MSB37882A.raw` | 671 |
| 2, repeat | `K562-HLA-A02:01-33405` | `MSB33405A.raw` | 920 |
| 3, repeat | `K562-HLA-A02:01-35123` | `MSB35123A.raw` | 1,070 |

The latter two samples also have B injections. Their extra injections are not
pooled into the primary numerator, avoiding unequal 1/2/2 acquisition effort.
Their separate same-preparation CID comparisons remain available. All use
Lumos DDA and the reported 2-hour LC method. Actual culture/preparation batch
effects and run-level QC/precursor selection remain possible confounders.

There are **three biological groups** (one triplicate, two pairs), **nine
same-preparation, same-method CID technical pairs**, and **eight CID/EThcD
method-comparison pairs**. The last eight have no pooled detection frequency or
exchangeable-replicate denominator. They cannot supply biological or same-method
replicates. Seven other monoallelic runs have no comparable repeat group.

## Exact candidate and detection counts

The source has 3,335,020 fragment-ion rows and 166,197 PSM groups. Mutually
exclusive PSM statuses, in frozen precedence order, are:

| Status | PSMs |
| --- | ---: |
| Null control | 2,008 |
| Not canonical 9-mer | 71,768 |
| Fails released per-PSM fragment/chimera QC | 8,466 |
| Outside released filtered peptide–HLA set | 1,373 |
| Retained unmodified 9-mer | 78,283 |
| Retained modified/fixed-CAM 9-mer species | 4,299 |

The filtered workbook contains **47,263 unique peptide–HLA pairs**, of which
**27,418 are canonical 9-mers**. Reconciliation finds 26,435 pairs with accepted
unmodified direct PSMs, 711 with modified-only accepted PSMs, and 272 without
qualifying run PSMs under the released code's rules. Those 272 are explicitly
listed; their detections are not invented from the aggregated workbook.

Across all 46 monoallelic runs, the unmodified set has **26,435 peptide–HLA
pairs, 20,397 distinct peptides and 25 alleles**. Modified records comprise
**1,696 molecular-species–HLA pairs**. Among the 12 comparable biological or
technical groups there are **13,580 peptide–group rows**, **11,382 unique
peptide–HLA pairs**, **10,436 distinct peptides**, **10 alleles**, and 23 distinct
raw runs. These group rows overlap and must not be counted as independent
experiments.

The primary A*02:01 union contains **1,536 unmodified 9-mers**, with **776
detected in one**, **395 in two**, and **365 in all three** biological units;
none can have four detections. A separate 118 modified-species union is retained.
The **671 index-conditioned peptides** have reserved-repeat counts of **99
in zero**, **207 in one**, and **365 in both** of the two reserved biological
repeat runs. The index cohort was not selected for repeat success.

Other comparable groups have these unmodified counts; `MSB<identity>A/B.raw`
denotes the original A/B filenames, in the frozen order:

| Type, HLA, sample/run identities | Union | In one | In both | Per-run direct counts |
| --- | ---: | ---: | ---: | --- |
| Biological A*31:01, 37881A / 37885A | 544 | 234 | 310 | 373 / 481 |
| Biological B*35:01, 37884A / 37878A | 1,380 | 583 | 797 | 1,155 / 1,022 |
| Technical A*02:01, 33405 A/B | 1,201 | 657 | 544 | 920 / 825 |
| Technical A*02:01, 35123 A/B | 1,303 | 498 | 805 | 1,070 / 1,038 |
| Technical A*11:01, 33408 A/B | 626 | 384 | 242 | 582 / 286 |
| Technical A*24:02, 33407 A/B | 1,316 | 548 | 768 | 1,128 / 956 |
| Technical A*33:03, 33659 A/B | 752 | 205 | 547 | 662 / 637 |
| Technical B*07:02, 33410 A/B | 1,093 | 647 | 446 | 867 / 672 |
| Technical B*40:01, 33411 A/B | 1,545 | 734 | 811 | 1,243 / 1,113 |
| Technical B*51:01, 33409 A/B | 978 | 397 | 581 | 831 / 728 |
| Technical B*57:01, 33663 A/B | 1,306 | 446 | 860 | 1,039 / 1,127 |

The nine technical groups contain 10,120 peptide–group rows and 9,386 distinct
peptide–HLA pairs across eight alleles. They characterize injection-level
reproducibility, not independent cell preparations. Two-unit groups remain
outside the existing primary association protocol's three-unit gate.

## Exact Teacher support and restore feasibility

The original definition remains `configs/stability_teacher_v0.json` and
`stability_teacher.py`: per-exact-allele human HLA-A/B, canonical 9-mers,
180 position/amino-acid features, ridge alpha 10, minimum 20 fitting rows,
log1p measured kinetic half-life in hours. No melting-temperature model,
family-based fallback or substitute predictor is introduced.

The authenticated Task 2.13 `positive_score_manifest.json` SHA256 is
`e79fb60b1c04f33889e9d3ecd6a7bd145255c156487cd4d4873a90c8ab715862`.
Its **`supported_HLA` field enumerates all 67 trained models**, as verified in
its generating code, rather than the 49 alleles with positive-score rows in
`positive_counts_by_HLA`. This additional metadata inspection resolves support
beyond Task 2.28's partial used-allele receipt without revising its report.
No stored prediction values were read.

**Supported (20):** HLA-A*01:01, A*02:01, A*03:01, A*11:01, A*24:02,
A*26:01, A*29:02, A*30:02, A*31:01, A*33:03, A*68:01; HLA-B*07:02,
B*15:01, B*18:01, B*35:01, B*40:01, B*51:01, B*57:01, B*58:01, B*81:01.
Every comparable biological/technical group's exact allele is supported.

**No trained exact allele model (5):** HLA-A*02:52, HLA-B*15:11,
HLA-B*15:13, HLA-B*15:18 and HLA-B*44:03. Nearby A*02/B*15/B*44 models do
not establish support. Support is not proof of good held-out accuracy for an
allele; original validation reports are still required.

The expected frozen Teacher is resolved project runs /
`task-2_3-first-stability-teacher/checkpoints/teacher_model.json`, SHA256
`a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99`.
It is absent, as are the original fitting partition and kinetic observation
registry. A focused check of the approved artifact registry, Teacher-specific
reconstruction entry and established local checkpoint-package manifest found
**no exact-byte restore artifact**. The Teacher entry is R2,
`exact_byte_backup: false`, with `requires_training: true`; its reconstruction
recipe was not executed. The local checkpoint archive describes BigMHC, not
this Teacher. No broad artifact search, model download, retraining or backup
was performed. Restoring the original Teacher plus fitting/validation metadata
is a concrete missing dependency, not something curation can replace.

## Exposure and confounders

Existing authenticated Task 2.26 sequence snapshots were reused; no historical
predictions, outcomes or benchmark results were reanalyzed. Exact sequence
overlaps are descriptive flags, not eligibility exclusions:

| Reference | Distinct sequences, all 20,397 peptides | Pair rows, all 26,435 | Primary union | Future index |
| --- | ---: | ---: | ---: | ---: |
| Actual BigMHC EL fitting | 11,254 | 15,288 | 1,128 | 522 |
| EL epoch-selection validation | 1,296 | 1,821 | 133 | 53 |
| Final IM fitting | 9 | 13 | 7 | 5 |
| Historical IM development | 0 | 0 | 0 | 0 |
| Prior published Mendeley benchmark | 1 | 1 | 0 | 0 |

These categories overlap and cannot be added. BigMHC exposure is not equivalent
to Teacher fitting exposure. Actual Teacher fitting sequences remain unavailable;
exact/one-substitution exposure to them cannot yet be verified. Peptide–HLA
training overlap or source-publication independence is not claimed from these
sequence-only references.

Available confounder metadata include run/sample/HLA, acquisition method,
precursor m/z, charge, RT, source protein accession, fragment counts,
modification and scan identity. The recorded **ion intensity is fragment-ion
intensity**, not quantitative precursor peptide abundance; it must not be used
as the protocol's peptide-abundance covariate. There is no matched per-run
precursor area, protein abundance or individual q value in the prioritized
outputs. The paper reports representative transcript profiling, but no matched
per-replicate expression covariate has been established here. No additional
expression data were imputed or acquired.

Important remaining confounders are DDA precursor sampling, peptide abundance,
protein expression/turnover, ionization, hydrophobicity, fragmentation propensity,
search confidence, preparation recovery, culture/acquisition batch and unequal
run depth. FDR/background/aggregate peptide selection and discovery conditioning
also affect the endpoint. Stability cannot be isolated causally from these
factors using this curation. In particular, MS stochasticity is not evidence of
a change in cell-surface pMHC abundance or an incorrect EL label.

## Frozen outputs and execution

Portable source root: resolved project data /
`monoallelic_replicate_rescue_task2_29a/`. Derived root: resolved project runs /
`task-2_29a-monoallelic-replicate-rescue/`. Data and generated outputs stay
outside Git. Paths are resolved exclusively through `stability_label_curation.paths`.

The immediate gate and design freeze preceded large-scale processing. The
design freeze was saved at `2026-10-20T05:59:08.018663+00:00`; the final freeze
at `2026-10-20T06:03:56.042232+00:00`. No Teacher predictions were accessed
at any stage. Important outputs:

- `manifests/monoallelic_runs.jsonl`, `excluded_runs.jsonl`,
  `replicate_groups.json`, `design_freeze.json`: original run/condition hierarchy.
- `observations/PSM_observations.jsonl`: all 166,197 PSM groups, original CSV
  row ranges, scan, raw file, chemical annotations, source covariates and QC.
- `matrices/`: separate unmodified and modified group matrices and sparse
  all-run peptide–HLA presence, retaining original PSM links.
- `manifests/primary_biological_union.jsonl`: SHA256
  `e3a7b12053de9d407d273f77780199ef8f3a25d880bd307b5239a031e5c03aa4`.
- `manifests/future_primary_index_cohort.jsonl`: SHA256
  `fc3f18266eef091b13903db1aca44715fcfe3199bad9fdcbfaceaa96fae6d50d`.
- `manifests/published_9mer_pair_reconciliation.jsonl`, `sequence_exposure.jsonl`:
  explicit missing/modified-only source pairs and reference flags.
- `reports/`: per-run/group counts, Teacher feasibility, overlaps, validation,
  focused-test log, execution evidence and the complete `dataset_freeze.json`
  source/derived hash inventory. All writes are exclusive; existing cohorts
  are not silently overwritten.

The final `reports/dataset_freeze.json` SHA256 is
`06567f225b07e1642ddd46e2fd349863b48b4cdc0dec5bd8d6fbb62d50985f46`.
All 42 pinned source, derived and implementation hashes passed the final check.

Implementation: `src/stability_label_curation/monoallelic_replicate_rescue.py`.
After authentic acquisition and the documented immediate gate, its stages are
`freeze-design`, `curate`, `support`, `validate`, `finalize`, invoked with
`PYTHONPATH=src python -m stability_label_curation.monoallelic_replicate_rescue <stage>`.
These commands refuse existing output replacement; they are not instructions
to rerun the frozen curation. Source receipts preserve original acquisition URLs.

**Focused tests: 16 passed** (seven new parser/chemical/replicate tests plus nine
existing replicate semantics tests). Saved validation checked 22,789 unmodified
or modified matrix rows, 35,641 direct-detection cells and links to 65,814
original accepted PSMs; all 3,335,020 source ion-row references are conserved.
Checks cover exact alleles, original Excel coordinates/formula rejection,
fragment-to-PSM collapse, chimera/fragment thresholds, chemical state, unequal
injection hierarchy and CID/EThcD separation. No broad test suite/audit was run.

CPU curation: 14.62 seconds process wall time (14.11 user + 0.49 system CPU
seconds), peak RSS 488,332 KiB, no swap; internal curation timer
14.496565927984193 seconds. The final resumed parallel processed-CSV acquisition
took 271.15892592299497 seconds, excluding earlier bounded/sequential reads.
Execution was Python 3.13.5 on x86_64 Linux
`6.18.33.2-microsoft-standard-WSL2`; no GPU computation occurred.

The [conditional protocol amendment](REPLICATE_STABILITY_ASSOCIATION_TASK2_29A_AMENDMENT.md)
freezes this source and index/repeat definition for a separately authorized
future task. A narrowly interpreted within-A*02:01 descriptive association is
scientifically possible after authentic Teacher restoration. There is only
one independent biological group, so the existing component bootstrap cannot
provide a confidence interval or biological-population inference. No Teacher
scores, associations, permutations, regressions, A/S/P evaluation, training,
tuning, model changes, RAW downloads or new backup archives occurred.
