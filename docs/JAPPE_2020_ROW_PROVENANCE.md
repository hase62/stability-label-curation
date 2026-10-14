# Jappe 2020 row-level field provenance audit (Task 1.6)

This audit preserves every physical source row and cell and separates field
semantics. It creates an audit ledger, not a training table. A publication-described
Tm candidate has source-level support but no independently verified underlying
MS trace, curve, replicate identity, or training eligibility. No source artifact
is changed or re-downloaded; no other scientific dataset is joined.

## Source evidence and identity

[Jappe et al., Nature Communications 11, 6305 (2020)](https://www.nature.com/articles/s41467-020-20166-4),
DOI `10.1038/s41467-020-20166-4`, defines Celsius Tm as the sigmoid unfolding
midpoint (Fig. 1, equation 2). The workflow uses distinct C1R-A*02:01/B*07:02
contexts with endogenous HLA-C*04:01. Results/Fig. 2c explicitly links Data 5 to
C peptides found in both contexts; Fig. 2e separately reports 359 C peptides.
These citations distinguish populations without establishing complete membership.

The [captured evidence register](../configs/jappe_2020_row_evidence.json) records
sections, scopes, and limits. Publisher descriptions were verified from the
unchanged one-page PDF in Task 1.5. No user-uploaded PDF is assumed. Source paths
and roles come from the existing Jappe artifact manifest, subordinate to the
seven-entry source registry. The row evidence register pins **local** Task 1.5
byte identities; these are not publisher-provided checksums:

| Artifact | Original filename | Required local SHA256 |
|---|---|---|
| Data 3 | 41467_2020_20166_MOESM6_ESM.xlsx | `c15cdee1454aaeafc73574ebd456919e88a15acdc3d3e58cfabb0e44df6361aa` |
| Data 4 | 41467_2020_20166_MOESM7_ESM.xlsx | `0b1b160265ae060a6fc353feb2290706c009628f9182ade778a9f2575bb619de` |
| Data 5 | 41467_2020_20166_MOESM8_ESM.xlsx | `1b8827a653862c03cc313798f01b140cd470eda09912a5448dbaa43c4e731f35` |
| Descriptions | 41467_2020_20166_MOESM3_ESM.pdf | `cfa66ac399d065c250540d84512e82c83e09dbf22731a5a4451723840c0f828a` |

All four checksums are gated before XML/scientific analysis and checked again
at completion. Files remain under resolved `data/stability-label-curation/jappe_2020`.
Publisher license/byte-version limitations from Task 1.5 remain applicable.

## Verified schemas and column meanings

All workbooks have one sheet and one exact-header block. Coordinates are original:

| Sheet | A1 | B1 | C1 | D1 |
|---|---|---|---|---|
| A0201 | Ligand | Tm | Transformed Tm | Predicted binding affinity (NetMHCpan-4.0) |
| B0702 | Ligand | Tm | Transformed Tm | Predicted binding affinity (NetMHCpan-4.0) |
| C0401 | Ligand | Tm (A0201 data) | Tm (B0702 data) | absent |

Tm fields are `publication_described_tm_measurement` for A/B and
`paired_context_tm_measurement` for C. Their unit is degrees Celsius from the
publication. Derived columns are `tm_derived_transformation`, dimensionless.
The prediction header supports `predicted_binding_affinity`, not an experimental
measurement; its numerical units are not explicit in the header and remain
unverified. Every field retains header coordinates, raw values/types, semantic
role, evidence references, and unverified underlying-assay status. Multiple fields
in a row do not become independent observations.

Column I in A has only a literal-space cell at I2. Column E in B has only U+200B
at E1356. Both are mapped to auxiliary metadata on direct content evidence, with
no header invented. The cells and row 1356 remain in the ledger. Unknown or
additional populated fields remain unknown, rather than becoming targets.

## Actual data counts and numerical quality

| Source | Physical rows | Peptide rows / distinct peptides | Valid Tm fields | Derived fields | Prediction fields |
|---|---:|---:|---:|---:|---:|
| A0201 | 1,095 | 1,094 / 1,094 | 1,094 | 1,094 | 1,094 |
| B0702 | 1,356 | 1,354 / 1,354 | 1,354 | 1,354 | 1,354 |
| C0401 | 137 | 136 / 136 | 272 across two contexts | 0 | 0 |

A has one header plus 1,094 peptide rows. B has one header, 1,354 peptide rows,
and one auxiliary-only row. All peptide strings are canonical 8–11-mers; no
duplicate peptide keys, missing/empty/non-numeric/non-finite scientific values,
or formulas occur in the actual data blocks. Stored header indices are resolved
as text; they are not numeric scientific values.

| Source | 8-mers | 9-mers | 10-mers | 11-mers |
|---|---:|---:|---:|---:|
| A0201 | 4 | 711 | 216 | 163 |
| B0702 | 92 | 782 | 318 | 162 |
| C0401 | 13 | 112 | 7 | 4 |

Observed Celsius ranges, rounded here for readability (full strings in reports):
A 40.10564–65.43171; B 40.10564–67.12476; C/A-context 41.9414–63.9266;
C/B-context 42.3729–63.4112. All fall within the assay's 37–73 °C temperature
range. This plausibility check is not independent experimental validation. A/B
share a numerical minimum; its origin is not inferred from numerical equality.

## C assay contexts and the 136-versus-359 question

The HLA restriction for both C columns remains **HLA-C*04:01**. A0201/B0702 in
these headers denote cell-line assay contexts, not restriction to HLA-A/B. No
averaging, receptor remapping, or independent-replicate assertion occurs.

There are 136 unique C peptides, 136 valid values per context, 136 complete pairs,
272 numeric context fields, zero one-sided pairs and zero missing/malformed
context values. The complete-pair correlation uses all 136 rows and no exclusions:

`Pearson r = 0.77705123410676861477362430354586208824959969322979`

It rounds to the publication's 0.78. A centered two-pass calculation with Decimal
precision 50 avoids unstable raw-sum subtraction. Source citation, two-context
layout, and agreement support correspondence to Fig. 2c; individual plotted
point identities are not independently verified. The paper's 0.87 after specified
outlier removal is recorded but not recreated with an invented exclusion rule.

For differences **A-context minus B-context**, in Celsius: mean −0.68318456,
median −0.3654, minimum −10.2643, maximum 14.623, population SD 3.06985169;
p05 −5.8148 and p95 2.794025 (Type 7 quantiles). Paired values and source rows
remain separate in the ledger.

The paper explicitly describes the both-context comparison for Data 5, whereas
359 belongs to the inter-allelic distribution in Fig. 2e. Thus these numbers are
not established as competing counts of the same population. The available paired
table cannot reconstruct all 359 peptides or their context selection; no 223
rows are invented. A complete inclusion/exclusion rule remains unresolved.

The specific official follow-up candidate is the article's
[Source Data workbook](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-020-20166-4/MediaObjects/41467_2020_20166_MOESM11_ESM.xlsx).
Only its actual HTML hyperlink was inspected. It was **not downloaded**, and its
contents/version/checksum are unknown. A later narrowly authorized investigation
could inspect its Fig. 2e population evidence. No PRIDE archive was accessed.

## Transformation comparison

The original Methods equations describe:

- A, motif analysis: `u=(Tm-min)/(max-min)`, then
  `clip(u + 3*(u-median(u)), 0, 1)` (equations 3–4).
- B, Stability Predictor: `0.5*(Tm-min(Tm_all))/(max(Tm_all)-min(Tm_all))+0.5`
  (equation 5). Separate sampled training negatives receive target zero.

Actual transformed values range **0.5–1** in both A/B workbooks. Each contains
one exact 1 and no exact zero. Most raw stored numbers have 17 fractional decimal
places from Excel serialization; all are within 1e−12 of a five-decimal grid.
This grid does not prove a historical rounding rule.

Predeclared comparisons test both equations, with no rounding or candidate
five-decimal HALF_EVEN rounding, over three explicit populations: each workbook's
valid Tm cells, pooled acquired A+B cells, and pooled acquired A+B plus both C
contexts. The latter is not a certified complete `Tm_all` population. No fitted
coefficients or target replacement are used.

| Same-workbook population, unrounded prediction | A0201 maximum absolute error | B0702 maximum absolute error |
|---|---:|---:|
| Equation A | 0.76148 | 0.77490 |
| Equation B | 0.00000506561 | 0.00000509177 |

Equation B's mean absolute errors are approximately 0.00000247679 and
0.00000244999. All rows agree within 1e−5. Rounding B predictions to five decimals
matches **1,089/1,094** and **1,349/1,354** rows within 1e−12; five rows per workbook
still differ by approximately 1e−5. The reports retain largest-error source
references. Input Tm precision and unrecorded historical processing may matter,
but no unverified explanation is asserted.

For A, pooled extrema worsen maximum B error to approximately 0.03133059. For B,
all tested populations have the same extrema and produce indistinguishable B
predictions. Population scope is consequently not uniquely established there.
The numerical results support B-like per-workbook linear scaling rather than the
tested motif formula, but **exact historical generation and rounding remain
unresolved**. Output range alone is insufficient evidence.

Zero transformed targets, if encountered in other fixtures/sources, remain derived
values and do not imply zero-Celsius measurements or synthetic status. The acquired
workbooks identify no explicit synthetic training targets; absence of such labels
does not certify every row's origin. None is assigned synthetic or training-ready.

## Reproduction, output safeguards, and deferred validation

Python 3.11+ standard library, no network needed:

```sh
PYTHONPATH=src python3 -B -m stability_label_curation jappe2020 audit --json
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
```

The row reader reuses Task 1.5's bounded ZIP/CRC/XML and relationship safeguards.
It only visits physical XML cells, with limits of 20,000 rows and 100,000 cells
per workbook. No million-row metadata range is expanded. Shared/inline strings,
explicit types, absent/empty cells, numeric text, Unicode, formula/cache text,
worksheet coordinates, and XML order are retained. Formula caches are not used
as scientific numeric entries. Decimal numeric syntax/finiteness/size gates flag
unsafe values. No allele, peptide, Tm, or derived value is destructively normalized.

Fixture overrides use repeatable `--file ARTIFACT_ID=PATH` and matching explicit
`--expected-sha256 ARTIFACT_ID=HEX`; canonical execution uses the pinned defaults.
`--evidence` selects a captured register. Default inspection writes nothing.
`--reports-dir` explicitly publishes into an existing run with all four hashed
inputs recorded, verifies unchanged bytes, and refuses replacement. The run API
and schema are unchanged. Canonical execution follows the final clean code commit.

Outputs include schemas, field provenance, measurement inventory, transformation
comparisons, C-context audit, count reconciliation, evidence, and `jappe_rows.jsonl`.
The ledger preserves **2,588 physical source rows**, including three headers and
one auxiliary-only row. It records all original cells and relevant parsed fields;
**2,720 valid Tm fields** are candidate estimates, not certified independent
experiments. Reports and ledgers remain outside Git.

Eventual independent validation would need assay/peptide identifiers, temperature
points, per-replicate peak areas and QC, curve-fit parameters/uncertainty, source
membership, raw precision, and transformation implementation. The publication's
fit/QC descriptions do not supply these per-row details in the three workbooks.
Scientific inclusion, context aggregation, outlier treatment, prediction units,
transformation history, and C-population reconciliation remain deferred. No
training, immunogenicity labels, kinetic conversion, or subsequent task is begun.
