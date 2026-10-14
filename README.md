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
