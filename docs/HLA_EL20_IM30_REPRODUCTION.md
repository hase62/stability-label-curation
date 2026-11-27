# HLA EL20→IM30 reproducibility

For a lightweight reproduction using the fixed manuscript aggregates, see the
[published figure command](../README.md#render-the-published-figures-on-cpu)
and the [source data index](../manuscript/source_data/index.tsv).


This entry point implements the raw-input path for the November 18 submission closeout. It uses a clean checkout of this commit, version-pinned upstream bytes, and a new output directory. The historical run is evidence for expected hashes and dimensions. It is unnecessary at runtime. Scientific operations were excluded from the November 19 implementation audit.

## Storage, environment and sources

Use Linux or WSL2 x86-64, Python 3.13.5 for scientific stages, one NVIDIA GPU for native training/inference, and explicit external project data/runs roots as resolved by `stability_label_curation.paths`. The native baseline was Windows WSL2, RTX 4090, CUDA 13.0, cuDNN 92000 and FP32 with TF32/AMP disabled. Tooling and SHA checks need Python ≥3.11. The recorded training environment is in `configs/hla_reproduction/requirements-gpu.txt`, including PyTorch 2.13.0+cu130 and its dependencies. A compatible CUDA wheel source and NVIDIA driver must be supplied by the operator. The recipe checks installed versions before a scientific stage and never installs packages or changes CUDA or drivers. CPU Teacher and metric stages use NumPy 2.2.6, SciPy 1.15.3 and sklearn 1.6.1. The original Teacher pins joblib 1.5.1 and threadpoolctl 3.6.0 in `requirements-teacher.txt`. On Linux x86-64 (including WSL2), use the numerical refit and metric environment in `requirements-cpu.txt` (joblib 1.6.0 and threadpoolctl 3.8.0). The November 8 refit audit in that environment matched all 63,053 downstream ranks and weights exactly, while the refitted coefficients differed from the Mac original at floating-point precision. The new recipe still stops if its entire decoded weight ledger does not match. Rendering uses Matplotlib 3.10.1 and its separate lock. Mix has a separate environment and uses bash and the pinned release's dependencies. Supply MAFFT if required by the upstream model.

Read `configs/hla_reproduction/sources.json` for access steps, versions, SHA256 and rights, and `official_bigmhc_files.json` for per-file BigMHC hashes. Store the original files under the project data directory. For Mendeley BigMHC v4, download `datasets.zip` from DOI `10.17632/dvmz6pkzvb.4` and place it unchanged at the manifest path. Direct, version-pinned sources may be downloaded by the explicit `acquire` command. There is no implicit network access. A researcher may place a verified licensed or access-controlled original under the data root and supply `--asset ROLE=/absolute/path` during `verify-assets`. The BigMHC upstream Academic License and the conditions for third-party datasets/weights apply. Unknown redistribution rights remain unknown. The repository contains artifact fingerprints and code, with research inputs and outputs stored outside Git.

## Build the environments

Use [CPython 3.13.5](https://www.python.org/downloads/release/python-3135/) with a recent `pip`. The device-specific environments below are separate. Keep them outside the source checkout alongside the project storage. Build these once, before starting a future authorized run.

```bash
env_dir="$HOME/hla-el20-im30-envs"
locks=configs/hla_reproduction
python3.13 --version                         # must report 3.13.5
for role in cpu gpu render mix; do
  python3.13 -m venv "$env_dir/$role"
done
for role in cpu render mix; do
  "$env_dir/$role/bin/python" -m pip install --only-binary=:all: \
      --index-url https://pypi.org/simple -r "$locks/requirements-$role.txt"
done
"$env_dir/gpu/bin/python" -m pip install --only-binary=:all: \
    --index-url https://pypi.org/simple \
    --extra-index-url https://download.pytorch.org/whl/cu130 \
    -r "$locks/requirements-gpu.txt"
cpu_python="$env_dir/cpu/bin/python"
teacher_python="$cpu_python"                 # Linux x86-64 numerical refit
gpu_python="$env_dir/gpu/bin/python"
render_python="$env_dir/render/bin/python"
mix_python="$env_dir/mix/bin/python"
```

The CUDA wheel uses the [PyTorch CUDA 13.0 index](https://download.pytorch.org/whl/cu130/torch/) and the CPython 3.13 Linux x86-64 tag. A compatible NVIDIA driver, glibc ≥2.28, adequate GPU memory and run disk space are required. Linux x86-64 was the observed GPU runtime. For the separate original-platform Teacher option, create a Python 3.13.5 macOS ARM64 environment using `requirements-teacher.txt`, and run the Teacher stage in that environment with the same source revision and project artifact bindings. The worksheet parser and IMPROVE distance search use the standard library. Mix inference uses bash and the pinned Python dependencies. The upstream [MAFFT program](https://mafft.cbrc.jp/alignment/software/) is required for the Mix sequence-alignment mode, which this allele-list diagnostic does not invoke.

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

"$teacher_python" "$entry" teacher --run "$run"
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

The `prepare` stage includes the exact HLA lookup. After `evaluate`, `supplement` regenerates Tables S10–S12 from this run's metrics, prediction receipts, and regenerated cohorts. The [output map](../configs/hla_reproduction/output_lineage.csv) lists the resulting CSVs. Keep these outputs in the run directory.

The acquired assets are read-only in scientific stages. Initialization, stage output, logs and status are confined to the new run. The fit command holds one local supervisor lock and invokes one worker at a time. Each seed's A is first. A started or failed incomplete fit stops the queue with the saved attempt and epoch-state receipts. A failed fit is never started automatically from a weights-only restart. At seal time the only fit-active data are cohort-independent training inputs, generated weight controls, and authenticated upstream encoder/source code. Training workers refuse access to cohort identities, outcomes and prediction files. Inference is a separate process and reads only cohort identities. The evaluation credential-free receipt is produced after verifying the 72 new prediction files.

The native model, sampling, optimizer behavior, epoch budgets, checkpoint selection, score orientation, paired comparisons and bootstrap unit/seed are preserved. `configs/hla_reproduction/02_EXPERIMENT_CONTRACT.json` and `EXECUTION_CONFIG.json` are evidence copies; the new runtime uses `native_runtime.json`. The historical `c52a4b05…` contains the preceding EL10→IM20 wrapper and native functions. The EL20→IM30 recipe uses those functions through the new wrappers and trains every trajectory fresh.

### Optional appendix routes

- **Official BigMHC**. Before `evaluate`, acquire `--role bigmhc_code --with-official-weights` and run `verify-assets --run "$run" --with-official-weights`. Run `"$gpu_python" "$entry" official --run "$run"`. This adds pinned official EL/IM ensemble inference, which the main evaluator tabulates if those predictions exist. Run `official-exposure` to reproduce the published-data exposure table from the BigMHC v4 archive. It keeps train, validation and test separate. Per-weight training membership remains incompletely documented.
- **MixMHCpred v3.0**. Acquire and verify `--role mix` and use the audited package versions in `requirements-mix.txt`, then run `"$mix_python" "$entry" mix-score --run "$run"` and `"$cpu_python" "$entry" mix-evaluate --run "$run"`. The scoring worker predicts exact designated-HLA scores from the original archive. The separate metric worker applies rank metrics that permit finite native scores outside [0,1]. Its table retains the historical filename `MIX_SAVED_REFERENCE_DIAGNOSTIC.csv`; the input scores are newly generated in this run. The main analysis has no dependency on Mix or the Task 2.40 score artifact.
- **Teacher sensitivity**. After `teacher`, run `"$cpu_python" "$entry" teacher-sensitivity --run "$run"` to produce the supplementary zero-handling table using the same DTU split. This stage never replaces the main zero-retaining Teacher.
- **Historical figures S9 and S10** have independent subcommands described below. The editorial Graphical TOC layout is outside the pipeline. Its numerical input is generated by `figures` as `figures/Graphical_TOC_Source.csv` from IM30 A AUROC and W_two vs W_two_perm ΔAP and interval for both cohorts.

### Historical supplements from raw sources

Use the same sealed fresh run. Both analyses use a newly trained unweighted Task 2.23 seed-42 EL10 ancestor. That ancestor neither uses the official BigMHC weights nor requires the EL20→IM30 trained models. The S9/S10 work directories and checkpoints remain inside this run. This route replaces the dependencies on the Task 2.23 checkpoint, Task 2.31 rank files, Task 2.35 candidate/decoy files and old score vectors.

```bash
python3 "$entry" acquire --role jappe_a02 --role jappe_b07
python3 "$entry" verify-assets --run "$run"
"$gpu_python" "$entry" historical-el10 --run "$run"

"$cpu_python" "$entry" s9-prepare --run "$run"
"$gpu_python" "$entry" s9-fit --run "$run"
"$gpu_python" "$entry" s9-infer --run "$run"
"$cpu_python" "$entry" s9-evaluate --run "$run"
"$render_python" "$entry" s9-figure --run "$run"

"$cpu_python" "$entry" s10-prepare --run "$run"
"$gpu_python" "$entry" s10-fit --run "$run"
"$gpu_python" "$entry" s10-infer --run "$run"
"$cpu_python" "$entry" s10-evaluate --run "$run"
"$render_python" "$entry" s10-figure --run "$run"
```

S9 uses the original journal workbooks from DOI 10.1038/s41467-020-20166-4. Supplementary Data 3 supplies A*02:01 measured Tm in Celsius. Supplementary Data 4 supplies B*07:02 sequences only for the exact measured-ligand veto on decoys. It is not an adaptation source. The EL-positive veto covers the original prepared EL population including the 11 rows excluded by the Task 2.23 split. Both external cohorts contribute the original label-free Hamming ≤2 exclusion. The existing Task 2.35 transform, source-identity and Task 2.37 balanced loss, permutation, 20-pass order and output-only adaptation are reused. The pinned decoy pair/order digest checks the 11,360 selected negatives. Outcome files are opened only after all 20 predictions freeze. Outputs are `metrics/S_Thermal_Transfer_9.csv` and `figures/Figure_S9_Measured_Tm_Transfer.pdf`, including 9 fixed contrasts across A*02:01 IMPROVE, full IMPROVE and Neo.

S10 regenerates bottom-10% HLA-specific removal from the checked Task 2.31-equivalent ranks. It uses the Task 2.41-B fixed seeds and the same HLA × length removal quotas for R1–R5, retaining the original A train/validation populations and labels. A, H and all five matched random removals each use 10 EL epochs, seed 42 and unweighted native BCE. The original paired 10,000-draw component bootstrap outputs H−A and H−mean(R1–R5), where the latter averages five AP values. Outputs are `metrics/S_LowStability_Removal_7_Arms.csv`, `metrics/Historical_Deletion_Contrasts.csv` and `figures/Figure_S10_Hard_Filtering.pdf`. Only the newly generated tables feed the supplement renderers.

## Known identities and limitations

`expected.json` pins compact cohort outputs, decoded training/weight CSVs, the Teacher partition, and expected stage dimensions. Strict identity gates stop on differing source rows, labels, weights, cohort identity, or split. The Teacher is refitted from DTU records using the original code and split. Its newly serialized provenance differs from the older manifest. Scientific continuity is checked by the original partition plus exact decoded per-row EL rank/weight ledger; the legacy model JSON SHA remains comparison evidence. The original fitting environment was macOS ARM64, whereas this CPU recipe can run on WSL2 x86-64. The prior WSL2 audit established rank continuity on the original rows. The new raw-input entry point has not re-executed that audit. Historic GPU/table hashes are for post-run comparison. Exact final numeric outputs have not yet been independently produced from a clean checkout.

Expected sizes include EL 1,308,196 fit and 145,371 validation; IM 3,428 fit; Neo 267 rows, 57 positive, 265 components; IMPROVE 7,788 rows, 227 positive, 38 components; original Teacher train/validation 21,625/5,406 with 67 fitted HLA; 63,053 EL-positive rows and 49 HLA rank groups; 18 trajectories, 900 epochs, 72 prediction files and 289,980 prediction rows. The evaluator produces the paired AP/AUROC and 10,000-draw intervals, the sensitivity endpoint and aggregate tables. The render stage emits ten PDFs and matched source CSVs, plus the two submission-styled AP panels under `figures/manuscript`. Private row files and bootstrap draws stay in the local run.
