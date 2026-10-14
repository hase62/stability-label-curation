# Stability-guided curation of human HLA-I immunogenicity training labels

The goal is to test whether an independent stability labeler trained on provenance-traceable measured human HLA-I stability data improves external generalization by removing or holding out high-confidence stability-inconsistent positive training examples. Stability is not added as an input feature, and the immunogenicity evaluator architecture and loss remain unchanged.

## Local storage

- `~/codex/data`: reproducible external source data.
- `~/codex/repos`: Git repositories; this project lives in `stability-label-curation/`.
- `~/codex/runs`: regenerable analysis outputs and run artifacts.

Source data and run artifacts are not stored in Git. Paths should resolve from `$CODEX_ROOT` with fallback `~/codex`; `$CODEX_DATA_ROOT`, `$CODEX_REPOS_ROOT`, and `$CODEX_RUNS_ROOT` may override the respective derived roots.

Mac is the primary development and analysis environment. WSL2 with 2 x RTX 4090 is the GPU compute environment. GitHub will synchronize the repository between systems.

Resolve storage without writing files, inspect the environment, or explicitly initialize
the project data and runs directories (Python 3.11+, standard library only):

```sh
PYTHONPATH=src python3 -m stability_label_curation paths
PYTHONPATH=src python3 -m stability_label_curation paths --json
PYTHONPATH=src python3 -m stability_label_curation doctor
PYTHONPATH=src python3 -m stability_label_curation init-storage
```

Overrides must be absolute paths or use `~/...`. Initialization is idempotent;
imports, path resolution, and `doctor` never create directories. See
[the storage policy](docs/STORAGE_POLICY.md) for the contract and platform details.

## Bootstrap validation

The version-controlled [data source manifest](configs/data_sources.toml) records
source metadata and intended research roles. Inspect or validate it without
downloading scientific data:

```sh
PYTHONPATH=src python3 -m stability_label_curation sources list
PYTHONPATH=src python3 -m stability_label_curation sources list --json
PYTHONPATH=src python3 -m stability_label_curation sources validate
PYTHONPATH=src python3 -m stability_label_curation sources show netmhcstabpan_2016 --json
PYTHONPATH=src python3 -m stability_label_curation sources validate --manifest /path/to/manifest.toml
```

See [the manifest schema and provenance policy](docs/DATA_SOURCE_MANIFEST.md).
Metadata validation does not certify individual experimental rows or authorize
scientific inclusion. Kinetic half-life, thermal melting temperature, synthetic
negatives, and model predictions remain distinct.

Create a run only when explicitly requested, from a clean committed checkout;
then inspect its provenance without changing storage:

```sh
PYTHONPATH=src python3 -m stability_label_curation runs create --kind infrastructure --seed 0
PYTHONPATH=src python3 -m stability_label_curation runs list --json
PYTHONPATH=src python3 -m stability_label_curation runs show <run_id> --json
PYTHONPATH=src python3 -m stability_label_curation runs validate <run_id>
```

Creation supports `--description`, `--config`, repeatable `--input`, and a strict
`--run-id`. `--allow-dirty` creates an explicitly noncanonical development run.
See [run manifests and reproducibility limits](docs/RUN_MANIFEST.md). Run outputs
remain outside Git, and this infrastructure performs no scientific experiments.

Requires Python 3.11 or later; no dependency installation is needed for these source-layout checks:

```sh
PYTHONPATH=src python3 -B -c "import stability_label_curation; print(stability_label_curation.__file__)"
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
```

Task 1.1 provides [original DTU 2016 acquisition and raw inventory](docs/NETMHCSTABPAN_2016_RAW_AUDIT.md).
The raw artifact stays in project data storage. Only `fetch` downloads; inspection
is offline and read-only unless `--report` is explicitly supplied:

```sh
PYTHONPATH=src python3 -B -m stability_label_curation dtu2016 fetch
PYTHONPATH=src python3 -B -m stability_label_curation dtu2016 inspect --json
PYTHONPATH=src python3 -B -m stability_label_curation dtu2016 inspect --input /path/to/local/Stability.txt --json
```

Preserve the acquisition JSON receipt. Published counts and numerical zeros do
not establish individual rows' experimental or synthetic origin; Task 1.2
provenance questions remain open.

Task 1.2 adds [source evidence, zero-value semantics, and C67S context](docs/NETMHCSTABPAN_2016_SOURCE_EVIDENCE.md).
The audit verifies the pinned Task 1.1 checksum and runs entirely offline:

```sh
PYTHONPATH=src python3 -B -m stability_label_curation dtu2016 audit
PYTHONPATH=src python3 -B -m stability_label_curation dtu2016 audit --json
```

Use `--reports-dir /absolute/project/run/reports` to explicitly write complete
audit reports and lossless row flags into an existing run with the raw artifact
recorded as an input. All row origins remain unverified; the audit does not
approve training labels or filtering. `--evidence` supports offline reuse of a
captured evidence register.

Task 1.3 provides a [pinned SPEARMINT Stage 2 / DTU overlap audit](docs/SPEARMINT_STAGE2_DTU_OVERLAP.md):

```sh
PYTHONPATH=src python3 -B -m stability_label_curation spearmint audit --json
```

Inspection is offline and read-only. `--reports-dir` explicitly writes audit
reports into an existing project run with every input recorded. The external
lockfile pins source bytes; matching SPEARMINT rows are never added as independent
measurements. No external code, dependencies, or weights are loaded.

Task 1.4 documents [historical NetMHCstab source recovery and limitations](docs/NETMHCSTAB_2013_HISTORICAL_PROVENANCE.md).
The original 5,509-row table remains unrecovered; overlap is not computed.
A separately pinned TLStab secondary score CSV is inventoried without treating
it as the original measurements:

```sh
PYTHONPATH=src python3 -B -m stability_label_curation historical audit --json
```

Inspection is offline and read-only. `--evidence`, `--dtu`, and `--secondary`
support explicit local inputs; `--reports-dir` explicitly publishes evidence-only
reports into an existing run with matching hashed inputs. No training table is created.

Task 1.5 adds [Jappe publisher-supplement acquisition and workbook inventory](docs/JAPPE_2020_SOURCE_INVENTORY.md):

```sh
PYTHONPATH=src python3 -B -m stability_label_curation jappe2020 fetch
PYTHONPATH=src python3 -B -m stability_label_curation jappe2020 inventory --json
```

Only four verified publisher links are allowlisted. Inventory is offline and
read-only; `--file ARTIFACT_ID=PATH` provides local overrides and `--reports-dir`
explicitly writes into a run with matching hashed inputs. Workbook rows and
transformed targets are not automatically measured-Tm observations.

Task 1.6 provides the [Jappe row-level field and assay-context audit](docs/JAPPE_2020_ROW_PROVENANCE.md):

```sh
PYTHONPATH=src python3 -B -m stability_label_curation jappe2020 audit --json
```

It verifies all four pinned input hashes and runs offline. `--reports-dir`
explicitly writes complete reports and a lossless audit ledger into an existing
run with matching hashed inputs. Tm, transformed values, predictions, auxiliary
cells, and paired C assay contexts remain distinct; training eligibility is not assigned.

Task 1.7 adds the [Jappe Figure Source Data audit](docs/JAPPE_2020_FIGURE_SOURCE_DATA.md):

```sh
PYTHONPATH=src python3 -B -m stability_label_curation jappe2020 figure-fetch
PYTHONPATH=src python3 -B -m stability_label_curation jappe2020 figure-audit --json
```

Acquisition permits only the official Source Data XLSX with a 5 MiB cap. Audit
is offline and read-only, reusing approved Task 1.6 evidence. The recovered workbook
covers Supplementary Figures 3–5; the complete Figure 2e HLA-C population remains
unavailable. Explicit `--reports-dir` publishes reports into a hashed-input run.

Task 1.8 provides the [canonical stability observation registry](docs/CANONICAL_STABILITY_OBSERVATION_REGISTRY.md):

```sh
PYTHONPATH=src python3 -B -m stability_label_curation registry validate --json
PYTHONPATH=src python3 -B -m stability_label_curation registry build --output-dir /absolute/project/run/reports
```

Validation is read-only and offline. Build requires an explicit hashed-input run.
The registry preserves 28,166 kinetic and 2,720 thermal measurement-value records;
27,031 SPEARMINT rows become lineage aliases, not additional observations.
Training eligibility and experimental independence remain unassessed.
