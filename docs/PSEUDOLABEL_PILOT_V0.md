# Frozen-Teacher EL/IM pseudolabel pilot v0

Task 2.4 scores the two released BigMHC Version 4 **training** members and writes
reversible candidate overrides. It does not modify original labels, refit the
Teacher, select final splits, optimize thresholds, evaluate predictive performance
or train BigMHC. Candidates are modeling interventions, not experimentally verified
repairs to EL presentation or T-cell response labels.

## Fixed exploratory rules

The source-specific [configuration](../configs/pseudolabel_pilot_v0.json) records
the existing source identities and rule version; it does not replace
`configs/data_sources.toml`.

| Original training label | Predicted kinetic half-life | Candidate pseudolabel |
| --- | --- | --- |
| 1 | strictly below 1.0 hour | 0 |
| 0 | at least 10.0 hours | 1 |
| Otherwise | any supported prediction | original label |

LOW is `[0,1)`, MID is `[1,10)`, HIGH is `[10,infinity)`. Exactly 1 hour does
not trigger LOW; exactly 10 hours triggers HIGH. The thresholds are engineering
defaults, not biological decision boundaries. The same directions apply to EL
and IM training candidates. MS-observed EL positives and publisher-described IM
outcomes retain their original experimental/source provenance regardless of any
proposed pseudolabel. Predicted stability does not prove presentation or T-cell
response, nor its absence.

## Frozen inputs and isolation

Use the [Task 2.3 Teacher](STABILITY_TEACHER_V0.md), SHA256
`a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99`,
with its 67 supported ordinary HLA-A/B models. The unchanged BigMHC archive is
authenticated against the existing registry's Version 4 checksum.

Seven explicit hashed inputs are required: archive, model, parent Teacher
manifest, parent execution receipt, saved Teacher partition, canonical registry,
and the Task 2.2 HLA mapping evidence report. The parent manifest records code,
configuration and training inputs; **its schema does not directly store model
output hashes**. The pinned execution receipt supplies the model and partition
hashes, checked against model provenance and the validated parent manifest.
No manifest schema is changed or output-input record fabricated.

Only `el_train.csv` and `im_train.csv` are decompressed. The reused ZIP inventory
reads directory metadata but never opens validation, test, IEDB, MANAFEST,
summary or pseudosequence members. Full-archive `testzip`/extraction is forbidden.
Allowed streams receive their own CRC and SHA256 checks and must match the
previously audited member identities and row totals. Merely hashing the archive
does not inspect compressed evaluation outcomes. The HLA evidence report is used
for explicit mappings, not validation-label analysis or threshold selection.

## Supported predictions and unchanged observations

Rows require exactly nine canonical uppercase amino acids, an explicit unique
mapping from Task 2.2, an exactly supported Teacher identifier and a finite
nonnegative prediction. Mapping is restricted to previously verified two-field
notation, including optional-asterisk variants only when explicitly evidenced.
No fuzzy matching, field truncation, C67S substitution or repaired sequence occurs.

Unsupported reasons are mutually exclusive, in order: length, amino-acid validity,
verified mapping, Teacher support and valid numerical prediction. A sparse
Teacher model remains unsupported. Unsupported rows have no fabricated prediction
and no override. Their original label remains the default; per-reason, per-label
and per-HLA aggregate counts account for every source observation.

No source rows are destructively deduplicated. Repeated contents at distinct row
coordinates remain distinct observations. Unexpected source schemas, labels,
member checksums or totals fail clearly rather than being silently repaired.

## Artifacts and exact row identity

Under one project run:

```text
predictions/el_train_teacher_scores.csv.gz
predictions/im_train_teacher_scores.csv.gz
processed/el_train_pseudolabel_overrides.csv.gz
processed/im_train_pseudolabel_overrides.csv.gz
reports/pseudolabel_summary.json
reports/pseudolabel_experiment_plan.json
reports/execution_verification.json
```

Scores contain every supported training row, including no-change rows. Sparse
override files contain only proposed label changes. Both use the same documented
CSV schema: source member, row index, physical line number, row identity and
checksum, original peptide/HLA/label, resolved HLA, predicted hours, stability
category, proposed pseudolabel, action/no-change status, Teacher version/hash,
rule version and source-exposure flags. All generated rows remain outside Git.

`row_index` is the one-based CSV data-record index, excluding the header.
`source_line_number` is the physical ending line reported by Python's CSV reader.
Identity is `bmhc_` plus SHA256 of archive SHA256, a NUL separator, authorized
member basename, another NUL, and the decimal row index. Thus identical sequences
or labels do not collapse different source rows.

`source_row_sha256` hashes compact UTF-8 JSON `[header_fields, original_fields]`,
with `ensure_ascii=False` and separators `(',', ':')`. It covers all original
field strings, including IM's `rand`, without claiming byte equality to a quoted
CSV line. Original CSV bytes remain in the immutable archive; member hashes and
headers are recorded in the summary. The original label is explicitly retained
in every override, making candidate changes reversible without rewriting source.

Gzip output has empty filename, timestamp zero, UTF-8, LF CSV lines and fixed
compression level 6. Files use temporary partials and atomic nonreplacing
publication with no-follow paths. A successful execution receipt completes the
scientific output set; a run manifest alone does not establish successful scoring.
Existing artifacts are preserved. A failed run removes only its own unpublished
temporary partials, not earlier data or runs.

## Exposure and descriptive summaries

The source index distinguishes the 21,559 observations actually used to fit the
67 supported models from all 27,031 ordinary DTU source observations. It uses
the saved partition and model support metadata, not SPEARMINT copies. For every
scored row, report exact peptide and peptide–HLA exposure to the actual fitted
data, within-one-mismatch exposure both across any HLA and at the same HLA, and
exact exposure to the full ordinary source population. Near matches include
exact identity and use the Task 2.0 aligned nine-mer masked-position predicate.
No indel, long-peptide fragment, antigen-family or donor inference is made.

Exposure is an explicit warning, not independent corroboration or an automatic
exclusion. Counts cover scored rows and changed candidates separately. Teacher
validation-source membership is not mislabeled as actual fitting exposure.

Summaries include total/scored/unsupported rows, original-label distributions,
HLA coverage, LOW/MID/HIGH counts by original label, both change directions and
fractions with explicit denominators. Prediction distributions use exact streamed
fixed-bin counts, minimum, maximum and mean; no full prediction array or sampled
quantiles are retained. Per-class change fractions at least 20% are flagged as
potentially large. That flag is descriptive and never adjusts either threshold.

Memory depends on the small frozen source index, HLA aggregates and gzip/CSV
buffers, not the number of EL records. The full 15-million-row EL table is never
materialized. Two complete passes may take several minutes on CPU.

## A–D plan and later application

The machine-readable plan points A to no overrides, B to EL overrides only,
C to IM overrides only, and D to both. The initial corrected condition uses both
LOW and HIGH rules. `candidate_for_policy` filters saved overrides as `low_only`
or `low_and_high`, without rescoring or modifying labels.

Before actual training, an adapter must accept an explicit row-ID authorization
set from the subsequently established split protocol, authenticate the source
archive/member and original fields/label, check Teacher/rule identity, and reject
duplicate, unordered or unauthorized overrides. `OverrideGuard` supplies coordinate,
ordering, identity and authorization checks; the future adapter must additionally
compare `source_row_sha256` and original label to the actual source record.
There is no actual application adapter, authorization mask, final split or
corrected training table in this task. Validation/test rows are never eligible
override targets. Original labels remain default for unsupported or absent rows.

## Run and reproduce offline

Use the existing supported run infrastructure after committing code. For example:

```python
import sys
from stability_label_curation import pseudolabel_pilot as pilot
from stability_label_curation import run_manifest as runs
from stability_label_curation.paths import resolve_paths
p = resolve_paths()
configuration = p.repository_root / pilot.CONFIG
c = pilot.load_config(configuration)
_, inputs = pilot.resolve_inputs(c, p)
run = runs.create_run(paths=p, kind='pseudolabel_pilot', config=configuration,
    inputs=[i['path'] for i in inputs], argv=sys.argv)
print(run)
```

```sh
PYTHONPATH=src python3 -B -m stability_label_curation pseudolabel pilot --config configs/pseudolabel_pilot_v0.json --out <run-directory>
PYTHONPATH=src python3 -B -m stability_label_curation pseudolabel pilot --config configs/pseudolabel_pilot_v0.json --out <run-directory> --verify-existing
PYTHONPATH=src python3 -B -m stability_label_curation runs validate <run-id>
```

Replay streams both members completely again, compresses generated output only
into hashing sinks, and compares every compressed artifact hash and aggregate
report byte-for-byte. It writes no replacement or duplicate datasets. Python and
zlib versions are recorded; cross-version compressed byte identity is not assumed.
Explicit `--input INPUT_ID=PATH` overrides support checksum-pinned synthetic
fixtures and relocated sources. Ordinary execution requires unchanged inputs
recorded in the output run. Tests use synthetic weights/data and prohibit network,
Teacher fitting and broader data audits. Run the full suite in the existing
Teacher environment to include its training tests.
