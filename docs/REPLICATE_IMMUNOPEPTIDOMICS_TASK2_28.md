# Task 2.28 — Replicate immunopeptidomics feasibility and curation

**Completed on Z790 WSL2, 2026-10-20.** Authentic PXD006939 processed outputs
support reproducibility descriptions for **54 distinct HLA-I MS runs**, **12
samples** and **16 comparable base replicate groups**. Those groups contain
**58,740 peptide–group observations / 36,055 distinct canonical 9-mers**.
Original observations, run names, nested replicates and direct-versus-transferred
identification states are preserved. No stability prediction or association was
performed.

**The allele-specific kinetic-stability association is not ready:** every curated
sample is multi-HLA, so there are **zero experimentally restricted peptide–HLA
observations eligible for the primary stability analysis**. The original frozen
Teacher JSON is also absent on this machine. These are separate dependencies:
restoring the model would not establish peptide restriction.

Branch: `task/2.28-replicate-el-detection-curation`, based directly on
`24659cfb830826673b5b0f834e7b14a5a7d1afd6`. Curation code and source/group rules
were committed before curation. Initial commit `321d376` encountered a metadata
sidecar filename issue before matrix generation; its two partial receipts are
preserved as `reports/attempt_1_*`. Commit `97cc98d` fixed that reader and
produced the successful curation. `6869461` adds technical assessment, focused
completion checks and the separate conditional Task 2.29 protocol. The final
report commit and clean worktree are sealed in the external finalization manifest.

## Authentic sources assessed

| Source | Scientific assessment | Acquisition/use in this task |
| --- | --- | --- |
| [PXD006939](https://www.ebi.ac.uk/pride/archive/projects/PXD006939), Chong et al. / Bassani-Sternberg group, DOI [10.1074/mcp.TIR117.000383](https://doi.org/10.1074/mcp.TIR117.000383) | Published high-throughput HLA-I/II workflow, original typing and replicate design, MaxQuant direct and matching flags | Selected; 16 original search-output members acquired, metadata and author processed exports preserved; HLA-II excluded |
| [PXD012797](https://www.ebi.ac.uk/pride/archive/projects/PXD012797), Ghosh et al., DOI [10.1074/mcp.C119.001652](https://doi.org/10.1074/mcp.C119.001652) | JY pan-HLA-I assay validation; repeatability, between-day precision and synthetic-spike experiments | Original metadata/file inventory assessed; no peptide counts or matrices claimed from unparsed MSF files |
| [PXD013831](https://www.ebi.ac.uk/pride/archive/projects/PXD013831), Solleder et al., DOI [10.1074/mcp.TIR119.001641](https://doi.org/10.1074/mcp.TIR119.001641) | Phosphorylated HLA-I aggregation with reused studies and mixed samples; not a clean monoallelic replicate panel | Metadata/file inventory assessed; giant processed archives not downloaded |
| [MSV000080527](https://massive.ucsd.edu/ProteoSAFe/dataset.jsp?task=a67baac756f5421faf51c5d4bac3005f), Abelin et al., DOI [10.1016/j.immuni.2017.02.007](https://doi.org/10.1016/j.immuni.2017.02.007) | Genuine engineered monoallelic HLA-I study; plausible alternative for restriction | Primary article and repository metadata assessed; an authenticated per-run processed export and complete comparable-replicate mapping were not recovered through the accessed endpoints |

PXD012797 lists 60 files: 30 RAW and 30 processed Proteome Discoverer MSF files.
Deposited names distinguish nine repeatability runs, nine intermediate-precision
runs and twelve runs across four synthetic-spike concentrations. Do not infer
five exchangeable replicates from the paper's generic instrument-method wording.
MSF files are approximately 196–219 MB each. The selected PXD006939 already
provides processed replicate detections, so those additional files and RAW files
were not necessary. JY remains a multi-HLA sample. MBR use is not established for
this source. Its PRIDE protocol states q≤0.05 (5% FDR), while the article prints
q≤0.05 with a parenthetical 1% FDR; that inconsistency needs actual export/search
resolution before using it. No favorable FDR interpretation was chosen here.

PXD013831 lists 211 files, including processed containers of 36,637,023,012 and
133,646,815,232 bytes. Neither was downloaded. Eighteen exact selected original
HLA-I RAW names also occur in that inventory; it cannot be treated as independent
replication merely because its accession differs. Phosphorylated ligand chemistry
also differs from an unmodified 9-mer kinetic Teacher.

Abelin's article describes 16 monoallelic lines and biological replicate overlap.
The acquired original MassIVE page identifies task
`a67baac756f5421faf51c5d4bac3005f`; its acquired file-list page embeds an empty
`row_data` array. This does not prove that the repository has no files. Europe
PMC's supplementary endpoint returned a 296-byte XML "not open access" error
under HTTP 200, not a ZIP; original XLSX links returned HTML browser-check
responses. No error page was parsed as experimental data, no access restriction
was bypassed, and no unvalidated reconstructed table was substituted. Precisely
missing for curation are authenticated per-run peptide identifications and their
comparable run/sample hierarchy, chemical-state and confidence metadata.

## Acquired PXD006939 provenance

External source storage: resolved project data /
`replicate_immunopeptidomics_task2_28/`. Derived storage: resolved project runs /
`task-2_28-replicate-el-detection-curation/`. All storage resolution uses
`stability_label_curation.paths`; generated data and source bytes are outside Git.

- Original PRIDE v2 project metadata and all file-inventory pages were retained
  for each requested accession, with request URL, HTTP headers, retrieval UTC,
  response size and SHA256. PXD006939 lists 125 files.
- The original [Alloutputtables.zip](https://ftp.pride.ebi.ac.uk/pride/data/archive/2017/12/PXD006939/Alloutputtables.zip)
  is 10,523,036 bytes. Its observed SHA1 matches PRIDE's
  `1e929a5f06ea1bbb9dadecd071fa09e4c87a7177`. This small export lacks per-run
  identification-type flags and is insufficient for a direct-MS/MS endpoint.
- The original [search.zip](https://ftp.pride.ebi.ac.uk/pride/data/archive/2017/12/PXD006939/search.zip)
  is declared as 626,695,636 bytes, SHA1
  `f2319bf637af1056c96bd1f0192923400e0374ae`. Only its central directory and
  selected member byte ranges were acquired. Responses had to honor exact
  ranges, archive size and ETag. Original members pass ZIP CRC32 and have local
  SHA256 receipts. **The full search.zip SHA1 was not verified**, because the
  full archive was not downloaded. No compressed-byte range was treated as an
  MS observation or executed.
- Selected members are `peptides.txt`, `experimentalDesignTemplate.txt`,
  `parameters.txt` and `summary.txt` from plates 1/2, class-I sensitivity,
  IFNγ "matched separetly" and interplate searches. The alternative "matched
  all" IFNγ search, class-II sensitivity, tryptic proteomics and `msms.txt`
  spectrum-detail tables were not needed or downloaded.
- Original article XML and its 14,384,036-byte supplementary package were
  preserved from Europe PMC. Supplemental Tables S1 (typing), S2 (replicate
  design) and S3 (heavy standards) were extracted as original PDFs and their
  text retained. An isolated `pypdf==6.21.1` environment was used only to read
  these otherwise unavailable metadata tables; the curator itself uses only
  the Python standard library. No model environment was changed.
- The community-annotated SDRF was retained as secondary metadata. Published
  pooled-lysate aliquoting and Table S2 take precedence over its biological-
  replicate labels. All source names, spelling discrepancies and mappings are
  documented rather than silently corrected.

| Original peptide-table member | Expanded bytes | Observed SHA256 |
| --- | ---: | --- |
| plates_1_2 / peptides.txt | 81832349 | `f75d1a4dde21eb4b0dde5e2d6d10c0c972e75d5177c136bbc6d8e52a00aeae3f` |
| plate_3_class_I / peptides.txt | 4652624 | `00d82e993cc7b90b574050bbd66dc7c87890cf13f80428689ac02929b4cd08b8` |
| plate_4_separate / peptides.txt | 3261781 | `79645a8f97099e47eb040dc409157cdd436aa3f10bbc78377e9f043fe98e3bdd` |
| interplate / peptides.txt | 3863004 | `a472dabea7424ec6f31c22208de9996aeb91a3b48fff28fb93ef734711caffb0` |

Original rows retain source member/block, one-based data row and line, MaxQuant
peptide ID, original sequence, raw-row SHA256, PEP, score, protein/gene strings,
modification/evidence/MSMS IDs, exact identification types and original
intensities. The source files themselves remain unchanged. Full URLs, hashes,
checksums and HTTP range receipts are in `source_acquisition_manifest.json`,
`processed_export_authentication.json` and source-side provenance files.

## Replicate definitions and run identity

1. **Plate 1:** seven cell-line samples have three preparation aliquots from
   pooled lysate, 1e8 cell equivalents each. These are preparation replicates,
   not three independent donors/cultures. CD165 has a published heavy-standard
   spike protocol. RA957 has two instrument injections of each preparation;
   its preparation matrix has three units, each aggregating the two injections
   by direct-identification OR. Three separate two-injection instrument matrices
   are preserved as diagnostics, without pooling them as independent evidence.
2. **Plate 2:** 3830-NJF has three sections, 3849-BR two, and 3865-DM/3912-BAM
   one each. Sections are biological/tissue-preparation replicates of the same
   patient, not independent patients. Section inputs range 0.7–1 g for repeated
   tissues, with potential heterogeneity. Singletons are retained descriptively
   and excluded from repeat-comparison totals.
3. **Sensitivity:** CD165 1e7, 3e7, 5e7 and 7e7 cell inputs each form their own
   three-preparation group. Different inputs and acquisition batches are not
   exchangeable replicates. The 1e8 view reuses exactly the three plate-1 CD165
   RAW measurements; it is saved separately as an alternative processing view,
   not three new runs or a second independent group.
4. **Plate 4:** four control and four IFNγ-treated UWB1.289 cell pellets,
   1.5e8 cells each, form separate biological groups. Treatment is 100 IU/ml
   IFNγ for 24 h. The conditions are never pooled; half the eluate is injected.
5. **Interplate JY:** three preparations on 2017-04-21, 05-09 and 05-16,
   with new reagents/plates and 1e8 cells per preparation, form a between-day
   preparation/batch group. Independent culture status is not established.
   These are distinct from the plate-1 JY group.

Original Table S2 records one-third injection for plates 1–3 and interplate,
and one-half for plate 4. Its BR/PR/MSR hierarchy is retained, rather than
assuming every numbered file is biological. ExperimentalDesign `Fraction`
values also identify processing/matching groups; they are not counted as
additional independent specimens.

There are **54 unique original HLA-I RAW run identities**, **57 search views**
(three reprocessed CD165 files), **18 base groups including two singletons**, and
**three overlapping instrument diagnostics**. An additional alternative-view
matrix retains all CD165 1e8 processing-specific calls. All 54 runs are mapped
in original design and summary files and have recorded acquisition/MSMS counts.
Fifty-one original search names exactly match deposited PRIDE RAW names; three
CD165 names include `spike` in the paper/search design but omit it in the deposit.
The explicit name-only aliases are retained. RAW bytes were not compared, so
this is not a raw-file checksum equivalence claim.

## Canonical 9-mers and identification semantics

Normalize by strip/uppercase, require nine canonical amino acids, remove original
reverse and potential-contaminant flags, and retain original accepted search
identifications. A class-II-only identification cannot create an HLA-I row.
Duplicate base sequences within a source view or unknown identification types
fail rather than being silently collapsed or inferred. PEP is preserved; it is
not silently converted into a per-run q-value or used as a new FDR cutoff.

All four original parameter files record MaxQuant 1.5.5.1, PSM FDR **0.01**,
protein FDR **1** (no restrictive protein FDR), MBR enabled, matching window
**0.7 minutes**, alignment window **20 minutes**. The manuscript describes a
0.5-minute matching window; the actual archived parameter value is retained.
Nominal pooled search FDR does not certify an identical per-group or 9-mer FDR.
No new spectra search or PSM rescoring was performed.

`By MS/MS` is a direct-identification success. `By matching` is a transferred
identification and is not a direct success. Blank is not identified in that
performed run; it is not inferred from zero intensity. Each matrix explicitly
preserves both direct and transfer-inclusive binary states and fractions with
the same known denominator. No missing intensity was imputed into a detection.
Each preparation unit with multiple injections is direct-positive if at least
one of its own injections is direct; all original injection states remain.

| Source view | Original peptide rows | Reverse | Contaminant | Invalid/non-9-mer | No HLA-I identification | Retained HLA-I 9-mer rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| plates_1_2 | 122015 | 2961 | 2948 | 78856 | 284 | 36966 |
| plate_3_class_I | 9289 | 179 | 121 | 2861 | 0 | 6128 |
| plate_4_separate | 7221 | 138 | 78 | 3534 | 0 | 3471 |
| interplate | 9784 | 176 | 717 | 7742 | 35 | 1114 |

These are sequential exclusions, reverse then contaminant then sequence validity
then HLA-I observation. Source views include different experiments and reused
processing; their retained-row counts must not be summed as distinct peptides.
There are **39,735 distinct HLA-I 9-mer sequences across all four original views**,
**39,478 across the chosen 18 base-group matrices**, and **36,055 in the 16
comparable base groups**. The alternate search contributes some processing-
specific sequences; all are preserved without calling them new measurements.

Across the chosen **54 unique run views**, accepted peptide–run cells include
**130,976 direct MS/MS** and **57,120 transferred-only** identifications. These
are peptide/run states, not counts of spectra or independent biological units.

## Detection-count distributions

Counts below are peptide–group observations in the directly identified union;
the same sequence can appear in several groups and must not be interpreted as
several independent peptides. Each row retains its own denominator and hierarchy.

| Group | Replicate units | Direct union | Directly in 1 | In 2 | In 3 | In 4 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| plate1_CD165 | 3 | 4208 | 2060 | 1153 | 995 | 0 |
| plate1_CM647 | 3 | 5261 | 2236 | 1418 | 1607 | 0 |
| plate1_JY | 3 | 1767 | 860 | 454 | 453 | 0 |
| plate1_PD42 | 3 | 2492 | 1253 | 634 | 605 | 0 |
| plate1_RA957 | 3 | 7861 | 2049 | 1583 | 4229 | 0 |
| plate1_TIL1 | 3 | 5500 | 1843 | 1338 | 2319 | 0 |
| plate1_TIL3 | 3 | 6536 | 2256 | 1693 | 2587 | 0 |
| plate2_3830-NJF | 3 | 1872 | 1042 | 460 | 370 | 0 |
| plate2_3849-BR | 2 | 8894 | 3836 | 5058 | 0 | 0 |
| plate2_3865-DM | 1 | 3635 | 3635 | 0 | 0 | 0 |
| plate2_3912-BAM | 1 | 3314 | 3314 | 0 | 0 | 0 |
| plate3_CD165_1e7 | 3 | 1267 | 555 | 378 | 334 | 0 |
| plate3_CD165_3e7 | 3 | 2161 | 879 | 590 | 692 | 0 |
| plate3_CD165_5e7 | 3 | 2313 | 1090 | 601 | 622 | 0 |
| plate3_CD165_7e7 | 3 | 2592 | 1192 | 695 | 705 | 0 |
| plate4_UWB1289_ctrl | 4 | 2351 | 811 | 505 | 412 | 623 |
| plate4_UWB1289_IFNg | 4 | 2551 | 955 | 536 | 468 | 592 |
| interplate_JY | 3 | 1114 | 637 | 273 | 204 | 0 |

For the **16 comparable base groups**, totals are **58,740 peptide–group rows**:
**23,554 in one**, **17,369 in two**, **16,602 in three**, and **1,215 in four**
replicate units. These are descriptive counts across different denominators and
replication types, not a pooled-binomial analysis. The two singletons add 6,949
rows to reach **65,689 rows** across all 18 base groups.

| Overlapping instrument diagnostic | Reported union | Direct union | Directly in 1 of 2 | In 2 of 2 | Transfer-only within this preparation |
| --- | ---: | ---: | ---: | ---: | ---: |
| plate1_RA957_instrument_1 | 7575 | 5871 | 2303 | 3568 | 1704 |
| plate1_RA957_instrument_2 | 7556 | 6298 | 2363 | 3935 | 1258 |
| plate1_RA957_instrument_3 | 7275 | 5733 | 2167 | 3566 | 1542 |

All reported-union rows, including zero-direct/transfer-only instrument rows,
remain in matrices with `direct_union_member` explicitly false where appropriate.
The alternate CD165 1e8 processing matrix has **4,462** direct-union peptides:
2,124 detected once, 1,180 twice and 1,158 three times. It is not included in
base-group totals and does not increase the number of distinct runs.

### Effect of identification transfer — descriptive only

| Base group | Direct union | Transfer-inclusive in 1 | In 2 | In 3 | In 4 |
| --- | ---: | ---: | ---: | ---: | ---: |
| plate1_CD165 | 4208 | 265 | 508 | 3435 | 0 |
| plate1_CM647 | 5261 | 326 | 487 | 4448 | 0 |
| plate1_JY | 1767 | 88 | 114 | 1565 | 0 |
| plate1_PD42 | 2492 | 267 | 383 | 1842 | 0 |
| plate1_RA957 | 7861 | 332 | 513 | 7016 | 0 |
| plate1_TIL1 | 5500 | 198 | 420 | 4882 | 0 |
| plate1_TIL3 | 6536 | 326 | 610 | 5600 | 0 |
| plate2_3830-NJF | 1872 | 150 | 173 | 1549 | 0 |
| plate2_3849-BR | 8894 | 1186 | 7708 | 0 | 0 |
| plate2_3865-DM | 3635 | 3635 | 0 | 0 | 0 |
| plate2_3912-BAM | 3314 | 3314 | 0 | 0 | 0 |
| plate3_CD165_1e7 | 1267 | 41 | 113 | 1113 | 0 |
| plate3_CD165_3e7 | 2161 | 138 | 181 | 1842 | 0 |
| plate3_CD165_5e7 | 2313 | 117 | 196 | 2000 | 0 |
| plate3_CD165_7e7 | 2592 | 98 | 157 | 2337 | 0 |
| plate4_UWB1289_ctrl | 2351 | 131 | 65 | 122 | 2033 |
| plate4_UWB1289_IFNg | 2551 | 142 | 88 | 153 | 2168 |
| interplate_JY | 1114 | 115 | 89 | 910 | 0 |

For example, RA957 is direct-positive in all three preparations for 4,229
peptides but transfer-inclusive positive in all three for 7,016. This is an
identification-transfer distinction, not a stability result. Direct and matching
states are never pooled into the same primary identification endpoint.

## HLA attribution and Teacher feasibility

All genotypes below come from original Supplemental Table S1. Both copies of
homozygous alleles are retained in configuration; the table displays the unique
candidate set. Genotyping establishes candidate alleles, not peptide-specific
restriction or measured allele-expression levels.

| Sample | Documented HLA-I candidate set |
| --- | --- |
| CD165 | A*02:05, A*24:02, B*15:01, B*50:01, C*03:03, C*06:02 |
| CM647 | A*01:01, A*24:02, B*13:02, B*39:06, C*06:02, C*12:03 |
| PD42 | A*02:06, A*24:02, B*07:02, B*55:01, C*01:02, C*07:02 |
| RA957 | A*02:20, A*68:01, B*35:03, B*39:01, C*04:01, C*07:02 |
| TIL1 | A*02:01, B*18:01, B*38:01, C*05:01 |
| TIL3 | A*01:01, A*23:01, B*07:02, B*15:01, C*12:03, C*14:02 |
| 3830-NJF | A*02:01, A*03:01, B*07:02, C*07:02 |
| 3849-BR | A*01:01, A*31:01, B*38:01, B*44:02, C*05:01, C*12:03 |
| 3912-BAM | A*01:01, A*29:06, B*08:01, B*15:01, C*03:04, C*07:01 |
| 3865-DM | A*01:01, A*03:01, B*35:01, B*57:01, C*04:01, C*06:02 |
| UWB1.289 | A*03:01, A*68:01, B*07:02, C*03:32, C*07:02 |
| JY | A*02:01, B*07:02, C*07:02 |

Table S1's RA957 `B*39.01` punctuation is explicitly normalized to `B*39:01`
without changing digits. The paper/S2 also spell CM647 as CM467; source RAW names
and Table S1 use CM647. No highest-affinity HLA, Teacher-assigned HLA or motif
inference was substituted. Published IFNγ-study binding assignments are predicted
and were not promoted to experimentally measured restriction.

There are **36 distinct candidate alleles**. An authenticated existing Task 2.13
support metadata receipt documents trained-Teacher use for **16 of these**.
**Nine A/B alleles remain undetermined** from that partial receipt, which covers
49 previously used supported alleles rather than all 67 trained models. Absence
from this receipt is not evidence that the original Teacher lacks a model.
**Eleven HLA-C alleles are outside the Teacher's human HLA-A/B scope.**

The frozen model's expected location is resolved project runs /
`task-2_3-first-stability-teacher/checkpoints/teacher_model.json`, expected SHA256
`a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99`.
It is **absent locally**. Its original fitting partition and canonical kinetic
registry are also absent, so exact Teacher-fitting sequence exposure cannot be
reconstructed from original fitting identities here. No weights were downloaded,
refitted or inferred from historical score values. Only support/availability
metadata were read; no saved stability prediction values were opened.

Restoring these original bytes would allow the already supported A/B pairs to
be scored without retraining, but cannot resolve the source's ambiguous peptide
restriction. A 9-mer can be syntactically scoreable against several genotyped
alleles without having an experimentally established allele-specific endpoint.
**Primary eligible allele-specific observations remain zero.** Per-allele support
categories and exact missing dependencies are saved in
`HLA_and_Teacher_compatibility.json`.

## Source and training-reference overlap

The actual Task 2.23 fitting/selection sequence snapshots already authenticated
in Task 2.26 were reused with their frozen hashes, without repeating a broad
training audit or opening historical model predictions. Counts below use the
39,478 unique peptides in chosen base groups. Exposure categories are separate.

| Reference | Exact unique sequences | Base peptide–group rows | Comparable peptide–group rows |
| --- | ---: | ---: | ---: |
| EL_fit | 17337 | 33873 | 30235 |
| EL_selection | 1945 | 3839 | 3459 |
| IM_fit | 11 | 21 | 21 |
| IM_historical_development | 0 | 0 | 0 |
| prior_Mendeley_published | 0 | 0 | 0 |

EL fitting overlap is **17,337 unique peptides**, EL selection **1,945**, IM
fitting **11**, historical IM development **0**, and the prior published Mendeley
sequence reference **0**. Overlapping categories must not be added as exclusions.
No current detection observation was removed using these counts. Prior external
benchmark identity exposure is not fitting exposure; no IM labels, predictions
or performance were evaluated. Experimental peptide–HLA pair overlap cannot be
claimed from candidate HLA sets. Upstream publication/sample independence from
BigMHC cannot be fully established from its prepared sequence references.

The separate **18 exact RAW-name overlaps with PXD013831** are source-reuse
warnings. Pooled source aggregation is not a new experimental replicate. Exact
peptide overlap with the entire phosphopeptide aggregation was not computed;
its large identification archives were not acquired. Unresolved comparisons
are reported as unresolved, never as zero.

## Chemical identity, selection and confounders

- Source `peptides.txt` aggregates chemical modification states into a base
  sequence. Oxidized methionine and other search-specific forms cannot be
  reconstructed per run from these fields alone. Original modification/evidence
  IDs are retained. An unmodified-sequence Teacher interpretation would require
  adequate per-run chemical-state evidence before a primary association.
- Supplemental Table S3 lists 15 isotopically heavy synthetic standards and
  their endogenous light counterparts in CD165 samples. Standard sequences and
  overlapping canonical 9-mers are explicitly annotated in
  `synthetic_standard_annotations.json`. Their base sequences alone cannot
  distinguish heavy standards from endogenous observations. They are not
  synthetic negatives or experimentally measured kinetic stability. No heavy
  standard is silently certified as an endogenous primary observation.
- Peptide abundance, source-protein expression/turnover, HLA expression,
  antigen processing and proteasome composition influence detection. IFNγ changes
  several of these jointly. RNA/protein covariates are not uniformly available;
  the acquired export contains an IFNγ protein-LFQ table, but no expression
  adjustment or causal analysis was attempted.
- DDA precursor competition, ionization/hydrophobicity, charge, chromatography,
  fragmentation, run depth, batch, extraction yield and source filtering can
  affect repeated identification. A best PEP pooled across runs is not an
  independent index-run covariate. Nominal FDR, per-allele Teacher uncertainty
  and unsupported alleles remain distinct limitations.
- Tissue sections can differ biologically and in input mass; preparation
  aliquots share lysate; instrument reinjections share eluate. The 58,740 rows
  and repeated group appearances are not independent biological measurements.
- **Absence from an MS run does not establish absence from the cell surface.**
  Identification in one of three runs does not show that an EL label is false.
  The observed union is conditioned on detection and is not an unbiased sample
  of all possible peptides or surface ligands.

## Task 2.29 readiness and fixed next protocol

The [separate Task 2.29 protocol](REPLICATE_STABILITY_ASSOCIATION_TASK2_29_PROTOCOL.md)
was committed before any stability scoring. It fixes established HLA restriction,
unmodified chemical correspondence, original frozen Teacher identity and
comparable replicate metadata as prerequisites. Current primary N=0 is explicit.
A future authorized Task 2.29 must report that blocker if the prerequisites have
not changed; this task does not authorize new restriction inference or retraining.

Conditional on separately authorized and authenticated eligible data, the plan
uses a deterministically fixed index unit and reserved-repeat direct-detection
frequency, continuous within-HLA Teacher stability, an equally weighted
HLA/context rank-association summary, whole sample/peptide-component uncertainty,
within-HLA identity-consistent permutation controls and an index-abundance
sensitivity. Technical/preparation/biological endpoints remain separate.
Unreliable or undefined estimates are reported without choosing a more favorable
source, threshold or subset. No component resampling, permutation, correlation,
regression, stability prediction or association endpoint was executed here.

**A defensible detection-reproducibility dataset has been built. A defensible
allele-specific kinetic-stability association cannot yet be run from these
curated observations.** The exact missing biological information is independent
peptide–HLA restriction and chemical-state correspondence; the technical missing
input is the original frozen Teacher and its support/fitting metadata.

## Tests, execution evidence and persisted outputs

**Nine focused unittest cases pass, zero failures/errors/skips**: direct versus
matching states, retained nondetection opportunities, transfer-only union rows,
nested instrument/preparation denominators, class-II exclusion, source flags,
no PEP-as-q cutoff, duplicate-source handling, unknown-state failure and RAW
acquisition rejection. Tests use synthetic data and never open a model or source
experiment. A focused completion check independently validates all **88,095
peptide–group rows in the 21 original matrices**, their complete source order,
state/denominator associations and unchanged original hashes. The alternative
processing matrix is retained separately. No historical reproducibility audit
was performed.

Curation runtime was **8.079115344036836 seconds**, peak
host RSS **653254656 bytes**, Python 3.13.5 on
Linux Microsoft WSL2. This excludes source acquisition, metadata extraction,
verification and report preparation. Preserved HTTP bodies total
**48278072 bytes**, including
**22299141 range bytes**; this is not a
measurement of all exploratory network traffic. No GPU or model was used.


Key files under the resolved Task 2.28 run directory:

- `observations/*_9mers.jsonl.gz`: source-preserving HLA-I rows and all run states.
- `matrices/*.jsonl.gz`: one row per original source peptide/group, explicit
  replicate-unit binary detections, original states, source identity, known
  denominator, direct and transfer-inclusive counts/fractions.
- `alternative_views/CD165_1e8_reprocessed_view.jsonl.gz`: all calls from the
  reused CD165 search view, excluded from distinct-run/base-group totals.
- `reports/replicate_groups.json`, `run_inventory.json`,
  `run_views_and_reuse.json`, `repository_run_name_alignment.json`: complete
  condition, hierarchy, original RAW associations and explicit alias/reuse maps.
- `reports/detection_distributions.json`, `source_parser_counts.json`,
  `overall_detection_summary.json`: exact counts, exclusions and transfer states.
- `reports/source_feasibility_catalog.json`, `source_acquisition_manifest.json`,
  `processed_export_authentication.json`, selected ZIP inventory, original
  parameter snapshots and extracted Tables S1/S2/S3: scientific provenance.
- `reports/technical_feasibility.json`, `reference_overlap_summary.json`,
  `peptide_sequence_exposure.jsonl.gz`, `HLA_and_Teacher_compatibility.json`,
  `synthetic_standard_annotations.json`: exposure, attribution and feasibility.
- `reports/focused_tests.json`, `focused_tests.log`, `curation_started.json`,
  `curation_complete.json`, `completion_verification.json`, `resource_summary.json`,
  `curation_freeze.json` and `finalization_manifest.json`: execution and freeze.
- `reports/scientific_interpretation.md`: exact copy of this report.

Code/configuration and documentation are committed; source and generated data
remain outside Git. The worktree is clean at final sealing. No merge or push,
model training, GPU learning, Teacher scoring, kinetic association, A/S/P
reevaluation, RAW download, spectra reprocessing, synthetic-label generation or
backup archive creation occurred. Stop after this feasibility and curation task.
