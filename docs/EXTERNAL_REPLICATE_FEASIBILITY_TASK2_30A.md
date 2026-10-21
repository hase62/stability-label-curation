# Task 2.30A — External biological replicate feasibility and freeze

Completed on Z790 WSL2, 2026-10-21. Branch
`task/2.30a-external-biological-replicate-curation`, based directly on approved
Task 2.29C commit `e4b224b36fa91a7d720018afd65467c4035035a6`.

**GO for a separately authorized external-context replication.** Authentic
run-resolved direct identifications were recovered for the edited JY W6/32
condition. The frozen candidate union has **1,472 unmodified canonical 9-mers**;
the metadata-defined index-clone cohort has **496**, with **130 not detected**
and **366 detected** in the other biological clone. Quantitative index MS1
feature intensity is available for **473/496**; 23 missing values remain.
The original A*02:01 Teacher and fitting/validation identities are available.
**No Teacher prediction or stability association was computed.**

This is an external replication planned after the exploratory SHERPA finding
was known. It provides a new JY/CRISPR biological context, not independent
confirmation already obtained, a sequence hard split, or multiple independent
HLA/study contexts. Two clones constitute one biological comparison group;
population-level biological confidence intervals remain unavailable.

## Exact source and acquisition

Cobos-Figueroa et al., *Innovative CRISPR/Cas9-Based Strategy for Allele-Specific
HLA Peptidome Analysis Using a Pan-HLA Antibody*, MCP (2026),
[DOI 10.1016/j.mcpro.2026.101578](https://doi.org/10.1016/j.mcpro.2026.101578),
[full text](https://pmc.ncbi.nlm.nih.gov/articles/PMC13240811/),
[MassIVE MSV000099922](https://massive.ucsd.edu/ProteoSAFe/dataset.jsp?accession=MSV000099922).
MassIVE submission task: `5ecbfb9a95414784a76668886df90ba7`.

At acquisition the MassIVE web page still described the deposit as private.
The article itself publishes dataset access credentials. These were used through
authenticated **explicit FTP AUTH TLS on port 21**, with certificate validation;
no credential guessing or author contact was needed. Passwords are not placed
in Git or acquisition receipts. Original URLs, source directory listings,
repository sizes/modification times, retrieval times, member identities and
local checksums are preserved. Search files have original November 2025
timestamps; the author-supplied mapping was added in the March 31, 2026 update.

The paper XML and Europe PMC supplementary archive were acquired from
`https://www.ebi.ac.uk/europepmc/webservices/rest/PMC13240811/`, using
`fullTextXML` and `supplementaryFiles`. Supplemental `mmc1.xlsx` contains the
`Peptides` worksheet and is byte-identical to deposited `search/Peptides.xlsx`:
**2,137,265 bytes**, SHA256
`a04ebe0754b47128a285a5290cad4e48332b1ae733496b1f4798c660d988e9fd`.

The independent raw-to-experiment mapping is
`updates/2026-03-31_Lauracobosf_85ac7533/other/Mappingfile.xlsx`, **13,720 bytes**,
SHA256 `f1054c99d0dfb1b6db15b305ed055e8e2798c3c2c2a91026f8289814840d864f`.
The original and update `ccms_parameters/params.xml` files were retained.
The 16 deposited RAW filenames were listed for identity checks only.

`search/Search_Engine.zip` is **16,026,123,506 bytes**. It was **not downloaded
in full**. Its ZIP64 central-directory index (23,306 members) was read using
bounded FTP REST ranges. Only these eight processed members were extracted:

| Original member prefix | Selected files |
| --- | --- |
| `Experiment 1/combined/txt/` | `evidence.txt`, `peptides.txt`, `summary.txt`, `parameters.txt` |
| `Experiment 2/combined/84884-901_txt re-run/` | `evidence.txt`, `peptides.txt`, `summary.txt`, `parameters.txt` |

Every selected member passed its original ZIP CRC32 check and received a local
SHA256 receipt. Range offsets, byte counts and SHA256 values are saved. The
whole 16-GB archive's SHA256 was not computed or claimed. Approximately 13.9 MB
of archive range payload was transferred across indexing/probing/member reads;
no RAW, mzML, spectra reprocessing or whole search archive acquisition occurred.

| Selected source | Bytes | SHA256 |
| --- | ---: | --- |
| Exp1 `evidence.txt` | 8,718,699 | `69f100f883b7a3e2b0df13a930919d42ba12abdd28571f573bca2058e88be290` |
| Exp2 `evidence.txt` | 10,244,110 | `1637436a7b6adb53e03946123cb723edd6e98dff98dca4df80fb4329e2e6f911` |
| Exp1 `peptides.txt` | 2,734,543 | `479be3ad5d9232f97949fd48bca70819fe37911001e15f57c40d48edf6b95d2c` |
| Exp2 `peptides.txt` | 3,039,808 | `9d44cb8e0ec58d482e6bab5b27888261cf0efec9369e1026efd8fabcdbdefef9` |

The selected source passes the run-resolved feasibility gate. The conditional
PXD034429 fallback was therefore not searched or downloaded.

## Experimental restriction, mapping and comparability

The source uses JY B-lymphoblastoid cells edited to disrupt classical
HLA-B*07:02 and HLA-C*07:02 while retaining endogenous HLA-A*02:01, with W6/32
capture. Genotype/flow characterization supports the experimental condition.
This does not individually prove restriction of every recovered ligand or
exclude residual/nonclassical HLA and nonspecific co-isolation. The spreadsheet's
computational `Affinity_HLA` assignment is **not an eligibility or HLA-assignment
rule**. No binding or Teacher prediction assigns an allele here.

Only the following four exact original runs enter the comparable condition:

| Biological clone | Role | Technical label | RAW basename | Legacy evidence experiment label |
| --- | --- | --- | --- | --- |
| ΔBC1 | Index | Exp1 | `Seq84886_HF` | `C.13 w6/32` |
| ΔBC1 | Index | Exp2 | `Seq84886_3-4_HF` | `C.13 w6/32 3-4` |
| ΔBC2 | Follow-up | Exp1 | `Seq84887_HF` | `C.15 w6/32` |
| ΔBC2 | Follow-up | Exp2 | `Seq84887_3-4_HF` | `C.15 w6/32 3-4` |

The deposited author mapping and both processed summary files agree on these
run/clone/condition identities. Legacy `C.13/C.15` labels remain preserved;
their interpretation comes from the explicit mapping, not filename inference.
The source describes two biological clones and two technical measurements per
clone, with 3e9 cells per biological unit and 1.5e9 per technical measurement.
The exact split stage/preparation-versus-repeat-injection history is not
independently recovered; technical labels are retained as nested measurements,
not promoted to independent biological preparations. All four use the reported
Q-Exactive-Plus/HCD LC-MS method. WT, PA2.1 and all other runs remain excluded.

The original joint searches contain 18 and 21 raw identities, including other
unmapped experiments. They are not new eligible conditions. Of 39,330 original
evidence rows (18,374 Exp1; 20,956 Exp2), **6,320** belong to the four selected
runs; **33,010** are outside the frozen condition.

## Direct identification, confidence and chemical state

The processed data preserve exact sequence, modified sequence, feature ID,
raw file, original experiment, MS/MS IDs and scan numbers, PEP, Andromeda score,
reverse/contaminant flags, charge, RT, proteins, and MS1 feature intensity.
All selected evidence has direct MS/MS count and identifiers, with source types
`MULTI-MSMS` (5,859), `MSMS` (200) or `MULTI-SECPEP` (261).
[Official MaxQuant output documentation](https://cox-labs.github.io/coxdocs/output_tables.html)
identifies these as direct spectrum-supported features, including second-peptide
identifications; `MULTI-MATCH` denotes between-run transfer. Both original
parameter files explicitly have **`Match between runs = False`**. No transfer-only
calls are made direct successes, and no intensity-only presence is invented.

Source confidence settings are preserved, not tuned:

- MaxQuant **2.4.9.0**, source `PSM FDR = 0.05`, `Site FDR = 0.01`.
- Processed `Protein FDR = 1` differs from the article's stated protein FDR
  0.01. This unresolved discrepancy is recorded literally; the parser does not
  reinterpret it as 1%, reestimate FDR or change peptide acceptance.
- Actual variable modifications include methionine oxidation **and protein
  N-terminal acetylation**, whereas the article only names oxidation. Mapping
  fixed-modification cells are empty and processed summaries report `NA`.
- PEP is preserved as the source posterior error probability, not treated as
  a newly estimated cohort FDR or an automatically applicable .05 cutoff.

Source acceptance requires original direct evidence, no reverse/contaminant
flag, and membership in the matching published run-specific accepted peptide
set. Original 8–15-mer source sets reconcile **exactly**, with zero missing or
extra peptides: 590, 637, 2,057 and 1,552 across the four ordered runs.

The primary candidate requires canonical uppercase length-nine sequence,
`Modifications == Unmodified`, and exact `_SEQUENCE_` modified-sequence form.
No variable modification is silently stripped into an unmodified detection.
Cysteine is not automatically discarded as in the fixed-CAM SHERPA search;
chemical eligibility follows this source's documented no-fixed-modification
setting. All original feature rows and modified molecular species remain saved.

Within the selected 6,320 evidence rows, mutually exclusive statuses are:

| Status | Feature rows |
| --- | ---: |
| Retained unmodified canonical 9-mer | 2,731 |
| Accepted modified 9-mer | 667 |
| Accepted noncanonical or other length | 2,347 |
| Reverse/contaminant or outside published accepted set | 575 |

One peptide–run presence can have multiple charge/features/PSMs. These original
records are preserved, with one binary presence per peptide/run and no invented
replicate. Source evidence IDs are unique within each search and namespaced by
search; intensity is counted once per unique evidence-feature row. All 6,320
evidence-to-original-peptide-table cross-references passed validation.

## Frozen cohort and detection distributions

The unrestricted processed direct union, excluding reverse/contaminant flags
but preserving all original lengths, has **2,927 base peptides** and **3,109
molecular species**. Its complete run-resolved matrix is retained as a
descriptive completeness view; longer sequences are not automatically declared
established A*02:01 ligands. The published 8–15-mer study-accepted union is
**2,821 base peptides** and **2,997 molecular species**, with modifications.
The planned unmodified canonical 9-mer union is **1,472 distinct peptide–HLA
pairs**, one allele. Per-run counts in the frozen order are **336 / 311 /
1,119 / 667**.

| Comparable unit | Union | Detected in one measurement | Detected in both |
| --- | ---: | ---: | ---: |
| ΔBC1, nested technical pair | 496 | 345 | 151 |
| ΔBC2, nested technical pair | 1,342 | 898 | 444 |
| Two biological clones | 1,472 | 1,106 | 366 |

Across all four nested technical measurements, the descriptive count 1/2/3/4
distribution is **834 / 409 / 135 / 94**. These are not four exchangeable
biological replicates.

The **496-peptide future primary cohort** is the union of direct unmodified
9-mers in both ΔBC1 technical measurements, selected by the original numbered
clone identity, not richness. ΔBC2 is the one biological follow-up. The binary
follow-up endpoint is **130 nondetections / 366 detections**; the preserved
nested technical counts 0/1/2 are **130 / 182 / 184**. No reverse index, alternate
antibody/genotype or pooled-condition analysis was selected.

An MS nondetection is not surface absence, an incorrect EL label or lack of
immunogenicity. The union is discovery-conditioned; the primary cohort is
index-clone conditioned. Clone-specific expression, editing/off-target effects,
batch and MS sensitivity can affect reproducibility.

## Intensity and available covariates

Unlike SHERPA's fragment-ion intensities, these tables contain quantitative
**MS1 isotope-feature/XIC intensities**, documented by MaxQuant. The frozen
per-run peptide quantity is the sum of positive finite intensities across
unique unmodified direct evidence features/charge states. It is an arbitrary
instrument-unit quantity, not calibrated cell-surface abundance or absolute
peptide concentration. Separate searches/run response and absence of established
cross-run intensity normalization remain limitations.

The fixed index covariate is the arithmetic mean of available positive per-run
peptide sums in **the two index-clone runs only**. Follow-up intensities are
preserved separately but never enter this baseline quantity. Zero, nonfinite
or missing values are unavailable, not zero biological abundance. There are
**473 available / 23 missing** index values. Availability across zero/one/two
index technical measurements is **23 / 327 / 146**. All 496 peptides remain in
the primary cohort. Future adjustment explicitly retains a missingness indicator.

Per-feature PEP/score, source proteins, RT, charge and original modification
information are available, but no post-result covariate selection is planned.
The pooled spreadsheet's best PEP across runs is not an index covariate. Matched
independent protein abundance has not been established. DDA selection, feature
quantification, confidence, sequence-dependent ionization/fragmentation and
conditioning on index discovery can confound an eventual association.

## Teacher compatibility and sequence exposure, without prediction

Recovered original Teacher SHA256:
`a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99`.
The unchanged original loader confirms exact HLA-A*02:01 support, 830 fitting
rows and 193 validation rows. The input encoder accepts every candidate 9-mer.
Authenticated fitting/validation CSVs, original partition and implementation
were verified. **Inference calls: zero.** No original SHERPA scores or association
outputs were opened or reanalyzed; only the known discovery documentation
motivates this separately planned external replication.

| Population | Exact fitting peptide–HLA / peptide-only | Exact validation peptide–HLA / peptide-only |
| --- | --- | --- |
| Unmodified union, N=1,472 | 12 / 13 | 3 / 3 |
| Future primary index, N=496 | 10 / 10 | 1 / 1 |

Exact minimum unweighted Hamming distances and witness sequences are saved for
both fitting and validation, relevant-allele and all-HLA references:

| Population/reference | 0 | 1 | 2 | ≥3 |
| --- | ---: | ---: | ---: | ---: |
| Index / A*02:01 fitting | 10 | 3 | 3 | 480 |
| Index / all-HLA fitting | 10 | 3 | 3 | 480 |
| Index / A*02:01 validation | 1 | 0 | 0 | 495 |
| Index / all-HLA validation | 1 | 0 | 0 | 495 |
| Union / A*02:01 fitting | 12 | 4 | 8 | 1,448 |
| Union / all-HLA fitting | 13 | 4 | 9 | 1,446 |
| Union / A*02:01 validation | 3 | 0 | 1 | 1,468 |
| Union / all-HLA validation | 3 | 0 | 1 | 1,468 |

Identity/normalization problems: **zero**. Primary eligibility never depends on
exposure. The frozen sensitivity excludes fitting distance 0/1 globally across
HLA, retaining **483 index peptides**; validation is reported separately, not
silently counted as fitting or added as another exclusion. Kinetic-training
labels are not MS-detection outcomes; overlap limits sequence generalization
but is not automatically leakage of this endpoint.

## Protocol readiness, validation and storage

The [locked Task 2.30B protocol](EXTERNAL_REPLICATE_ASSOCIATION_TASK2_30B_PROTOCOL.md)
defines the index clone, one binary biological follow-up, nested technical
diagnostics, missing-intensity handling, fixed fitting-exclusion sensitivity,
tie-aware statistics and dependence limitations **before any study scoring**.
Its two-clone endpoint is explicitly different from SHERPA's two reserved
biological follow-ups. It does not revise the historical SHERPA protocol.
Coefficient evaluability requires N≥2 and nonconstant score/outcome; N<30 or a
minority outcome <10 is flagged sparse without changing membership. Current
N=496 and outcome sizes 130/366 meet those count checks. Actual Teacher-score
variation and future regression rank remain untested until Task 2.30B.

**12 focused tests passed**, covering bounded RAW rejection, ZIP index-only
reads, selected-member/CRC verification, cached range/budget behavior, BOM
headers, direct versus transferred/second-peptide evidence, missing intensity,
index-only quantification, nested technical hierarchy, modified-only exclusion
and Hamming witnesses against brute force. Saved source validation passed
6,320 evidence/peptide-table links and 2,433 direct-detection cells across 1,472
candidate rows, including exact index membership. No broad audit was performed.

All paths use `stability_label_curation.paths`:

- Source data: resolved project data /
  `external_biological_replicates_task2_30a/`.
- Derived manifests/reports: resolved project runs /
  `task-2_30a-external-biological-replicate-curation/`.
- `observations/evidence.jsonl` retains every selected original feature and
  original fields; `matrices/` retains unrestricted and study-range molecular species and all four
  unmodified 9-mer run states, source links and separate intensity values.
- `manifests/run_identities.jsonl`, `design_freeze.json`,
  `future_primary_index_cohort.jsonl`, `Teacher_sequence_overlap.jsonl`,
  `future_sensitivity_source_identities.json` freeze the future analysis inputs.
- `reports/` preserves source reconciliation, curation/Teacher summaries,
  validation and final hash inventory; `logs/` contains focused tests.

Primary manifest SHA256:
`37d5247b7533243d4083142b9ec3dd4645eb8bcc344293908763cfb94bac5cd2`.
Run mapping SHA256:
`700c26f02842d7d6b49e28667f39082af8fe87927f88939401317d73f26f116b`.
Four-run matrix SHA256:
`be7ca2512342ffda5cbdf6362ad8c2ce008df7b08315dbdb49bc8fc212805e67`.
Sensitivity-ID manifest SHA256:
`a7e6dbc0e53432fdd655556114318f3293142c014e9b0c742c8772b50aa61edd`.

The design was frozen at `2026-10-21T06:34:40.534800+00:00`, before matrix
construction and all sequence-overlap analysis, with metadata-only index choice.
Curation used 0.99 seconds process wall time, peak RSS 212,316 KiB; overlap
checking used 2.21 seconds, peak RSS 44,428 KiB, Python 3.13.5 on x86_64 WSL2.
Network acquisition time is separate and range receipts preserve its evidence.
No GPU, new dependency, Teacher prediction, stability association, model training,
recalibration, SHERPA reanalysis, RAW download or backup archive was used.
Existing models, SHERPA data and previous results remain unchanged. Stop at this
freeze; Task 2.30B still requires separate authorization.
