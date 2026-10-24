# Task 2.37 — Pre-evaluation checkpoint-probe metadata repair

2026-10-24 JST. Original protocol/configuration, targets, weights, seeds, optimizer,
orders, score extraction and metric definitions remain byte-identical. No new
IM predictions or performance outputs existed when this repair was made.

D seed123 completed all20 passes and3780 updates, saved its exact two-tensor
output checkpoint and all20 pass receipts, then stopped at a bitwise reload-probe
assertion. The training-mode original had only two output tensors requiring
gradients, while the freshly reloaded model defaulted to all parameters requiring
gradients. With identical36 tensor values, native CUDA forward on16 training
observations differed by up to1.430511474609375e-06. A focused same-model diagnostic
shows that restoring the training requires_grad flags makes the forward bitwise
equal (difference0); no optimizer step or IM observation was used in diagnosis.

The correction is to call freeze_output_only on the reloaded model for the
**training-mode checkpoint probe**. IM scoring retains the originally committed
native eval/no-grad pathway for every model, matching the saved A pathway; it is
not changed by this repair. Freezing metadata does not change checkpoint tensors.
A guarded resume accepts only the authenticated already-completed D_123 fit and
executes the remaining eight unchanged fits. D_123 is not retrained or discarded.

The completed D_123 receipt is reconstructed from its preserved head, the exact
parent A and20 original pass records. Its exact fit-only elapsed time and original
live probe vector were not preserved by the failed process and are reported as
unavailable. Tensor integrity and a bitwise training-mode probe between independent
reconstructions are verified. The original control flow checked all3780 optimizer
steps, frozen tensor identities and allowed changed keys before saving the head.
The raw optimizer state was not saved and is not needed to continue another fit.
The reconstructed optimizer-default metadata is explicitly marked as reconstructed
from the unchanged configuration. Other fits retain their normal live-versus-reload
training probes and exact optimizer-step receipts.

Original failure/start/log/telemetry, completed weights and histories are retained.
The recovery manifest pins their bytes and the old/new code hashes.17 focused
checks, including a new reload-metadata test, pass. No epoch, hyperparameter,
cohort, orientation, seed or experimental arm is changed. This is execution
bookkeeping and validation repair, not a scientific protocol amendment or a new
experiment. See the run's technical_reload_repair.json, reload_diagnostic.json,
reload_mode_alignment.json and checkpoint D_123 identity receipt.
