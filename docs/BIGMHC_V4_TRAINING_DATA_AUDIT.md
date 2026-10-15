# BigMHC Version 4: training/validation acquisition and audit

Task 2.2 authenticates the release and inspects only authorized training,
validation and receptor-reference content. It creates aggregate reports, not
training datasets, correction masks, splits or model results.

## Current scientific direction

The final Task 2.2 instruction supersedes conflicting earlier scope. The future
comparison has four conditions: A original EL → original IM; B corrected EL →
original IM; C original EL → corrected IM; D corrected EL → corrected IM.
Corrections would be separately versioned **training pseudolabels**. Original MS
and experimental IM labels must always remain available as source evidence.
All four conditions eventually use the same independent experimental T-cell
evaluation outcomes, which remain unchanged. This audit implements none of the
experiments or corrections. Numeric thresholds and experiment details await review.

[The Task 2.0 protocol](PHASE2_EL_TO_IM_RESEARCH_PROTOCOL.md) and Task 2.1 code
audit remain dated evidence. The new scope is recorded in
[bigmhc_v4_audit.json](../configs/bigmhc_v4_audit.json), which supplements the
existing source registry rather than replacing it. Detailed sampler equalization,
optimizer-step matching, multiple seeds, causal decomposition, extensive controls
and full hard-split construction are explicitly deferred, not prerequisites here.

## Authentic release and evaluation isolation

Authority: [Mendeley Data Version 4](https://data.mendeley.com/datasets/dvmz6pkzvb/4),
DOI `10.17632/dvmz6pkzvb.4`, published 14 April 2023. Data listing terms are
CC BY 4.0, separate from the BigMHC Academic software license. No raw data are
redistributed in this repository.

Actual immutable artifacts acquired on 15 October 2026:

| Artifact | Bytes | Locally verified SHA256, also matching publisher reference |
| --- | ---: | --- |
| datasets.zip | 144,274,974 | `0d152a452756cf2e0014ffced6afc25118e7c11cf1f626b26e49f50f79edffaa` |
| pseudoseqs.csv | 15,921,144 | `cd1fa24fb4c9fc0ee592a3d753458c4e3abed0d5cc4ca76e325aa274df8e900a` |

Both live under the resolver's project data directory, in `bigmhc_v4/`.
`acquisition_receipt.json`, `reference_acquisition_receipt.json` and
`publisher_file_metadata.json` preserve HTTP evidence and the official file list.
Local hashes identify bytes; publisher-reference agreement establishes released
artifact identity, not scientific validity or cohort independence.

Verified original and resolved URLs:

- Archive: `https://data.mendeley.com/public-files/datasets/dvmz6pkzvb/files/1da0314f-692d-4c39-b81f-fa2a7dba86bf/file_downloaded?version=4`
- Archive resolved: `https://prod-dcd-datasets-public-files-eu-west-1.s3.eu-west-1.amazonaws.com/b7ef294a-1a96-45af-8a16-ab060251e131`
- Reference: `https://data.mendeley.com/public-files/datasets/dvmz6pkzvb/files/6e3754c4-53dd-4e6c-8a8d-10e0ef2e61a2/file_downloaded?version=4`
- Reference resolved: `https://prod-dcd-datasets-public-files-eu-west-1.s3.eu-west-1.amazonaws.com/4257cd1f-d936-4e81-9227-8584d7f8b24c`

The authenticated archive contains **eight members**, despite the landing-page
description listing ten. `pseudoseqs.csv` and `manafest.csv` are absent. The
expressly authorized pseudosequence reference was therefore acquired from its
separate official Version 4 entry. MANAFEST was not acquired.

The archive remains whole. Only `el_train.csv`, `el_val.csv`, `im_train.csv` and
`im_val.csv` are decompressed and parsed. `el_test.csv`, `im_test.csv` and
`iedb.csv` remain unopened inside it. Missing `manafest.csv` is marked absent and
not acquired. Sealing here means enforced reader scope, not encryption or removal
from the downloaded container. `summary.csv` is also unopened because it is not
needed and includes evaluation composition. No whole-archive CRC walk,
`testzip`, extraction or prediction-column inspection occurs. Authorized member
CRC validation happens during full streaming reads. ZIP directory names and
sizes are metadata, not inspection of evaluation payloads.

Acquisition enforces an exact artifact/redirect allowlist, verified TLS, bounded
streaming, finite timeouts, 256 MiB archive / 32 MiB reference caps, publisher
size/checksum checks, no-follow paths and nonreplacing atomic placement. Failed
partials are removed; existing different artifacts are preserved. No weights,
additional scientific payloads or external repositories are acquired.

## Direct training/validation observations

| File | Rows | Positive | Negative | Original HLA identifiers | Ordinary DTU alleles represented |
| --- | ---: | ---: | ---: | ---: | ---: |
| el_train.csv | 15,324,585 | 259,298 | 15,065,287 | 149 | 56 |
| el_val.csv | 1,702,732 | 28,734 | 1,673,998 | 149 | 56 |
| im_train.csv | 6,185 | 1,407 | 4,778 | 70 | 39 |
| im_val.csv | 688 | 173 | 515 | 55 | 34 |

EL has exactly `mhc,pep,tgt`; IM has `mhc,pep,tgt,rand`. All observed `tgt`
strings are literal `0` or `1`. Every IM `rand` flag is literal `0`.
No malformed rows, nonfinite labels, within-file duplicate pair keys, exact
full-field duplicate records, or within-file conflicting binary labels were
found. EL training contains three rows with noncanonical peptide characters;
EL validation contains one. The aggregate report retains character counts and
source-line references without altering those rows. IM has no such flags.

Peptide-length counts:

| Length | EL train | EL validation | IM train | IM validation |
| --- | ---: | ---: | ---: | ---: |
| 8 | 3,444,938 | 382,845 | 0 | 0 |
| 9 | 3,675,111 | 407,872 | 3,850 | 444 |
| 10 | 3,504,080 | 389,522 | 2,335 | 244 |
| 11 | 3,465,166 | 385,036 | 0 | 0 |
| 12 | 433,762 | 48,129 | 0 | 0 |
| 13 | 421,051 | 46,828 | 0 | 0 |
| 14 | 380,477 | 42,500 | 0 | 0 |

The reference has 18,929 unique raw identifiers, 414 binary features across 30
aligned positions, no duplicate identifier or sanitized-UID collision, and no
invalid per-position one-hot row. All 72 ordinary DTU identifiers and all 153
identifiers appearing across the four allowed files have unique supported
reference matches. This checks encoding availability, not Teacher generalization.
No fuzzy HLA matching, field truncation or C67S-to-wild-type mapping is used.

## DTU compatibility and basic overlap

The immutable DTU checksum is verified before parsing and after analysis:
`5f2c6e82d198705a66974b4e42a0ed1412124c4b1e8f7033c7cd43bbdac07f67`.
The comparison uses its 27,031 ordinary HLA-A/B nine-mer rows, 72 identifiers and
4,711 reported zeros. Its 1,135 C67S rows remain untouched and separately counted.

| Allowed file | Canonical nine-mer rows with ordinary DTU allele and unique receptor reference | Exact DTU pair keys | Shared distinct DTU peptides, any HLA | DTU zero-valued keys among pair matches |
| --- | ---: | ---: | ---: | ---: |
| el_train.csv | 1,631,849 | 309 | 344 | 29 |
| el_val.csv | 181,149 | 26 | 66 | 4 |
| im_train.csv | 3,508 | 121 | 144 | 0 |
| im_val.csv | 405 | 19 | 19 | 0 |

These are descriptive input-scope counts, not an inclusion mask or approved
Teacher coverage. EL training has 1,631,850 ordinary-allele nine-mer rows before
the canonical-character check. A nine-mer-only Teacher does not automatically
support longer/shorter peptides, HLA-C, or ordinary alleles absent from its source.
Binary EL/IM outcomes are not numerically comparable to kinetic half-life hours.
DTU zero semantics remain unresolved.

Exact raw HLA keys and evidence-supported optional-asterisk notation matches
give the same actual pair-overlap counts. Within EL and within IM,
train/validation pair overlap is zero, but shared peptide counts are respectively
703,412 and 38. Thus pair-disjoint release partitions are not peptide-disjoint.
EL versus IM has 122 shared distinct peptides across the allowed files:

| File pair | Shared peptide–HLA keys | Shared distinct peptides |
| --- | ---: | ---: |
| EL train / IM train | 77 | 109 |
| EL train / IM validation | 4 | 10 |
| EL validation / IM train | 3 | 13 |
| EL validation / IM validation | 1 | 2 |

Cross-task label disagreement does not establish an erroneous label: presentation
and T-cell response are different outcomes. Counts are exact-string observations;
no near-sequence search, hard-split assignment or independent-test overlap
assessment is performed here.

## Source semantics and missing evidence

[BigMHC Methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC10569228/), Datasets /
Epitope presentation training, attributes EL input to NetMHCpan-4.1 and
MHCflurry-2.0 single-allelic collections; Figure 1 distinguishes MS positives
from decoys. Datasets / Immunogenicity training describes nonrandom PRIME-1.0/2.0
examples. Its reported train/validation counts match all four local files, and
the local IM flags are consistent with the described nonrandom selection.
Neither this agreement nor the flags independently trace each assay or negative.

The files lack row-level study, donor, antigen, assay endpoint, multi-allelic
assignment history and individual decoy-generation metadata. They cannot certify
experimental non-presentation for EL negatives or independently establish the
functional response evidence for every IM negative. Checkpoint exposure remains
subject to [Task 2.1's limitations](BIGMHC_SOURCE_AND_CHECKPOINT_PROVENANCE.md).

The practical next step is a narrowly scoped, reviewed Teacher implementation
and validation plan for ordinary HLA-A/B nine-mers, carrying forward the detected
DTU/EL/IM exposure. Before any correction, specify behavior outside that scope
and preserve original labels separately from pseudolabels. Independent evaluation
data remain sealed/unselected. This task does not make detailed sampler controls
or full hard-split construction a prerequisite.

## Offline reproduction and run evidence

```sh
PYTHONPATH=src python3 -B -m stability_label_curation bigmhc data-audit --json
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
```

Inspection is offline and read-only. Explicit `--archive`, `--dtu`, `--pseudoseqs`
and corresponding expected SHA256 options support synthetic fixtures. The default
uses the established path resolver and source registry. Streaming CSV parsing
feeds a bounded in-memory SQLite key index (3 GiB page cap); no row tables or
temporary scientific files are written. Analysis may take several minutes.

For a canonical run, use existing `runs create --kind data_audit --config
configs/bigmhc_v4_audit.json` with repeatable `--input` for the archive, standalone
reference, DTU file and any local receipts/metadata read. Then pass that run's
`reports` directory to `bigmhc data-audit --reports-dir`. Run evidence must record
every input; ZIP member SHA256 values describe authorized decompressed streams,
not fabricated separately stored CSV input files.

Reports contain archive identities/open-member ledger, per-file label/length/HLA
counts, receptor/DTU compatibility, exact overlaps, provenance gaps and deferred
scope. `execution_verification.json` hashes each report. Recompute offline and
compare report hashes; validate the existing run manifest and rehash all inputs.
The source acquisition commands (`bigmhc fetch-data` and `bigmhc fetch-data
--artifact pseudoseqs.csv`) only fetch the two allowlisted artifacts. Existing
matching files are reused without replacement; the original acquisition receipts
must be retained separately from subsequent reuse reports.
