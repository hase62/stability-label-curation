# Stability-guided curation of human HLA-I immunogenicity training labels

Task 2.12 proposes a prospective **EL-positive loss-weighting A/B/P comparison**,
with original EL/IM labels preserved. Training approval remains pending; see
[the weighting protocol](docs/EL_POSITIVE_STABILITY_WEIGHTING_PROTOCOL.md).
This predictive-utility proposal does not establish EL mislabeling or detection reproducibility.

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

Task 1.9 prepares the [Gate 0 scientific decision dossier](docs/GATE0_SCIENTIFIC_DECISION_DOSSIER.md):

```sh
PYTHONPATH=src python3 -B -m stability_label_curation gate0 inspect --json
```

Inspection is offline and read-only from pinned Task 1.8 outputs. It quantifies
zero/construct alternatives and leakage evidence while every eligibility decision
remains pending. Explicit `--reports-dir` writes aggregate reports into an existing
hashed-input run; it creates no training tables, inclusion masks or split assignments.

## Phase 2: EL-to-IM protocol and leakage preflight

The [Task 2.0 EL-to-IM protocol](docs/PHASE2_EL_TO_IM_RESEARCH_PROTOCOL.md)
records the earlier EL-only intervention. The [Task 2.2 revision](docs/BIGMHC_V4_TRAINING_DATA_AUDIT.md)
now documents four future original/corrected EL × original/corrected IM training
conditions. Original experimental labels and independent test outcomes remain
preserved. The earlier protocol and Gate 0 dossier remain historical evidence.
[Hard-split evidence and threats](docs/HARD_SPLIT_METHODS_AND_LEAKAGE_THREATS.md)
distinguish publication descriptions, unresolved implementation details and
candidate diagnostics. No split, correction threshold or training is implemented.

```sh
PYTHONPATH=src python3 -B -m stability_label_curation leakage inspect --json
```

This command is offline and read-only. Explicit `--registry`/`--config` overrides
remain checksum-gated; `--reports-dir` writes only to an existing authorized run.

## BigMHC static source provenance

The [Task 2.1 audit](docs/BIGMHC_SOURCE_AND_CHECKPOINT_PROVENANCE.md) traces
commit-pinned EL sampling, IM transfer, HLA fallback and checkpoint inheritance.
Source snapshots stay outside Git; no data or weights are acquired by inspection.

```sh
PYTHONPATH=src python3 -B -m stability_label_curation bigmhc source-audit --json
```

The command is offline and read-only; explicit snapshot/evidence overrides remain
checksum-gated. Report output requires an existing authorized project run.

## BigMHC Version 4 training/validation audit

The [Task 2.2 data audit](docs/BIGMHC_V4_TRAINING_DATA_AUDIT.md) verifies the
official archive and separate receptor reference, inventories only authorized
train/validation files, and reports exact EL/IM/DTU overlap. Evaluation members
stay sealed. No labels, splits or models are generated.

```sh
PYTHONPATH=src python3 -B -m stability_label_curation bigmhc data-audit --json
```

This is offline and read-only; explicit `--reports-dir` requires an existing run
with every input recorded. `bigmhc fetch-data` and `bigmhc fetch-data --artifact
pseudoseqs.csv` are the two bounded, checksum-gated acquisition options. Inputs
remain outside Git; existing different bytes are never replaced.

## First kinetic Stability Teacher

[Teacher v0](docs/STABILITY_TEACHER_V0.md) is a per-allele Ridge pilot on ordinary
DTU HLA-A/B nine-mers, retaining reported zeros and fitting log1p half-life hours.
Its provisional internal split groups exact and one-mismatch peptides globally.
Training uses the small pinned CPU environment in
`configs/requirements-teacher-v0.txt`; other commands and JSON inference retain
standard-library-only operation.

```sh
PYTHONPATH=src python -B -m stability_label_curation teacher train --config configs/stability_teacher_v0.json --out <existing-run-directory>
```

The run must record configuration, seed and registry/evidence input hashes; see
the guide for creation, evaluation and inference. Model weights and split/metric
reports stay outside Git. Unsupported inputs get explicit null predictions.
Task 2.3 implements no EL/IM corrections or BigMHC training.

## Frozen-Teacher training pseudolabel candidates

[Task 2.4](docs/PSEUDOLABEL_PILOT_V0.md) streams only EL and IM training members,
scores supported nine-mers, and writes separate reversible candidate overrides.
The exploratory rules are positive→pseudo-0 below 1 hour and negative→pseudo-1
at or above 10 hours. Original labels stay unchanged; these are unvalidated
modeling candidates, not experimentally verified corrections.

```sh
PYTHONPATH=src python3 -B -m stability_label_curation pseudolabel pilot --config configs/pseudolabel_pilot_v0.json --out <existing-run-directory>
```

See the guide for hashed-input run creation and read-only `--verify-existing`
replay. No Teacher refit, validation/test inspection, final split or BigMHC
training occurs. Future override application requires explicit training-row
authorization under the subsequently established split protocol.

## Leakage-controlled four-condition pilot data

[Task 2.5 preparation](docs/BIGMHC_PILOT_PREPARATION.md) joins saved frozen-Teacher
scores to authenticated training rows, protects an IM development cohort by global
exact/one-substitution sequence separation, and writes identical-cohort original,
LOW-only and LOW+HIGH label views. Original labels and source-row lineage remain
available. No models are trained; extreme allele shifts require review.

```sh
PYTHONPATH=src python3 -B -m stability_label_curation pilot-prepare --config configs/bigmhc_pilot_v0.json --out <existing-hashed-input-run-directory>
```

Use `--verify-existing` for a read-only byte-identical replay. See the guide for
run creation, the A–D manifest and remaining training-environment requirements.

## Allele-specific stability diagnostic

[Task 2.6](docs/ALLELE_SPECIFIC_STABILITY_DIAGNOSTICS.md) compares frozen training
scores by HLA and original label, with descriptive training-set ROC-AUC and saved
DTU validation context. **Historical LOW/HIGH corrected views are scientifically
unapproved for BigMHC training.** No replacement strategy or cutoff is selected.

```sh
PYTHONPATH=src python3 -B -m stability_label_curation allele-diagnostics
```

Inspection is read-only. An explicit `--out <existing-hashed-input-run>` writes
aggregate reports; `--verify-existing` performs read-only deterministic replay.

## Original-label BigMHC runtime smoke

[Task 2.7](docs/BIGMHC_BASELINE_RUNTIME.md) runs the pinned authentic BigMHC
architecture on fixed small **original-label-only** EL and IM subsets, using a
bounded isolated CPU worker. It saves/reloads the full EL checkpoint and IM
overlay, then predicts the frozen development cohort. This is an engineering
smoke, not scientific baseline performance; corrected views remain unapproved.

```sh
PYTHONPATH=src <isolated-runtime-python> -B -m stability_label_curation bigmhc-smoke --config configs/bigmhc_baseline_smoke_v0.json --out <existing-hashed-input-run>
```

See the guide for environment versions, seed42, run creation, checkpoint-parent
layout and resource bounds. No published checkpoints or sealed tests are used.

For the portable single-GPU execution worker, see
[BigMHC WSL2 worker handoff](docs/BIGMHC_GPU_WORKER.md). Verify the 21 pinned
external inputs with `PYTHONPATH=src python3 -m stability_label_curation bigmhc-worker verify-inputs --json`.
The CUDA configuration preserves the original-label Task 2.7 smoke; remote
installation, transfer and GPU validation are separate execution steps.

Task 2.11 examines [low-stability EL positives and repeat-detection evidence](docs/EL_POSITIVE_STABILITY_HYPOTHESIS.md).
`PYTHONPATH=src python3 -m stability_label_curation el-positive-analysis --json` is read-only.
It uses original EL positives first, preserves labels, and selects no curation rule.
