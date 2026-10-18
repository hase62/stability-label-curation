# Task 2.17 preregistered A/B/P execution

Starting main: `2ae58c234924c602863e470dd6873f14f45d0cfb`.
Branch: `task/2.17-abp-comparison`. Host: Z790 WSL2, RTX 4090, CUDA device 0.

Reuse `configs/bigmhc_abp_task2_14b.json`, the existing Task 2.14C fail-fast
preflight, the Task 2.13 adapter and all existing inputs. Execute exactly one
fresh A, B and P in that order; do not resume Task 2.14B. Scientific settings,
historical comparison tolerances and the completed-A gate for B/P are unchanged.
The launcher retains its 3,600-second worker and 10,800-second total budgets.

The launcher now defaults to the requested `task-2_17-abp-comparison` under
`resolve_paths().project_runs_dir`, with separate A/B/P children. Historical
Task 2.14B names remain accepted for evidence compatibility. Run creation still
rejects existing destinations. Task identifiers and starting-main metadata are
updated; no input configuration, optimizer, sampling or loss definition changes.

Stage-start receipts include configuration identity and the existing training
RNG boundary hashes. Stage-completion receipts additionally record the process
RSS high-water mark through that stage (not an isolated stage increment).
EL development predictions are persisted after EL checkpoint reload verification,
before IM begins. Existing full-precision losses, ordered batch fingerprints,
stage wall times, CUDA allocator peaks, tensor identities and checkpoint receipts
remain enabled. All execution evidence and outcomes belong outside Git.

Before execution, run the complete unittest suite in the existing GPU Python
environment and the existing small synthetic CUDA no-op gate. Run the launcher
with `CUDA_VISIBLE_DEVICES=0` and `CUBLAS_WORKSPACE_CONFIG=:4096:8`, supplying
the passing test log and CUDA report. Its integrated preflight authenticates
both full cohorts, the Teacher sidecar, A/B/P weights and historical evidence
before any scientific optimizer update.

Report frozen-development non-interpolated IM AP as primary, IM AUROC and
EL-proxy AP/AUROC as secondary, and B-A, B-P, P-A for all four. This is one
exploratory seed and one permutation, without significance, generalization,
label-error or repeat-detection conclusions. No additional seed, tuning, sealed
evaluation access, checkpoint upload, merge or push is authorized.
