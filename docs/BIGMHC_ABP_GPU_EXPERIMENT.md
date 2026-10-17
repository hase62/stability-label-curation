# Task 2.14B matched A/B/P GPU experiment

This task explicitly authorizes one fresh A, one stability-weighted B and one
fixed within-HLA permuted P, using the approved Task 2.12 protocol and Task 2.13
adapter from GitHub main `0c3b5cf245c42803854c9139f4c4058cc36f7dbf`.
Original EL/IM labels, full eligible populations, seed 42, FP32, native sampling,
architecture, AdamW defaults, one epoch per stage and frozen development are fixed.
The earlier engineering-only configuration remains disabled.

`configs/bigmhc_abp_task2_14b.json` enables execution. The launcher creates all
artifacts below the project runs root's `task-2_14b-abp-gpu-experiment/`, with
separate A/B/P manifests and outputs. B/P configurations are saved outside Git
only after A succeeds, pinning its actual `matched_state.json` hash. Each worker
retains a maximum 3,600-second wall budget and the total launcher budget is
10,800 seconds. A failure stops execution without retry or automatic adjustment.

Minimal runner integration authenticates these nested arm manifests against
the canonical experiment manifest. The legacy unweighted path is preserved.
Task 2.13's reference comparison now canonicalizes optimizer-default sequences
through JSON so persisted list-valued AdamW betas match runtime tuples; changes
to their values still fail. No loss, sampler or optimizer equation changes.

Before training, run the full suite and the synthetic CUDA gate:

```bash
PYTHONPATH=src ~/codex/.venvs/bigmhc-gpu/bin/python -B -m unittest discover -s tests -v > /tmp/task2_14b-tests-preflight.log 2>&1
PYTHONPATH=src CUDA_VISIBLE_DEVICES=0 CUBLAS_WORKSPACE_CONFIG=:4096:8 \
  ~/codex/.venvs/bigmhc-gpu/bin/python -B -c \
  'import json; from stability_label_curation.el_stability_loss_adapter import synthetic_noop_evidence; print(json.dumps(synthetic_noop_evidence(device="cuda"),indent=2))' \
  > /tmp/task2_14b-cuda-noop.json
```

The gate uses synthetic observations and authentic pinned BigMHC code. CUDA
checks include two matched single-step AdamW updates, identical loss/gradients,
A/B/P initial tensors, source-ID propagation and unchanged native sampler RNG.
It never reads scientific training or development rows. Its source hashes must
match execution source bytes. CPU default checks retain zero optimizer steps.

Commit implementation before starting the exclusive launcher:

```bash
PYTHONPATH=src CUDA_VISIBLE_DEVICES=0 CUBLAS_WORKSPACE_CONFIG=:4096:8 \
  ~/codex/.venvs/bigmhc-gpu/bin/python -B -m stability_label_curation.bigmhc_abp_experiment \
  --noop-report /tmp/task2_14b-cuda-noop.json --test-log /tmp/task2_14b-tests-preflight.log
```

Before B, A must match authenticated Task 2.10 initial tensors, scientific
configuration, exposures, optimizer defaults and skip schedule. Historical
FP32 step-loss comparison uses rtol 1e-5/atol 1e-7; probability comparison uses
rtol 1e-5/atol 1e-6. These bounds are fixed before A outcomes. Larger differences
stop execution for investigation. The exact historical tensors need not be
reused. Across new A/B/P, initial tensors, RNG boundaries, every ordered batch
source-ID/label digest, optimizer defaults, steps and skips must match exactly.

Worker receipts authenticate datasets, lineage, checkpoints and predictions.
The launcher verifies receipt hashes, recomputes the same non-interpolated AP
and AUROC from saved 383-row probabilities, and exports all three prescribed
contrasts. Per-HLA metrics require five positives and five negatives; all rows
remain in global metrics. Compact sequence fingerprints retain batch boundaries;
per-batch fingerprints remain available in matched-state evidence.

This is one exploratory seed and one permutation on previously viewed development
data. Neither improved utility nor a null result establishes whether low-stability
EL positives are erroneous or reproducible. Sealed independent outcomes, extra
seeds, alternative strengths and correction methods are outside authorization.
