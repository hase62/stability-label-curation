# HLA EL20→IM30 reproducibility

This entry point implements the raw-input path for the November 18 submission closeout. It uses a clean checkout of this commit, version-pinned upstream bytes, and a new output directory. The historical run is evidence for expected hashes and dimensions. It is unnecessary at runtime. Scientific operations were excluded from the November 19 implementation audit.

## Storage, environment and sources

Use Linux or WSL2 x86-64, Python 3.13.5 for scientific stages, one NVIDIA GPU for native training/inference, and explicit external project data/runs roots as resolved by `stability_label_curation.paths`. The native baseline was Windows WSL2, RTX 4090, CUDA 13.0, cuDNN 92000 and FP32 with TF32/AMP disabled. Tooling and SHA checks need Python ≥3.11. The recorded training environment is in `configs/hla_reproduction/requirements-gpu.txt`, including PyTorch 2.13.0+cu130 and its dependencies. A compatible CUDA wheel source and NVIDIA driver must be supplied by the operator. The recipe checks installed versions before a scientific stage and never installs packages or changes CUDA or drivers. CPU teacher and metric stages use NumPy 2.2.6, SciPy 1.15.3 and sklearn 1.6.1. Rendering uses Matplotlib 3.10.1 and its separate lock. Mix has a separate environment and uses bash and the pinned release's dependencies. Supply MAFFT if required by the upstream model.

Read `configs/hla_reproduction/sources.json` for access steps, versions, SHA256 and rights, and `official_bigmhc_files.json` for per-file BigMHC hashes. Store the original files under the project data directory. For Mendeley BigMHC v4, download `datasets.zip` from DOI `10.17632/dvmz6pkzvb.4` and place it unchanged at the manifest path. Direct, version-pinned sources may be downloaded by the explicit `acquire` command. There is no implicit network access. A researcher may place a verified licensed or access-controlled original under the data root and supply `--asset ROLE=/absolute/path` during `verify-assets`. The BigMHC upstream Academic License and the conditions for third-party datasets/weights apply. Unknown redistribution rights remain unknown. The repository contains artifact fingerprints and code, with research inputs and outputs stored outside Git.

## Verify-only entry

```bash
python3 scripts/hla_reproduction/run.py plan
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_hla_reproduction.py' -v
```

The plan prints the stage input/output contract and historical comparison sizes without opening data or launching workers. Tests use synthetic data. Initialization requires a clean checkout and authenticates 20 native scientific files against the run seal. It also checks the 18-fit order and endpoint budgets against the saved experiment contract.

## Authorized future execution

Run from the repository root at the committed revision. Use a fresh directory directly under the configured project runs directory, e.g. `$HOME/codex/runs/stability-label-curation/reproduction-001` when the default roots apply. Replace the interpreter variables with the Python paths of independently installed, locked environments. Commands are shown for a subsequently authorized scientific run.

```bash
entry=scripts/hla_reproduction/run.py
run="$HOME/codex/runs/stability-label-curation/reproduction-001"

python3 "$entry" init --run "$run"
python3 "$entry" acquire --role dtu --role improve --role improve_crosscheck --role bigmhc_code
# Place the BigMHC v4 datasets.zip from Mendeley in the configured data directory.
python3 "$entry" verify-assets --run "$run"

"$cpu_python" "$entry" teacher --run "$run"
"$cpu_python" "$entry" prepare --run "$run"
"$cpu_python" "$entry" cohorts --run "$run"
"$cpu_python" "$entry" controls --run "$run"

export CUDA_VISIBLE_DEVICES=0
"$gpu_python" "$entry" seal --run "$run"
"$gpu_python" "$entry" train --run "$run"
"$gpu_python" "$entry" infer --run "$run"

# Optional official and Mix appendix diagnostics are described below.
"$cpu_python" "$entry" evaluate --run "$run"
"$cpu_python" "$entry" qa --run "$run"
"$cpu_python" "$entry" supplement --run "$run"
"$render_python" "$entry" figures --run "$run"
```

The acquired assets are read-only in scientific stages. Initialization, stage output, logs and status are confined to the new run. The fit command holds one local supervisor lock and invokes one worker at a time. Each seed's A is first. A started or failed incomplete fit stops the queue with the saved attempt and epoch-state receipts. A failed fit is never started automatically from a weights-only restart. At seal time the only fit-active data are cohort-independent training inputs, generated weight controls, and authenticated upstream encoder/source code. Training workers refuse access to cohort identities, outcomes and prediction files. Inference is a separate process and reads only cohort identities. The evaluation credential-free receipt is produced after verifying the 72 new prediction files.

The native model, sampling, optimizer behavior, epoch budgets, checkpoint selection, score orientation, paired comparisons and bootstrap unit/seed are preserved. `configs/hla_reproduction/02_EXPERIMENT_CONTRACT.json` and `EXECUTION_CONFIG.json` are evidence copies; the new runtime uses `native_runtime.json`. The historical `c52a4b05…` contains the preceding EL10→IM20 wrapper and native functions. The EL20→IM30 recipe uses those functions through the new wrappers and trains every trajectory fresh.

### Optional appendix routes

- **Official BigMHC**. Before `evaluate`, acquire `--role bigmhc_code --with-official-weights` and run `verify-assets --run "$run" --with-official-weights`. Run `"$gpu_python" "$entry" official --run "$run"`. This adds pinned official EL/IM ensemble inference, which the main evaluator tabulates if those predictions exist. Run `official-exposure` to reproduce the published-data exposure table from the BigMHC v4 archive. It keeps train, validation and test separate. Per-weight training membership remains incompletely documented.
- **MixMHCpred v3.0**. Acquire and verify `--role mix` and use the audited package versions in `requirements-mix.txt`, then run `"$mix_python" "$entry" mix --run "$run"`. It predicts exact designated-HLA scores from the original archive and applies rank metrics that permit finite native scores outside [0,1]. Its table retains the historical filename `MIX_SAVED_REFERENCE_DIAGNOSTIC.csv`; the input scores are newly generated in this run. The main analysis has no dependency on Mix or the Task 2.40 score artifact.
- **Teacher sensitivity**. After `teacher`, run `"$cpu_python" "$entry" teacher-sensitivity --run "$run"` to produce the supplementary zero-handling table using the same DTU split. This stage never replaces the main zero-retaining Teacher.
- **Historical figures S9 and S10**. These use the separately run Task 2.37 measured-Tm and Task 2.41-B hard-filter experiments. Their source trees, inputs and result lineage are listed in `configs/hla_reproduction/output_lineage.csv`. Their old aggregate files are no part of this pipeline. An independent raw-to-figure path for those analyses and the editorial graphical TOC are outside the main entry point.

## Known identities and limitations

`expected.json` pins compact cohort outputs, decoded training/weight CSVs, the Teacher partition, and expected stage dimensions. Strict identity gates stop on differing source rows, labels, weights, cohort identity, or split. The Teacher is refitted from DTU records using the original code and split. Its newly serialized provenance differs from the older manifest. Scientific continuity is checked by the original partition plus exact decoded per-row EL rank/weight ledger; the legacy model JSON SHA remains comparison evidence. The original fitting environment was macOS ARM64, whereas this CPU recipe can run on WSL2 x86-64. Exact rank continuity from the re-fit has not yet been demonstrated in this recipe. Historic GPU/table hashes are for post-run comparison. Exact final numeric outputs have not yet been independently produced from a clean checkout.

Expected sizes include EL 1,308,196 fit and 145,371 validation; IM 3,428 fit; Neo 267 rows, 57 positive, 265 components; IMPROVE 7,788 rows, 227 positive, 38 components; original Teacher train/validation 21,625/5,406 with 67 fitted HLA; 63,053 EL-positive rows and 49 HLA rank groups; 18 trajectories, 900 epochs, 72 prediction files and 289,980 prediction rows. The evaluator produces the paired AP/AUROC and 10,000-draw intervals, the sensitivity endpoint and aggregate tables. The render stage emits ten PDFs and matched source CSVs, plus the two submission-styled AP panels under `figures/manuscript`. Private row files and bootstrap draws stay in the local run.
