# Task 2.7: original-label BigMHC EL-to-IM CPU smoke

This is condition A only: **original EL → original IM**. It is an engineering
smoke run, not a meaningful baseline benchmark or evidence for/against stability
correction. Historical LOW-only/LOW+HIGH views remain scientifically unapproved
and are neither opened nor trained. No Teacher fitting, scoring, new correction,
external-test inspection, multiple-seed study or full-data training is performed.

## Authentic source and runtime

The runner verifies all ten previously acquired BigMHC source files at commit
`199e890fa69a63646730bcecea0a520e08ca4f02`. It executes the authenticated original
`bigmhc.py`, `dataset.py`, `encseq.py` and `mhcuid.py` without changing their bytes.
The other six files are integrity checked. External source is not redistributed
in this repository; the original Academic License remains in its snapshot.

`BigMHC()` is constructed with **unchanged defaults**: mhclen=414, minpep=8,
enclen=20, hidlen=1024, layers=2. It has 87,444,881 parameters and 36 saved state
tensors. No smaller substitute network is used. The same architecture is used for
EL and IM. There are no downloaded weights or production ensembles.

An isolated environment lives under the resolver's project data directory:
`environments/bigmhc-smoke-v0-py313`. The actual host uses Python 3.13.5 on macOS
arm64, PyTorch 2.14.1, NumPy 2.5.4, pandas 3.0.6 and psutil 7.2.2.
[The frozen dependency list](../configs/requirements-bigmhc-smoke-v0.txt) records
all installed package versions; the run also captures installed versions and
hardware. These are compatible present-host packages, not a reconstruction of
the original 2023 training environment. PyTorch provides a
[macOS pip installation path](https://pytorch.org/get-started/locally/).
Only necessary runtime packages and their dependencies are installed: no
TorchVision, TorchAudio, CUDA stack, checkpoint or additional scientific dataset.
The existing Teacher/test environment remains separate and unchanged.

## Input authenticity and deterministic subsets

[bigmhc_baseline_smoke_v0.json](../configs/bigmhc_baseline_smoke_v0.json) pins 21
inputs: ten external source files, three original-label CSVs, their three
coordinate-provenance ledgers, the verified 414-feature receptor reference, and
four parent manifest/receipt/inventory files. All actual input bytes are checked
before and after execution. Parent artifact checksums authenticate the original
EL/IM/development views; corrected filenames, correction policies and non-A
conditions are rejected. No original BigMHC ZIP payload is opened.

The source populations are the Task 2.5 original views: 1,453,578 EL rows and
3,428 IM rows. The frozen development cohort is 383 rows, 120 original positives
and 263 negatives, across 31 HLA identifiers. Development labels are retained
for traceability and population verification; no outcome is used for selection,
configuration or threshold choice.

Selection is a one-pass uniform reservoir sample separately within each **original
training label**, using a local `random.Random(42)`, then sorted by prepared-view
row index. The fixed engineering subset is 128 positive +128 negative EL rows
and 64 positive +64 negative IM rows. This deliberately balanced debug sample is
not a prevalence-preserving scientific cohort. Its size bounds CPU work for the
large authentic network. No validation result or Teacher score affects selection.

Only after the chosen row identities are fixed, the original-coordinate fields
of Task 2.5 provenance ledgers are joined. Historical prediction/proposed-label
fields in these ledgers are unused. The subset manifest retains prepared row
index, source-view SHA256, publisher row identity/coordinates, original HLA,
peptide and original label. No source row or label is overwritten.

Every selected sequence is checked against the complete frozen development
cohort using all canonical single substitutions plus exact identity, globally
across HLA identifiers. No prohibited match is allowed. This establishes only
the provisional sequence rule; donor/study independence remains unverified.

## Minimal runtime adaptations and unchanged training semantics

The runner bypasses stock CLI initialization/DataLoader construction and otherwise
uses the pinned architecture, CSV reader, encodings, native batching and saves.

| Adaptation | Reason |
| --- | --- |
| Python, NumPy and Torch seed 42; deterministic CPU algorithms | Stock CLI hardcodes seed1; one declared reproducible smoke seed is required |
| Four CPU intra-op threads, one inter-op thread; explicit CPU tensors | Bound resources and avoid device autodetection |
| DataLoader `num_workers=0`, `persistent_workers=False` | Avoid uncontrolled multiprocessing and stale worker replicas; no prefetch worker state |
| Strict dictionary receptor lookup after unique-reference/HLA validation | Prevent `MHCEncoder` nearest-allele fallback; retain authentic 414 binary features |
| Per-process forced weights-only Tensor loading | Reload only locally generated authenticated tensor checkpoints; no arbitrary model-object pickle |
| Separate bounded supervisor process | Enforce 600-second wall budget and 6 GiB worker RSS cap; terminate only its own worker on violation |

EL uses the native `Dataset.makebats(maxbat=8, shuffle=True, negfrac=0.99)`.
IM uses native ordinary length-group batching with `negfrac=None`. There is one
epoch each. Loss is `BCEWithLogitsLoss`, optimizer is `AdamW(lr=5e-5)` with
installed-version defaults recorded. No sampler redesign or step equalization
is introduced. The balanced EL debug subset emits eight-row native batches.

IM updates only `condenser.att.{weight,bias}` and
`condenser.out.{weight,bias}`. The encoder weights remain outside the optimizer;
the full model is still in training mode, including dropout, matching the source.
Nonoptimized encoder gradients are not redefined as frozen evaluation features.
All-negative IM batches are skipped as in the source, and are counted. Reports
distinguish planned batches, actual optimizer steps, consumed rows, row-weighted
BCE and the source-style epoch-loss denominator. Equal epochs do not guarantee
equal exposure; this task does not solve that deferred design question.

## Checkpoint inheritance and inference

```text
checkpoints/
  el/                 # 36 full EL .lyr tensor files
    im/               # four IM .lyr overlay tensor files
```

Each directory is exclusively reserved; an existing checkpoint cannot be silently
overwritten. Saves use authentic `BigMHC.save`. An interrupted save is not a
completed smoke run: require the final successful execution receipt.

Authentic `BigMHC.load` reloads EL, then reconstructs IM from its immediate EL
parent and four-file overlay. The lineage report hashes every checkpoint tensor,
records all state keys and initial/EL/IM tensor identities, verifies that only
allowed IM tensors changed, and checks that EL files remain unchanged. Full
model state and all development predictions must match exactly before/after
reload. No published model or external checkpoint is loaded.

EL and IM each produce sigmoid probabilities for all 383 development observations
in original prepared order. CSVs retain the original source row ID, original HLA,
resolved HLA, peptide and unchanged original label. No AUROC/AUPRC is calculated:
the engineering check is finite prediction coverage and exact reload agreement,
not performance selection. This tiny-debug model cannot certify baseline quality,
final independent generalization or a correction benefit.

## Canonical artifacts and execution

A single canonical run records the committed wrapper, configuration, all hashed
inputs and seed42. Outputs include subset manifests/CSVs, leakage verification,
environment/version record, both checkpoints, lineage, training step/loss logs,
EL/IM development predictions, resource observations and execution verification.
All belong under project run storage and stay outside Git.

From the checkout, use the isolated runtime's Python (resolved portably below):

```python
from stability_label_curation.paths import resolve_paths
from stability_label_curation import bigmhc_baseline_runner as baseline, run_manifest
import subprocess

paths = resolve_paths()
config_path = paths.repository_root / baseline.CONFIG
config = baseline.load_config(config_path)
_, inputs = baseline.resolve_inputs(config, paths)
run = run_manifest.create_run(
    paths=paths, run_id="task-2_7-bigmhc-baseline-smoke", kind="bigmhc_baseline_smoke",
    seed=42, config=config_path, inputs=[item["path"] for item in inputs],
    argv=["Task 2.7 canonical original-label smoke"],
)
python = paths.project_data_dir / "environments/bigmhc-smoke-v0-py313/bin/python"
subprocess.run([str(python), "-B", "-m", "stability_label_curation", "bigmhc-smoke",
                "--config", str(config_path), "--out", str(run)], check=True)
```

Set `PYTHONPATH=src` when invoking from the checkout. `--input INPUT_ID=PATH`
permits explicitly pinned local fixtures. Runtime imports are lazy: ordinary CLI
and normal unit tests do not require Torch or run expensive NN optimization.
The supervisor owns the sole heavy worker; its wall/RSS report records success
or the exact blocker. Its `--worker` entry is internal, not the normal user path.

Reproduction means identical selected rows and checkpoint-reload predictions in
the recorded runtime. This task does not promise byte-identical serialized Torch
files or rerun a second training experiment. Input/output hashes and a reload
verification establish the executed artifacts, not portability of learned weights
across arbitrary PyTorch/hardware versions.

## Before full-data or A–D training

A successful smoke removes the basic architecture/loader/transfer/save/inference
engineering blocker. Full-data training still requires an explicit compute and
training budget, environment validation on the target hardware, initialization
and parent-checkpoint bookkeeping, logging of native sampler omissions/skips,
and a separately approved scientific evaluation protocol. macOS CPU execution
provides no WSL2/GPU validation.

The historical absolute correction rule remains scientifically unapproved.
Before B/C/D, scientific review must justify an EL/IM correction strategy,
calibration/reference population, uncertainty handling and controls. No decision
or implementation of those choices occurs here. Stop after Task 2.7.
