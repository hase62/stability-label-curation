# Data source manifest

`configs/data_sources.toml` is the single source registry. Python 3.11+ loads it
with `tomllib`; no runtime dependencies, network access, downloads, dataset
parsers, or training are involved. Validation checks metadata consistency, not
scientific eligibility or the truth of external claims. It does not certify that
every row in a source is experimentally measured. There is no separate
scientific registry implementation.

## Commands and API

```sh
PYTHONPATH=src python3 -m stability_label_curation sources list
PYTHONPATH=src python3 -m stability_label_curation sources list --json
PYTHONPATH=src python3 -m stability_label_curation sources validate
PYTHONPATH=src python3 -m stability_label_curation sources show netmhcstabpan_2016 --json
PYTHONPATH=src python3 -m stability_label_curation sources validate --manifest /path/to/independent.toml
```

`--manifest` is accepted before or after the sources subcommand. These commands
are read-only, return 0 on success and 1 for loading/validation/lookup failures,
and retain the existing storage configuration safeguards. No directories are
created. Standard Python bytecode caching may occur during CLI imports; use `-B`
when even interpreter cache writes must be suppressed.

`load_manifest(manifest=None, paths=None)` defaults to
`resolve_paths().repository_root / "configs/data_sources.toml"`. An explicit
manifest path does not change the project data storage root. `validate_manifest`
accepts an already decoded document. Both return an immutable `SourceRegistry`
with `get(source_id)`, `list_sources()`, and `as_dict()`. Sources are sorted by ID;
JSON listing is an object with `schema_version` and `sources`, and JSON show is a
single source object. Optional absent values become JSON `null`, and tuple
metadata becomes JSON arrays. Lookup failures identify the requested ID.
`SourceMetadata.target_path(paths)` resolves the intended artifact location.

## Schema version 1

The top-level keys must be exactly `schema_version = 1` and a nonempty array of
`[[sources]]` tables. Unknown keys, duplicate IDs, unsupported schema versions,
invalid types, empty strings, and missing mandatory fields are errors.

| Mandatory field | Contract |
| --- | --- |
| `source_id` | Stable lowercase identifier matching `[a-z][a-z0-9_]*` |
| `title`, `notes` | Nonempty descriptive strings |
| `source_type` | One of the source classifications below |
| `research_role` | One of the roles below |
| `species_scope` | `human_hla_i`, `mixed_species`, `mouse`, `rat`, `unknown`, `not_yet_verified` |
| `measurement_type` | A classification below; source-level intended measurement, not a row label |
| `provenance_status` | An explicit status below |
| `landing_url` | HTTP(S) URL without credentials or whitespace |

Optional string fields are `publication_doi`, `download_url`,
`target_relative_path`, `expected_sha256`, `license`, `artifact_name`,
`published_version`, `count_basis`, `measurement_unit`, `assay_conditions`, and
`verification_notes`. DOI values are identifiers beginning `10.` followed by a
registrant number and slash, rather than DOI URLs. DOI syntax validation does
not prove a DOI exists. `publication_doi` can identify a versioned data deposit,
as it does for BigMHC v4.

`expected_record_count` and `expected_allele_count` are positive integers. Either
requires `count_basis = "published_expectation"`. `columns`, `training_datasets`,
`validation_datasets`, `evaluation_datasets`, and `evidence_urls` are optional
arrays of nonempty strings; evidence entries must be HTTP(S) URLs. These arrays
record published file purposes, not inspected archive contents or approved
split independence.

The explicit values `unknown` and `not_yet_verified` are accepted only in
`species_scope`, `measurement_type`, `provenance_status`, `license`,
`published_version`, `measurement_unit`, and `assay_conditions`. Other unverified
optional fields must be omitted, including URLs, checksums, DOI, and counts.
Document unresolved facts in `notes` or `verification_notes`. `source_type` and
`research_role` always require a known classification.

## Classifications and compatibility

| Source type | Meaning |
| --- | --- |
| `experimental_dataset` | Source described as experimental; still subject to row auditing |
| `mixed_dataset` | Collection may combine observed labels, synthetic rows, or predictions |
| `synthetic_dataset` | Constructed examples, requiring `synthetic` measurement classification |
| `prediction_dataset` | Computed outputs, requiring `prediction_only` classification |
| `model_reference` | Model/checkpoint reference; never an experimental dataset |
| `dataset_reference` | Reference whose exact downloadable files may remain unresolved |

Measurements are `kinetic_half_life`, `thermal_melting_temperature`,
`immunogenicity`, `synthetic`, `prediction_only`, `mixed`, `not_applicable`,
`unknown`, or `not_yet_verified`. Experimental datasets require one of the first
three. Model references accept only `not_applicable`, `prediction_only`, or
`mixed` (for a reference covering both models and dataset material).

| Research role | Allowed source types | Allowed measurements |
| --- | --- | --- |
| `primary_kinetic_candidate` | experimental_dataset | kinetic_half_life |
| `secondary_thermal_candidate` | experimental_dataset, mixed_dataset | thermal_melting_temperature |
| `downstream_immunogenicity` | experimental_dataset, mixed_dataset | immunogenicity |
| `independent_evaluation_candidate` | experimental_dataset, mixed_dataset, dataset_reference | immunogenicity |
| `historical_overlap_audit` | experimental_dataset, mixed_dataset, dataset_reference, model_reference | kinetic_half_life, mixed, not_applicable, unknown, not_yet_verified |
| `model_comparison` | model_reference, prediction_dataset, dataset_reference, mixed_dataset | prediction_only, not_applicable, mixed, unknown, not_yet_verified |
| `audit_only` | any supported type | any supported measurement |

The four candidate/downstream roles require `human_hla_i`. Mouse and rat are
outside the primary research scope; mixed/unknown species references may be
recorded for auditing, without authorizing research inclusion. Role compatibility
is a schema check, never an automatic scientific inclusion decision.

## Provenance and measurement boundaries

- `row_audit_required`: source/publication evidence exists, but row-level validity
  and separation have not been established.
- `unresolved_pending_audit`: original provenance remains unresolved; SPEARMINT
  uses this status and remains audit-only.
- `unknown`: provenance information is unavailable.
- `not_yet_verified`: metadata/provenance verification remains pending.
- `row_provenance_verified`: reserved for an explicitly documented future audit.
  The validator does not perform or certify that audit.

Kinetic half-life (DTU, hours) measures dissociation over time. Thermal melting
temperature (Jappe, Tm) measures a different property and must remain separate.
No conversion or pooling occurs here. Synthetic negatives and prediction-only
values are not experimental measurements. Numerically zero stability does not
establish synthetic origin. Chemically synthesized peptides used in actual
experiments are also different from computationally constructed negative rows.

Jappe supplementary rows require separation of measured Tm, synthetic negatives,
and predictions. BigMHC EL datasets concern presentation; IM datasets concern
immunogenicity. Predictions in either collection are not observed stability.
Model checkpoints are not experimental datasets. ITSNdb labels must come from
source evidence; missing labels must not be fabricated or inferred.

Published expected counts describe reference expectations, not verified local
counts, unique independent observations, or proof of validity. The manifest has
no verified-local-count field. NetMHCstab 2013 and NetMHCstabpan 2016 may overlap;
their counts must not be summed as independent observations.

## Artifact paths and future verification

Targets are portable POSIX file paths relative to
`resolve_paths().project_data_dir`, never the checkout, data root, or runs root.
For example, `netmhcstabpan_2016/Stability.txt` is beneath project data storage.
Absolute POSIX/Windows paths, Windows drives, backslashes, colons, empty or dot
components, and `..` are rejected. The basename must match `artifact_name`.
Resolution checks existing symlinks and rejects targets escaping the project
storage boundary. Checks create no directories and do not reserve a path; a
future downloader must repeat boundary checks immediately before writing.

A `download_url` requires an identified `artifact_name`, `target_relative_path`,
nonempty `evidence_urls`, and `verification_notes` explaining the independent
check. It must be taken from a publisher/repository link or verified metadata;
never construct guessed artifact endpoints. A landing-page link check is
distinct from fetching the artifact and testing its availability.

`expected_sha256` requires the same artifact/evidence fields and exactly 64
hexadecimal characters. It must be published or verified for that exact named
artifact and version. BigMHC's recorded value is the publisher's v4
`datasets.zip` checksum, not a locally computed hash. The v2 checksum is
different and must not be substituted. A future authorized download task should
record redirects/version, hash the actual bytes, compare with the published
expectation, verify license applicability, and retain provenance evidence.
Validation has no network requests and cannot enforce whether an evidence claim
is truthful. Reviewers must inspect the evidence.

## Initial inventory and evidence limitations

The seven IDs are `netmhcstabpan_2016`, `netmhcstab_2013`, `jappe_2020`,
`bigmhc_v4`, `itsndb`, `spearmint_stability_audit`, and `tlstab_reference`.
Per-source `verification_notes` record checks and limits from 2026-10-11.
Only DTU's Stability.txt link is recorded as a direct download URL. Only
BigMHC's datasets.zip has an established published checksum and dataset license.
No artifact bytes were downloaded or hashed. Some publication/repository pages
were blocked; indexed publication metadata was used where stated. All sources
retain future row or artifact provenance work.

## Adding a source

1. Add a stable `[[sources]]` ID and every mandatory field. Pick a role and
   classification consistent with the intended use and available evidence.
2. Cite original publication/repository evidence, its exact version, and the
   verification date and limits. Leave optional unsupported facts absent.
3. Record published counts with their explicit basis. Document overlap risks,
   species limits, assay differences, and mixed evidence in notes.
4. Add artifact metadata only after independently identifying its URL and
   matching any checksum to the exact artifact. Keep files under project data.
5. Run `sources validate` and the complete unittest suite, review the scientific
   classification, and commit the small TOML change on an authorized branch.

Metadata registration never authorizes downloads, parsing, training, evaluation,
or scientific inclusion. Those require a subsequent authorized task.

Task 1.5 records Jappe's four publisher supplements in
[`jappe_2020_artifacts.json`](../configs/jappe_2020_artifacts.json), subordinate to
the existing registry identity/DOI/article URL. The multi-artifact manifest keeps
verified links and roles separate from acquisition receipts and locally observed
workbook structure. Published counts and worksheet dimensions do not establish
experimental row counts. See [the Jappe source inventory](JAPPE_2020_SOURCE_INVENTORY.md).

Task 1.8's [observation registry](CANONICAL_STABILITY_OBSERVATION_REGISTRY.md)
uses the existing seven source IDs. Its portable `observation_registry.lock.json`
pins audited artifacts, evidence and lineage roles without changing this schema
or making training-inclusion decisions. SPEARMINT is represented as DTU aliases;
kinetic hours and thermal Celsius remain separate physical measurement types.
