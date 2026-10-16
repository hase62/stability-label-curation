# BigMHC single-GPU worker handoff

Mac owns development, scientific auditing, configurations and analysis. WSL2 is
an execution worker. This task prepares code and verifies local inputs; it does
not install remote software, transfer data or validate CUDA hardware. The
interrupted CPU scale-up worktree is separate and must remain untouched.

The worker uses condition A only: **original EL → original IM**, with pinned
BigMHC source `199e890fa69a63646730bcecea0a520e08ca4f02`. Historical LOW/HIGH
corrections remain scientifically unapproved. No corrected CSV, override, sealed
evaluation payload, Teacher artifact or published checkpoint is needed.

## Code and input handoff

After review, publish the approved worker commit through the normal Git workflow.
On WSL2, fetch and check out that same full commit in
`~/codex/repos/stability-label-curation`, with a clean tree. The new worker branch
is deliberately not pushed by this task; current GitHub main alone cannot run
these new commands yet. No Codex installation on WSL2 is required.

[The transfer manifest](../configs/bigmhc_gpu_worker_transfer.json) lists every
external input with its original relative path, size and exact locally verified
SHA256: **21 files, 207,979,774 bytes**. `area=data` resolves below
`~/codex/data/stability-label-curation`; `area=runs` resolves below
`~/codex/runs/stability-label-curation`. The existing path resolver also honors
`CODEX_ROOT`, `CODEX_DATA_ROOT` and `CODEX_RUNS_ROOT`. No username is embedded.

| Input group | Files |
| --- | ---: |
| Original EL/IM training views and frozen development CSV | 3 |
| Original-coordinate provenance ledgers | 3 |
| Task 2.5 manifest, receipt, training inventory, experiment manifest | 4 |
| BigMHC pseudosequence reference | 1 |
| Authenticated BigMHC source/license/README files | 10 |

Transfer only those files later, preserving relative paths. Do not copy the whole
Task 2.5 directory: it also contains unapproved corrected views. Parent manifests
may describe historical conditions; the worker authenticates those documents
without opening the corresponding corrected payloads. Their historical Mac paths
remain evidence and need not be rewritten. The fresh run records actual WSL paths.
Git-managed configurations and this manifest arrive with the approved checkout.
No original BigMHC ZIP, source Git clone or Task 2.7 checkpoint is required.

Receiving-system verification is read-only and needs only Python 3.11+:

```bash
cd ~/codex/repos/stability-label-curation
PYTHONPATH=src python3 -B -m stability_label_curation bigmhc-worker verify-inputs --json
```

This checks the exact configuration/manifest allowlist, every size/SHA256 and the
parent records authenticating original-label views. Missing/changed files,
symlinks, path traversal and unapproved or sealed inputs fail verification.

## WSL2 environment check

Use an isolated Linux environment outside Git with compatible PyTorch, NumPy,
pandas and psutil. Select the PyTorch build only after checking the installed
Windows NVIDIA driver and its WSL support; use the
[official installation selector](https://pytorch.org/get-started/locally/).
The Mac requirements freeze documents the Mac smoke environment and is not a
Linux CUDA installation lock. This task performs no installations.

With the intended environment activated, inspect both physical GPUs:

```bash
nvidia-smi --query-gpu=index,name,driver_version,memory.total --format=csv
python - <<'PY'
import sys, torch, numpy, pandas, psutil
print(sys.version)
print('packages:', torch.__version__, numpy.__version__, pandas.__version__, psutil.__version__)
print('CUDA available:', torch.cuda.is_available(), 'PyTorch CUDA runtime:', torch.version.cuda)
print('visible GPUs:', torch.cuda.device_count())
for index in range(torch.cuda.device_count()):
    print(index, torch.cuda.get_device_name(index))
PY
```

Confirm the two RTX 4090 devices before launching. A missing CUDA-enabled build,
driver incompatibility or unavailable GPU is a blocker, never a reason for an
automatic CPU fallback. Do not configure networking or credentials through this
runner.

## First CUDA smoke

[bigmhc_gpu_worker_v0.json](../configs/bigmhc_gpu_worker_v0.json) reproduces Task
2.7 selection: seed 42, 128 original positives +128 negatives EL, 64 +64 IM,
one epoch each, batch size eight, the same 383-row development cohort (120
positives/263 negatives/31 HLAs). Original-label stratified reservoir sampling
and all exact/one-substitution separation checks remain unchanged. No outcome or
Teacher score influences selection. The smoke subset is deliberately balanced
and is not a scientific full-data baseline.

Select **one** physical GPU before starting. To use GPU 0:

```bash
PYTHONPATH=src CUDA_VISIBLE_DEVICES=0 python -B -m stability_label_curation bigmhc-worker run \
  --config configs/bigmhc_gpu_worker_v0.json --run-id task-2_8-wsl2-bigmhc-smoke
```

Use `CUDA_VISIBLE_DEVICES=1` instead for GPU 1. Both choices become logical
`cuda:0` inside the process. An unset/multiple-device selection is rejected;
there is no distributed or multi-GPU code. Run only one smoke initially.
The run ID is exclusive and cannot overwrite an existing run.

The existing `bigmhc-smoke` command remains available; CPU remains its default
through the approved CPU configuration. The worker profile allows later explicit
configuration changes to `rows_per_class`, batch size and wall/RSS budgets, without
changing eligibility or sampling rules. It retains balanced per-class sampling;
using all IM rows at their original prevalence would require a separately reviewed
extension. Its guardrails cap EL at 100,000 per class, IM at 1,714 per class,
wall time at 1,800 seconds and worker RSS at 8 GiB. The supplied first-run config
keeps the original 600-second/6-GiB bounds and small row counts. No scale-up run
is authorized here.

## Preserved semantics and portable checkpoints

Architecture defaults, BCE-with-logits, AdamW, native batching/EL `negfrac=0.99`,
IM all-negative-batch skipping and the four transfer parameters are unchanged.
Model, features and targets move to the selected device; outputs return to CPU
for reporting. Strict authenticated receptor lookup prevents fuzzy HLA fallback.
DataLoader workers remain zero, with no persistent workers. CUDA seed 42,
deterministic algorithms, cuDNN settings, disabled TF32 and pre-initialization
`CUBLAS_WORKSPACE_CONFIG=:4096:8` are recorded adaptations. Unsupported
deterministic CUDA operations fail explicitly. See
[PyTorch reproducibility guidance](https://docs.pytorch.org/docs/2.14/notes/randomness.html).

Native saves retain 36 EL tensor files under `checkpoints/el` and four IM overlay
files under `checkpoints/el/im`. Saves stage tensors on CPU and restore the runtime
device. The wrapper loads tensor-only files with explicit `map_location='cpu'`,
validates the immediate EL parent and overlay, strictly reconstructs the authentic
architecture, then moves it to the selected device. This avoids source-loader
implicit storage-device restoration; authenticated source bytes are unchanged.
See [torch.load](https://docs.pytorch.org/docs/2.14/generated/torch.load.html).

State tensor identities must match exactly after reload. Predictions must agree
on the selected device: exact for CPU; CUDA relative tolerance `1e-6`, absolute
`1e-7`, with actual maximum difference reported. No byte-identical Mac/Linux or
CPU/CUDA result is promised. CUDA behavior remains unvalidated until execution
on the workstation.

## Artifacts and return to Mac

The run is created using existing run-manifest infrastructure under
`~/codex/runs/stability-label-curation/<run-id>`. It records the clean code commit,
configuration, seed and all 21 actual hashed inputs. Outputs include:

- Selected original row identities/CSV subsets and leakage verification.
- Environment/Python/package/device/GPU/CUDA information and runtime configuration.
- EL checkpoint, IM overlay, state hashes and explicit parent lineage.
- EL/IM losses, optimizer steps, row counts and all-negative IM skips.
- Two 383-row development prediction CSVs and reload-consistency checks.
- Worker RSS/wall time, CUDA allocator peak allocated/reserved bytes, and output hashes.

GPU memory values describe PyTorch allocator peaks, not all processes on the GPU.
Missing GPU fields on CPU mean unavailable, not measured zero GPU usage. No
predictive-performance comparison is needed for this engineering smoke.

Require successful `reports/resource_execution.json` and
`reports/execution_verification.json`, then validate the manifest:

```bash
PYTHONPATH=src python -B -m stability_label_curation runs validate task-2_8-wsl2-bigmhc-smoke
PYTHONPATH=src python -B -m stability_label_curation bigmhc-worker verify-inputs --json
```

Return the complete new run directory (manifest, reports, logs, predictions,
processed row manifests and checkpoint parent/child tree) to Mac through the
separately authorized transfer mechanism. Preserve directory layout and all file
bytes; verify output hashes in the execution receipt before analysis. Keep all
scientific artifacts outside Git. This task performs no connection or transfer.
