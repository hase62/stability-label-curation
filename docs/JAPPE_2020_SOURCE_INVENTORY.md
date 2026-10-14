# Jappe 2020 primary supplement acquisition and structural inventory

Task 1.5 acquires four explicitly allowlisted publisher supplements and inventories
OOXML workbook structure. It does not extract measured-Tm training data, classify
individual rows, evaluate formulas, fit curves, join kinetic measurements, or
convert Celsius Tm into hours. Detailed block interpretation belongs to Task 1.6.

## Publication and scientific evidence

[Jappe et al., Nature Communications 11, 6305 (2020)](https://www.nature.com/articles/s41467-020-20166-4),
DOI `10.1038/s41467-020-20166-4`, describes temperature-dependent immunoprecipitation
and DIA mass spectrometry of naturally presented pHLA complexes. Methods/DIA
analysis specifies 8–11-mers; Generating thermostability curves describes sigmoid
fits. The reported references are **1,094 HLA-A*02:01**, **1,354 HLA-B*07:02**, and
**359 HLA-C*04:01** curves/peptides (Methods; Fig. 2). These are publication counts,
not worksheet dimensions or locally validated experimental-row counts.

Methods describes iRT normalization, dotP controls, `R² > 0.85` fits, and motif
outlier processing. Tm is the unfolding midpoint in degrees Celsius. Results/Fig.
2c compares HLA-C*04:01 peptides detected in both C1R assay contexts. Distinct
transformed-Tm ANN targets are described in Methods/Data transformation. The
Stability Predictor uses length-balanced human UniProt-Swissprot sampled negatives
(ten times each length group), assigned target zero. These publication categories
do not identify every workbook block or establish that zero means Tm = 0 °C.

Rights and permissions states CC BY 4.0, with exceptions for third-party material
carrying separate credit notices. Article-level licensing is documented; any
artifact-specific notices must be checked separately. No publisher SHA256 has
been identified. [Alternative PMC article](https://pmc.ncbi.nlm.nih.gov/articles/PMC7726561/)
returned a challenge during source verification.

## Four authorized publisher artifacts

The [source-specific manifest](../configs/jappe_2020_artifacts.json) supplements
the existing `jappe_2020` registry entry; it is not a second global source registry.
Its links were extracted from the official article's actual supplementary anchors,
not generated from suffix guesses. Publisher filenames are preserved.

| Stable artifact ID | Publisher filename | Intended publisher role |
|---|---|---|
| supplementary_data_3 | 41467_2020_20166_MOESM6_ESM.xlsx | HLA-A*02:01 ligands, Tm and transformed Tm |
| supplementary_data_4 | 41467_2020_20166_MOESM7_ESM.xlsx | HLA-B*07:02 ligands, Tm and transformed Tm |
| supplementary_data_5 | 41467_2020_20166_MOESM8_ESM.xlsx | HLA-C*04:01 ligands and Tm |
| descriptions | 41467_2020_20166_MOESM3_ESM.pdf | Descriptions of additional supplementary files |

Download hyperlinks:

- [Supplementary Data 3](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-020-20166-4/MediaObjects/41467_2020_20166_MOESM6_ESM.xlsx)
- [Supplementary Data 4](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-020-20166-4/MediaObjects/41467_2020_20166_MOESM7_ESM.xlsx)
- [Supplementary Data 5](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-020-20166-4/MediaObjects/41467_2020_20166_MOESM8_ESM.xlsx)
- [Descriptions PDF](https://media.springernature.com/original/springer-static/esm/art%3A10.1038%2Fs41467-020-20166-4/MediaObjects/41467_2020_20166_MOESM3_ESM.pdf)

Role descriptions will be checked against the acquired official descriptions PDF.
Supplementary Data 1–2 concern spectral-library ligands; Data 6 concerns evaluation
and is excluded. No Source Data workbook, extra supplementary PDF, raw-MS archive,
external repository, checkpoint, or prior Git object cache is required.

## Storage, acquisition, and provenance

Inputs go beneath `resolve_paths().project_data_dir / 'jappe_2020'`, normally
`~/codex/data/stability-label-curation/jappe_2020/`. Imports and path resolution
create no directories. Only explicit acquisition creates missing source folders.

```sh
PYTHONPATH=src python3 -B -m stability_label_curation jappe2020 fetch > /tmp/jappe2020_acquisition_receipts.json
PYTHONPATH=src python3 -B -m stability_label_curation jappe2020 inventory --json
```

`fetch --artifact supplementary_data_3` selects one authorized ID; repeat to
select more. Default fetch selects exactly four. No recursive crawling, Git
acquisition, retry loop, or unlisted download exists. Redirects retain the selected
filename and article identity on official publisher CDNs; other hosts, files,
HTTP, credentials, queries, and fragments are rejected before following.

Downloads verify TLS, request identity encoding, stream at most 64 KiB at a time,
and use finite connection/read timeouts (default 30 seconds). Caps are 15 MiB per
artifact and 50 MiB cumulatively per invocation, including failed streamed bodies.
This task must also stay below 50 MiB across actual acquisition attempts. Oversized
reported lengths are rejected before body reads; missing-length bodies reaching
the cap are conservatively rejected if EOF cannot be verified within the cap.
Unexpected HTML and invalid container signatures are rejected. XLSX archives
must pass bounded ZIP/CRC and basic OOXML checks; PDF checks are signature/end-marker
checks, not a complete PDF integrity or content validator.

Placement uses no-follow directory traversal, an exclusive partial file, fsync,
and atomic nonreplacing publication. Failed partials are removed; existing bytes
are never replaced, including a concurrent destination. Valid existing artifacts
are reused and identified by hash; reuse does not compare them with current
publisher bytes or recover their original HTTP metadata.

Receipts capture article/hyperlink/final URLs, UTC retrieval time, HTTP status,
original filename, local size/SHA256, reported length/type/ETag/Last-Modified,
integrity outcome, reuse status, and limitations. Local SHA256 verifies bytes;
server metadata and HTTP success do not establish scientific row provenance.
Publisher checksum remains null unless separately verified.

## Offline workbook inspection

The narrow inspector reads ZIP members without extraction. It lists actual package
parts; resolves the workbook, sheet, and shared-string relationships; preserves
sheet order/name/state; and records declared dimensions, physical/populated
rows/cells, storage types, formula counts, and cached/value text samples.
Header candidates and relevant text cells retain their references. Shared-string
and inline rich-text samples concatenate text runs; original XML remains intact.
No numeric cell value is converted into a scientific target or date.

Separated populated row/column ranges indicate possible multiple blocks, not
approved scientific partitions. Hidden sheets, merged ranges, external relationships
(not followed), unusual embedded/macro parts, and uninterpreted XML structures are
reported. Formula text and cached results are recorded without evaluation.
Styles, charts, dates, prediction semantics, and unknown blocks remain uninterpreted.

Inspection is bounded to 5,000 ZIP entries, 32 MiB per uncompressed part and 128 MiB
total. DTD/entities and unsupported XML encodings are rejected. Transitional
UTF-8 OOXML is supported; this is not a general Excel implementation. Missing or
invalid essential relationships fail clearly. These bounds and CRC checks do not
certify experimental observations.

Explicit local overrides are offline and read-only:

```sh
PYTHONPATH=src python3 -B -m stability_label_curation jappe2020 inventory --json \
  --file supplementary_data_3=/absolute/Data3.xlsx \
  --file supplementary_data_4=/absolute/Data4.xlsx \
  --file supplementary_data_5=/absolute/Data5.xlsx \
  --file descriptions=/absolute/descriptions.pdf
```

Synthetic tests construct tiny ZIP/XML fixtures; publisher artifacts are never
required for tests. Run all checks with:

```sh
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
```

## Canonical execution and remaining questions

After committing implementation and completing acquisition, create one run using
supported `runs create --kind source-inventory --config configs/jappe_2020_artifacts.json`
with four repeatable `--input` paths. Then use `jappe2020 inventory --json
--reports-dir /absolute/project/run/reports`. The destination must belong to an
existing run with all four unchanged inputs explicitly hashed. Receipts, test
logs, and report hashes belong under that run. The manifest schema is unchanged.

Task 1.4's approved history was safely pushed to HTTPS origin/main at
`0d5ba08abf428079d39ddb004d1749b5e1eb557d` before Task 1.5 changes. The Task 1.5
branch remains local, unmerged and unpushed. Prior artifacts and the TL-MHC object
cache are untouched.

Task 1.6 must identify each block's headers, units, transformations, quality-control
context, and row origins; reconcile publication counts with appropriate workbook
blocks; and examine repeated HLA-C peptide contexts without aggregating them
prematurely. Synthetic versus measured membership requires explicit evidence.
No inclusion/filtering, zero semantics, immunogenicity labels, or Tm-to-kinetic
mapping decision is made here.
