# Task 2.21 — Z790 stability auxiliary A/S/P execution

Execution is authorized by Task 2.21, starting at main
`8f827b47920c2ae56f0098f4ae6170a7ad322692`, on branch
`task/2.21-stability-auxiliary-gpu`. The fixed scientific protocol remains
[Task 2.20](BIGMHC_STABILITY_AUXILIARY_PROTOCOL.md) and the canonical
`configs/bigmhc_stability_auxiliary_task2_20.json` is unchanged.

The only runner change is the output run ID, now
`task-2_21-stability-auxiliary-gpu`. Follow the protocol's Z790 commands with
preflight directory `task-2_21-z790-preflight`; use its explicit authorized
configuration copy. No inputs are copied or downloaded. S/P each run once;
historical A is referenced in place if all gates pass. No sealed outcomes
are accessed.

## Pretraining evidence

Actual platform: Z790 WSL2, NVIDIA GeForce RTX 4090, existing Python 3.13.5,
PyTorch 2.13.0+cu130 / CUDA 13.0. The protocol's eight related unittest
modules passed 163 tests without failures or skips. The current authentic
synthetic CUDA gate passed all 12 tests without skips. Evidence is in resolved
project runs / `task-2_21-z790-preflight`, under `logs/relevant_tests.log`,
`logs/synthetic_cuda_gate.log`, and `reports/synthetic_cuda_gate.json`.

The strict 17-row historical-A CUDA compatibility gate passed: native and
historical unit-weight BCE both equal `0.6862132549285889`; all gradient and
post-AdamW tensors are exactly equal, with maximum absolute differences 0.
Therefore historical A reuse is selected, subject to the unchanged full-cohort,
artifact, runtime, initialization, sampling and RNG gates. No tolerance changed.

S/P use native BCE plus 0.1 times positive-anchor squared rank error, the
isolated seed-22042 414-to-1 head, and the original native training schedule.
The launcher requires a clean committed source tree before scientific work.
Completion evidence and development results will be appended after execution.
