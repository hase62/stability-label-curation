# Task 1.4: historical NetMHCstab provenance

The provenance search is complete within the examined sources. The original
5,509-row machine-readable measurement table was **not recovered**. Historical
row overlap with DTU 2016 is **not computed**, rather than zero. No original-format
parser, training table, inclusion decision, or source pooling was introduced.

The captured [evidence register](../configs/netmhcstab_2013_evidence.json) separates
confirmed publication facts, discovery limitations, and a pinned secondary
artifact. Evidence validation checks structure and arithmetic; it does not
independently reverify paper statements or certify individual measurements.
Access date: 2026-10-14 UTC. Primary DTU bytes remain immutable.

## Original publication and source discovery

[Jørgensen et al., DOI 10.1111/imm.12160](https://onlinelibrary.wiley.com/doi/10.1111/imm.12160)
was first online 8 August 2013 and appeared in the January 2014 Immunology issue.
Retain `netmhcstab_2013`. Methods/Data and Table 1 describe scintillation proximity
peptide–MHC-I dissociation measurements, hours, and 5,509 nine-mers across ten
human HLA-I alleles. Table 1, printed p.19, was checked in the article and
[institutional primary-paper copy](https://ri.conicet.gov.ar/bitstream/handle/11336/17953/CONICET_Digital_Nro.21885_A.pdf?sequence=2).
The published per-allele counts sum to 5,509; they are not recovered local counts.

| Original HLA string | Original Table 1 published count | Pinned TLStab secondary CSV observed count |
|---|---:|---:|
| HLA-A*01:01 | 259 | 195 |
| HLA-A*02:01 | 890 | 988 |
| HLA-A*03:01 | 812 | 881 |
| HLA-A*11:01 | 335 | 607 |
| HLA-A*24:02 | 571 | 601 |
| HLA-A*26:01 | 277 | 277 |
| HLA-B*07:02 | 530 | 658 |
| HLA-B*15:01 | 1,059 | 1,081 |
| HLA-B*35:01 | 470 | 692 |
| HLA-B*40:01 | 306 | 317 |
| Total | 5,509 | 6,297 |

The columns describe different source stages. Equal counts for one allele do not
establish matching rows, measurements, or materials.

The original article's Supporting Information lists Figure S1 (`imm12160-sup-0001-FigureS1.docx`,
predicted IEDB half-lives) and Figure S2 (`imm12160-sup-0002-FigureS2.pdf`, sequence
logos). These are not listed as a measurement-table release. File bodies were
not recovered: publisher supplement links failed in the web tool. The supporting
information listing is also present on printed p.26 of the institutional paper.

The [official NetMHCstab 1.0 service](https://services.healthtech.dtu.dk/services/NetMHCstab-1.0/)
is marked discontinued. Its abstract describes the study but provides no verified
raw-table link. The software directory points to an
[academic software request/license form](https://services.healthtech.dtu.dk/cgi-bin/sw_request?packageversion=1.0a&platform=Linux&software=netMHCstab&version=1.0).
That form specifies internal-use and redistribution restrictions. No request was
submitted and no NetMHCstab software package downloaded. Software availability
and licensing do not establish experimental-dataset availability or a dataset license.

Indexed official supplementary/archive and institutional/author source searches
did not identify an authenticated historical row table. Wayback CDX access was
blocked; archive recovery remains unresolved. This search does not establish
that no table exists. PMC requests returned HTTP 200 CAPTCHA pages, which were
rejected as article evidence. Wiley full text and primary-paper PDF web views
supported the statements captured in the register. A separate local download of
the institutional original PDF timed out; no recovered PDF is claimed for it.

## Artificial augmentation and target encoding

Methods/Data/Artificial neural network training describes 1,000 peptides per allele
selected for experimentally determined weak affinity (>20,000 nM), then assigned
artificial half-life zero. The measured 5,509 count precedes that enrichment.
Binding-affinity measurements do not establish stability measurements. Numerical
zero alone cannot identify those artificial targets; separate augmentation-file
distribution is unverified. Methods/Artificial neural network training encodes hours as `2^(-2/Th)`, except
HLA-B*40:01 uses `2^(-0.7/Th)`. No target transformation is applied by this audit.
These statements come from the [original methods](https://onlinelibrary.wiley.com/doi/10.1111/imm.12160).

## TLStab: a separately identified secondary release

The [TLStab primary paper](https://kavrakilab.org/publications/fasoulis2024-transfer.pdf),
DOI `10.1016/j.immuno.2023.100030`, reports 6,298 NetMHCstab-derived records across
ten alleles in §2.2.1; §3.1 describes acquisition through IEDB. This publication is
in the March 2024 issue and was available online in December 2023. It does not
explain the difference from 5,509 or specify an archived training export version.

The author-linked [TL-MHC repository](https://github.com/KavrakiLab/TL-MHC) was
pinned at `ec58087383f59f8afa9c1e8fbc8c5bb68e752ccb`, branch `master`, clean after
an explicit seven-file sparse acquisition. The external lockfile preserves the
SPEARMINT pin and records TL-MHC source-file identities. No external code was
executed or dependencies installed.

Inspection of the pinned
[preprocessing script](https://github.com/KavrakiLab/TL-MHC/blob/ec58087383f59f8afa9c1e8fbc8c5bb68e752ccb/TLStab/src/Dataset_processing.R)
provides these traceable details:

- Lines 11 and 18–30 read `mhc_ligand_full.csv`, select half-life/class-I data,
  require pseudosequence mapping, and assert minutes. That export is absent from
  the tracked tree; its date, original units, assay IDs, and reference lineage are unavailable.
- Lines 38–58 and 131–136 accept equality or blank inequality in the final call,
  remove missing numerical values, select training by an exact Authors string,
  and keep lengths 8–15. Training is not restricted by a study reference IRI.
- Lines 41–49 encode a dimensionless score `2^(-1/t_hours)` after a minutes-to-hours
  division in the final default call. The name `measurement_value` does not
  identify hours. Other calls have two test-study unit exceptions.
- Lines 60–72 average repeated **test** keys and remove test/training overlaps;
  this does not explain the training-count discrepancy. Lines 74–75 discard
  original units and study/assay metadata from the three-column release.

TLStab also points to online Supplementary Methods; a complete local methods
supplement was not recovered. The script is evidence of documented processing, not proof that it fully
reconstructs the released CSV. Predictions from inference scripts remain
predictions. README/output unit inconsistencies are not used to infer training
measurement units.

Only the selected training CSV was deliberately recovered:
`TLStab/misc/datasets/training_data/cleaned_data/cleaned_train_data.csv`.
Its snapshot is `data/stability-label-curation/tlstab_2024_secondary/cleaned_train_data.csv`
under resolved project storage: 237,419 bytes, SHA256
`2d2c2a8ed0319ade9ec8657cbc4246d38924d0b21b33717b2ef7887e7f238fa7`.
The Git blob identity `3cbfd2708cd1f207c4b1cd08faac60c6ec720ce2` independently ties
these bytes to the pinned tree. Neither is a publisher-provided SHA256.
Original and final HTTPS URLs and retrieval/server metadata are recorded separately.
Classification: `secondary_reprocessed_source`; row origin and dataset license
remain unverified. This release is not entered as the original primary download.

Offline inventory observes 6,297 rows, ten original HLA strings, no duplicate
allele/peptide keys, no malformed or missing/non-finite values, and 482 numerical
zeros with text `0`. Peptide lengths are 8:67, 9:5,963, 10:143, 11:122, 13:1, 15:1.
No C67S identifiers appear in this secondary table. No allele or score is
rewritten. Zero mechanism remains unresolved; scores are not inverted into
purported physical half-lives.

The paper-to-original difference is 789 records. The released CSV has 788 more
rows than the original published total and one fewer than TLStab's published
total. The released CSV has 6,298 physical lines including its header; header
counting could account for the one-row difference, but this is an unverified
hypothesis about the publication. Different length criteria and IEDB processing identify possible source
stages, but do not explain row membership or either discrepancy. No original
versus secondary source equivalence, or experimental independence, is established.

## Acquisition deviation

During the authorized filtered TL-MHC clone, `git ls-tree -r -l HEAD` triggered
unintended lazy blob fetches, including an 8,904,535-byte pretrained TLBind model
blob and unrelated TLImm data blobs. The listing and fetch processes were stopped.
The full unintended blob inventory is not established. Git cache was retained
without deletion; weights and unrelated data were not materialized in the sparse
working tree, loaded, inspected as scientific inputs, or executed. This was an
out-of-scope acquisition error, not a successful restriction-compliant download.
The register records the known model blob identity and the limitation. Subsequent
inspection used name-only trees and explicit provenance-file selection; the
secondary CSV was retrieved separately over HTTPS and matched to the pinned blob.

## Offline reproduction and canonical reports

Python 3.11+ standard library only; imports and inspection do not write or download:

```sh
PYTHONPATH=src python3 -B -m stability_label_curation historical audit --json
PYTHONPATH=src python3 -B -m stability_label_curation historical audit --secondary /absolute/pinned/cleaned_train_data.csv --json
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
```

`--evidence` reuses the captured register offline. `--dtu` and
`--expected-dtu-sha256` support explicit local fixtures; production defaults
require the immutable Task 1.1 identity. Changed DTU or secondary bytes fail
before their respective analyses. Missing secondary data are reported unavailable,
not as zero observations. No historical-format parser is speculated.

After committing, create one evidence-only run from a clean tree with supported
`runs create --kind evidence-audit --config configs/netmhcstab_2013_evidence.json`
and repeat `--input` for DTU, secondary CSV, and recovered publication/service
evidence files. Supply `--run-id task-1_4-historical-netmhcstab-evidence` if that ID
is unused. Write with `historical audit --json --reports-dir /absolute/run/reports`.
The output guard requires matching hashed inputs in an existing run and never
replaces reports. Report hashes and input checksums are checked at completion.
The existing run CLI has no external-repository capture option; its empty external
repository list is preserved. The exact TL-MHC pin is recorded in the hashed
evidence configuration, Git-managed lockfile, and reports instead. The run schema
is unchanged.

Generated reports include the evidence register, artifact discovery and secondary
inventory, published count comparison, TLStab discrepancy assessment, conditional
row-overlap status, and report checksums. Retrieval receipts and execution
verification accompany the canonical run. No row-level overlap file is generated:
all historical overlap quantities are null and explicitly not computed. The
primary-file identity is
`5f2c6e82d198705a66974b4e42a0ed1412124c4b1e8f7033c7cd43bbdac07f67`.
No DTU/SPEARMINT input is modified or counted as an independent new source.

## Questions deferred

Obtain an author/institution-authenticated original table, including units,
version, augmentation separation, and permitted use; or a versioned IEDB export
with assay/reference identifiers and traceable membership. Establish the 789-row
published discrepancy and one-row release discrepancy before comparing physical
measurements. Numerical equality/difference alone cannot establish the identity
or independence of experimental assays. Preserve all original strings, numerical
zeros, and mutant identifiers in any later authorized comparison. No scientific
eligibility, zero semantics, mutation normalization, or pooling decision is made.
