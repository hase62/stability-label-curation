# Canonical stability observation registry (Task 1.8)

The registry is a reproducible input foundation for later scientific review. It
records source-reported measurement values and lineage without approving training
eligibility, independence, inclusion rules, target transformations, or splits.
It is not an independently validated experimental cohort or a training dataset.

## Observation identity and schema

`Observation`, a frozen typed dataclass, implements schema version 1. Every record
contains `schema_version`, `observation_id`, `source_id`,
`source_artifact_sha256`, `source_locator`, `original_allele`, `original_peptide`,
`original_measurement_text`, `parsed_measurement_decimal`, `measurement_type`,
`measurement_unit`, `assay_context`, `published_source_provenance`,
`row_origin_status`, `data_quality_flags` and `source_record_context`.
There is no training-eligibility field on an observation.

The ID is `obs1_` plus a full SHA256 of a canonical serialized identity:
identity version, source ID, immutable artifact SHA256, and exact source locator.
It never depends on an allele–peptide key, local home directory, output run,
float conversion, target normalization, or registry ordering. A locator is either:

- DTU: portable artifact path and original source line number.
- Jappe: portable workbook path, worksheet, original row and measurement cell.

Changing the immutable source bytes creates a different identity; relocating
identical bytes does not. Jappe C B/C cells retain separate identities even when
peptides or numerical values coincide. ID uniqueness is checked before publication.
Raw numeric strings remain original; Decimal parsing provides an exact numeric
representation, not a common modeled target. Invalid/non-finite or oversized
numeric representations fail validation before output rather than being imputed.

DTU raw lines are retained in record context. Jappe records preserve original
physical row cells (including derived/prediction fields), column roles, selected
header and approved ledger identity. Their original ZIP bytes and the full source
ledger remain immutable outside Git. Headers and auxiliary-only rows stay in that
ledger and do not become observations. Thus the registry preserves measurement
information and lossless source references without pretending to replace all
workbook content or OOXML metadata.

## Physical measurement separation

Only these type/unit combinations are accepted:

| Measurement type | Registry unit | Interpretation |
|---|---|---|
| kinetic_half_life | hours | Reported pMHC dissociation half-life |
| thermal_melting_temperature | degC | Publication-described thermal transition estimate |

`degC` is an explicit schema vocabulary mapping from the audited
`degrees_Celsius` field, with no numeric conversion. No log transform, Tm-to-hours
conversion, cross-unit mean, common ranking or regression target is calculated.

DTU assay context is described at the published dataset level as SPA dissociation;
individual row conditions remain unverified. Jappe's C1R contexts come from the
approved field audit. They are assay contexts, not substitutions for restricting
HLA identities.

## Sources and lineage

The global source registry remains `configs/data_sources.toml` with all seven IDs.
`configs/observation_registry.lock.json` is a subordinate, portable Task 1.8 lock:
input paths/hashes, count expectations, source roles, existing external Git pins,
scoped evidence-file hashes and unresolved questions. It does not supersede the
source registry or introduce training inclusion policy. No external checkout
inspection, Git blob operation, model loading or network request is needed.

| Representation | Registry contribution | Provenance limits |
|---|---|---|
| Original DTU 2016 | 28,166 kinetic records | Individual traces and zero semantics unverified |
| SPEARMINT Stage 2 | 27,031 aliases, zero new observations | Derived exact ordinary-DTU subset; released splits are lineage metadata |
| Jappe Data 3 | 1,094 A Tm candidates | Publication-described; individual MS traces unverified |
| Jappe Data 4 | 1,354 B Tm candidates | Same source-level limitation |
| Jappe Data 5 | 272 C context-specific values for 136 peptides | Context independence not established; never averaged |
| Historical NetMHCstab | Documentary evidence only | Original 5,509-row table unavailable; overlap unavailable, not zero |
| TLStab secondary scores | Secondary derived reference only | Historical lineage and physical measurement identity unresolved |
| Jappe Figure 2e / Source Data | Documentary evidence only | Complete identifiable C359 population unrecovered |

The total **30,886** counts measurement-value records, not independent experiments,
donors, or distinct peptides. No independent-experiment count is claimed.
Jappe transformed targets, affinity predictions and Source Data peak-area examples
are not additional Tm observations. No historical or TLStab raw artifact is required.
BigMHC and ITSNdb retain their metadata entries but are not processed by this task.

## DTU preservation and SPEARMINT aliases

All 75 original DTU identifiers are retained, including 1,135 C67S-annotated rows.
All 5,679 exact zeros retain original text `0.00`, `exact_zero` and
`zero_semantics_unresolved` flags. Flags also describe ordinary A/B and C67S
identifiers. No synthetic, missing, exact-physical-zero or censored designation
is inferred. Row origin remains
`published_raw_stability_table_row_origin_unverified` for positive and zero values.

Stage 2 CSVs and their pinned receptor reference are read using existing audited
parsers. Literal identifiers plus exact reference sequences, or uniquely supported
exact sequence mappings, produce traceable aliases. Each alias retains raw CSV
fields/cells, source filename/hash, record number, physical line span, released
split, label text, mapping evidence, external commit and canonical DTU ID.

Every alias must match one DTU key and exactly agree as Decimal hours. Unmatched
or ambiguous mappings, numerical disagreement, duplicate assignments within/across
splits, or incomplete ordinary-DTU coverage fail validation. No tolerance is used
to accept aliases. C67S is never mapped to wild type or excluded from DTU.
The expected counts are train 21,626, validation 2,705 and test 2,700.

All 1,103 released 181-residue sequence entries remain unchanged. Their exact
named-reference correspondence does not establish complete chains or experimental
material equivalence. No sequence repair or model execution occurs. The preprint's
27,034 aggregate versus 27,031 released rows remains a documented uncertainty.

## Jappe and repeated keys

The three original XLSX hashes and approved Task 1.6 ledger hash are verified
before accepting fields. Only its two publication-described raw-Tm role categories
are selected. Cell coordinates, exact headers, numeric types, formula/cache status,
parsed values and context mappings are validated. The earlier field-audit module
is reused without fitting new curves or interpreting unknown cells.

The 136 C peptides each contribute one C1R-A*02:01-context and one
C1R-B*07:02-context value; HLA restriction stays HLA-C*04:01. The 272 values are
not 272 distinct peptides or established independent replicates. Every Jappe row
uses `publication_described_source_row_underlying_assay_traceability_unverified`.

The summary lists 150 peptide–allele combinations appearing across distinct
reported methods or contexts: 136 paired C keys and 14 kinetic/Tm keys. These
records are retained individually. Shared sequences, equal values or different
methods do not independently establish historical measurement independence.

## Reproduction and safe publication

Python 3.11+ standard library only, from the repository:

```sh
PYTHONPATH=src python3 -B -m stability_label_curation registry validate --json
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
```

Validation is offline and read-only. Defaults use resolved project data/runs.
Repeatable `--input INPUT_ID=PATH` supports relocated or synthetic inputs; `--lock`
selects explicit fixture hashes and complete fixture expectations. There is no
checksum bypass, count-relaxation option, or optional historical-data requirement.
All nine used artifacts are gated before scientific row processing. Existing
committed evidence is also hash-checked against the portable lock.

After committing, create one canonical run through supported `runs create`
options: kind `observation_registry`, configuration
`configs/observation_registry.lock.json`, and nine repeatable `--input` arguments
for the DTU table, three Stage 2 CSVs, reference CSV, three Jappe XLSX files and
approved ledger. Then execute:

```sh
PYTHONPATH=src python3 -B -m stability_label_curation registry build \
  --output-dir "$HOME/codex/runs/stability-label-curation/task-1_8-canonical-observation-registry/reports"
```

Custom storage roots must use their resolved run path instead. The destination
must be an existing valid project run with every input/hash recorded. Unsafe
paths/symlinks, missing inputs, count discrepancies and existing outputs fail;
raw files are never overwritten. Atomic publication is per file. The final
checksum receipt marks bundle completion; interrupted output is retained without
automatic cleanup. The run-manifest schema is unchanged.

Outputs are `canonical_observations.jsonl`, `spearmint_stage2_aliases.jsonl`,
`registry_validation_summary.json`, `source_lineage_matrix.json`,
`measurement_type_summary.json`, `source_evidence_manifest.json`, report checksums
and execution verification. Ordering is DTU source lines, followed by approved
Jappe workbook/row/cell order; aliases follow train/validation/test source order.
These scientific JSON/JSONL outputs contain portable source references. Run
manifests and checksum receipts record actual local input paths for execution
provenance. Offline regeneration and final raw-input hashes verify reproducibility.

Later scientific review must decide zero semantics, C67S construct handling,
individual assay traceability, context dependence, eligibility, independence,
licensing, and future split policy. Missing historical/C359 populations remain
unresolved. This task neither resolves those decisions nor begins Task 1.9.
