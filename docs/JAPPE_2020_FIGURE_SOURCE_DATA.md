# Jappe 2020 Figure Source Data audit (Task 1.7)

This is an artifact and figure-population audit, not training-data curation.
Task 1.6 is approved and closed. Its captured row ledger and C-context report are
reused as hashed evidence; its audit is neither rerun nor modified.

## Authoritative source and acquisition

[Jappe et al., Nature Communications 11, 6305 (2020)](https://www.nature.com/articles/s41467-020-20166-4),
DOI `10.1038/s41467-020-20166-4`, provides a separate **Source Data** hyperlink:

<https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-020-20166-4/MediaObjects/41467_2020_20166_MOESM11_ESM.xlsx>

The actual publisher anchor and exact URL were verified from bounded official
article HTML on 2026-10-14. The bare article request first attempted an
authentication redirect, which was rejected. The same official article with
`?error=cookies_not_supported` returned its public HTML without following an
external authentication endpoint. No credentials or TLS exceptions were used.

The sole acquired scientific artifact is `41467_2020_20166_MOESM11_ESM.xlsx`,
149,509 bytes, retrieved at `2026-10-14T07:28:04.776677Z`, HTTP 200. Its resolved
URL equals the hyperlink. Local SHA256:

`fae10a4fcdb681cd1e925104406b6973861f5777e83b7dcbd42a79e0013c07a4`

Storage is resolved through `paths`: `data/stability-label-curation/jappe_2020/`.
There is no verified publisher SHA256. Server metadata includes ETag
`15d0119b79d4902c3487b2c3638e084f`, Last-Modified `Mon, 04 Dec 2023 16:49:21 GMT`,
Content-Type `application/octet-stream`, and no Content-Length. These are server
claims, not a publication-time version guarantee. All ZIP member CRC checks pass.

Acquisition is restricted to this filename on official publisher CDNs, HTTPS
with normal certificate verification, finite timeout, bounded streaming, a
**5 MiB cap**, partial-file cleanup and atomic nonreplacing final placement.
Existing files are identified and retained; mismatched audit hashes fail.
The old four-artifact acquisition allowlist remains unchanged. No other
supplements, Source Data variants, PRIDE data, repositories or models were fetched.
The article states CC BY 4.0 with its usual third-party-material qualification;
this is not a separately verified license for every underlying MS resource.

## Actual workbook contents

Six visible sheets occur in this order; worksheet parts are `sheet1.xml` through
`sheet6.xml`. There are 15 archive members, shared strings, no formula cells,
and no chart parts, external-link parts or embedded payloads. Physical rows,
including headers and empty/auxiliary rows, total **2,603**; cells total **9,238**.
Worksheet dimensions are metadata and never expanded into observation counts.

| Sheet | Dimension | Physical rows / cells | Identifiable block |
|---|---|---:|---|
| Suppl Fig 3a | A1:AK16 | 16 / 526 | 12 A peptides, 432 raw peak areas |
| Suppl Fig 3b | A1:QE18 | 17 / 527 | 12 B peptides, 432 raw peak areas |
| Suppl Fig 3c | A1:OQ22 | 17 / 535 | 12 C peptides, 432 raw peak areas |
| Suppl Fig 4 | A1:C99 | 99 / 294 | 96 A peptides, separate t1/2 and Tm fields |
| Suppl Fig 5a | A1:C1097 | 1,097 / 3,288 | 1,094 A peptides, Tm and median peak area |
| Suppl Fig 5b | A1:C1357 | 1,357 / 4,068 | 1,354 B peptides, Tm and median peak area |

Raw peak-area blocks contain a temperature row (row 3), a peptide/replicate
header (row 4), and peptide rows 5–16. There are 12 temperatures, 37–73 Celsius,
and three replicate columns per temperature. Peak-area units are instrument
area units, not Tm. Exact zeros number 102 / 79 / 106 for A / B / C; none is
assigned synthetic status or interpreted as a zero-Celsius estimate. No curves
are fitted. The C title explicitly states **from C1R-A*02:01 assay**, while HLA
restriction remains HLA-C*04:01.

Suppl Fig 4 has headers `Peptide`, `t1/2`, `Tm` at A3/B3/C3. The paper's
kinetic-comparison section supports keeping half-life and Tm distinct. These
96 rows are inventoried; no kinetic source join or unit conversion occurs.
Suppl Fig 5a/b have `Peptide`, `Tm`, `Median peak area at 37℃` at A3/B3/C3.
Numeric values, original coordinates, source order and cell types are preserved.
All identifiable blocks have valid numeric fields and no duplicate peptide keys.

Unusual cells are retained rather than repaired:

- `Suppl Fig 3b!QE18` contains U+200B, an auxiliary nonprinting cell.
- `Suppl Fig 3c!OL22:OQ22` contains six numeric cells without a peptide identifier
  or applicable temperature/replicate header. Their scientific identity remains
  unresolved. They are not six Tm measurements or additional peptides.
- Workbook revision/AlternateContent/extLst elements are reported as
  uninterpreted metadata. No scientific meaning is assigned to them.

## Figure 2 and the HLA-C population

The workbook contains **no Figure 2 sheet or identified Figure 2c/d/e block**.
No 359-value C Tm distribution, anonymous C Tm array or aggregate Figure 2 table
was recovered. The recovered Figure 2e C-value count is zero **within this
artifact**; the biological population and its overlap are unavailable, not zero.
No peptide identities or assay-context mapping for the 359 population are recovered.

The paper's Figure 2e legend reports 1,094 A, 1,354 B and **359 C peptides**.
The Results separately link Figure 2c and Supplementary Data 5 to C peptides
identified in both contexts. The approved Task 1.6 evidence contains 136 complete
C pairs and PCC **0.7770512341**, rounding to the paper's 0.78. That result is reused
without recalculation; the 0.87 outlier-removed result is not reproduced.

All **12/12** C peak-area examples have exact peptide-string matches in the
approved 136-pair ledger; 124 ledger peptides do not occur in this example block.
This is an identifier comparison between an example peak-area subset and a
paired-Tm table. It supplies no new fitted Tm, full-population membership, or
independent experiment evidence. No inference is made from 359 minus 136.

## A/B numerical distribution evidence

Suppl Fig 5a/b match **1,094/1,094 A** and **1,354/1,354 B** peptide identifiers
in the approved ledger, with no unmatched or ambiguous keys. Their higher-precision
Tm fields differ from the ledger's stored values by at most
`0.000004998228001` and `0.000004998336401` Celsius respectively; all agree within
`1e-5`. Neither comparison has exact Decimal equality. Original versions remain
separate; this does not establish historical rounding implementation.

Source Data medians are **57.816534411615400** and **59.9497040429302995** Celsius,
consistent with the article's one-decimal 57.8 and 59.9. The A/B numerical arrays
and summaries are reproducible, but the full three-allele Figure 2d/e distributions,
C median 53.5, plot bins and inter-allelic significance tests cannot be reproduced
from the acquired material. No histogram bins, C measurements or plotting values
are invented. Quantiles in these audit summaries use Type 7 interpolation.

## Reproduction and canonical evidence

Python 3.11+ standard library, from the repository:

```sh
PYTHONPATH=src python3 -B -m stability_label_curation jappe2020 figure-fetch
PYTHONPATH=src python3 -B -m stability_label_curation jappe2020 figure-audit --json
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
```

The second command is offline and read-only. `--source-data`, `--approved-ledger`
and `--approved-context-report` allow explicit local overrides. A matching
`--expected-sha256 INPUT_ID=HEX` pins each fixture override. There is no hash-bypass
flag. The source-specific evidence configuration remains subordinate to the
existing `jappe_2020` registry entry; no global schema changes occur.

After committing, create one canonical run using supported `runs create --kind
source_audit --run-id task-1_7-jappe2020-figure-source-data --config
configs/jappe_2020_figure_evidence.json` with repeatable `--input` for the Source
Data workbook and both approved Task 1.6 report files. Then select that run's
`reports/` using `figure-audit --reports-dir`. Existing reports are not overwritten.
The canonical run records the new commit and all three actually read inputs.
Original workbooks from Task 1.6 are not reread or revalidated.

Reports include source inventory, population reconciliation, identifier/numerical
comparison, captured evidence, a physical-cell JSONL ledger, acquisition receipt,
checksums and execution verification. All generated files remain under runs.
Independent offline recomputation verifies deterministic scientific JSON/JSONL;
acquisition timestamps remain historical receipt metadata.

The unresolved next step is author/institution clarification of the complete
Figure 2e C peptide–Tm list and its assay-context/selection rules. Any further
acquisition or author contact requires separate authorization. Training eligibility,
measurement independence, context aggregation, synthetic status and historical
precision decisions remain deferred. Task 1.8 is not begun.
