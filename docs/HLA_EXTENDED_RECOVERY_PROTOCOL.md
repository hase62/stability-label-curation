# HLA extended epoch recovery — storage amendment, 2026-11-03 JST

The researcher authorizes eight fixed fits in an isolated recovery run following
the diagnosed missing `checkpoints/` parent failure. The old failed run and its
receipts remain immutable. Source is commit
`97637c290bd59b3e811992b370c85e3b4ccb63cb`.

The original scientific module, all original configuration and dependency source
files remain byte-identical. `hla_epoch_recovery` explicitly replaces only the
original module's `paths_config`, `require`, and `save_complete` IO boundaries.
Training, inference, loss, rank/weight, RNG reset, sampler and optimizer functions
are neither edited nor replaced. The inherited config's original `run_id`
describes scientific lineage; `storage_run_id` in the recovery receipt specifies
the new, sibling recovery directory. No write targets the failed run.

The exact six frozen input files are copied and authenticated; training-only
weights are not recomputed and the Teacher is not rescored. Original 63,053 EL
positives/1,245,143 negatives, fixed 145,371 EL validation rows, and all 3,428 IM
training observations are unchanged. Seeds42/123/456, original initialization,
native AdamW lr5e-5/defaults, native batches and row-mean weighted BCE, EL10/IM20
and final-epoch policy remain fixed. A42's existing EL10/IM20 are reused. A123,
A456,W42,L42 repeat the lost EL10; W123,L123,W456,L456 are original first fits.

Before GPU training: create the isolated checkpoint parent safely, run CPU
sentinel tests, save an actual untrained authentic BigMHC EL checkpoint, strictly
reload it in a fresh CPU process and compare all36 parameter-state hashes.
Reload that parent and test the IM full-checkpoint save path likewise, without
updates or forward passes. Reject missing files, all files without a marker,
corruption and pre-existing targets. Independently reload both authentic reused
A42 checkpoints. No optimizer updates are authorized in this gate. GPU training
is blocked until every check, focused test and frozen code/input guard passes.

Each real save first persists expected state hashes, reserves an exclusive new
target, writes all36 tensors, reloads in a separate CPU process with
`weights_only=True`, retains the original same-device16-training-row probe, and
checks that scientific RNG is unchanged. Only then is `VERIFIED_CHECKPOINT.json`
issued. A partial directory is never a valid checkpoint. EL certification must
finish before IM20 begins. IM restarts RNG with the same seed and fresh native
optimizer, exactly as before. Predicting uses a separate fresh process after
training, avoiding repeated interop-thread initialization.

Four concurrent jobs retain the existing resource setting. Every fit has one
attempt; a previously existing started receipt/target prevents duplication. On
unknown failure stop the queue, terminate only supervisor-owned worker process
groups, preserve all evidence and report. No automatic retry, changed seed or
hyperparameter adjustment. The failed run's complete file inventory is checked
before and after recovery. No old checkpoint or pilot is overwritten.

Final audit authenticates18 checkpoints and strict reload evidence, all ordered
cohort identities and36 native score files /144,990 rows. Ranks or scores are not
transformed anew. Outcome identities are consulted only after prediction freeze
for byte-exact Mac handoff; no outcomes enter fitting, scoring, checkpoint/epoch
selection, tuning or calibration. No IM AP/AUROC, paired deltas or bootstrap CIs
are computed. Preserved original outcomes, row keys/dependence identifiers,
actual score files, code/config/receipts and SHA256 ledgers are included in a
private final ZIP, while large checkpoint weights remain in WSL storage.

The final five requested files are copied to a newly timestamped actual Windows
Known Folder Downloads directory (Desktop only as fallback), with ZIP CRC,
member hashes, re-extraction and Windows-copy verification. Failed/incomplete
exports are explicitly labeled. No merge, push, Release, automatic Mac transfer,
new model variants, independent-confirmation claim or additional experiment.
