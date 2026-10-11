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

Requires Python 3.11 or later; no dependency installation is needed for these source-layout checks:

```sh
PYTHONPATH=src python3 -B -c "import stability_label_curation; print(stability_label_curation.__file__)"
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
```
