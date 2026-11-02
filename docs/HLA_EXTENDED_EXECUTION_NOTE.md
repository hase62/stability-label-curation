# Process-isolation note, before any completed epoch or new IM score

The frozen scientific protocol and implementation at `72eb757` are unchanged.
After launch, an isolated two-call synthetic check confirmed that PyTorch
`set_num_interop_threads(1)` raises on its second call. The original combined
fit-and-predict CLI would therefore finish training and fail at inference setup,
before loading a scoring model or writing predictions. This is an orchestration
error, not an optimization, data or score-definition change.

The original supervisor alone is replaced; the four live training processes
continue unchanged. Their training checkpoints and receipts are retained. Their
known post-training setup errors will be preserved, and scoring will run in a
fresh process. The four unstarted fits call the exact same frozen `train`
function and then score in a fresh process. No training is repeated, resumed
or selected, and no conditions, seeds, losses, budgets or predictors are changed.
Any other worker failure is not automatically retried. The execution receipt
records original/adopted PIDs, source hashes, commit and any recovery.

The original Task2.31 config is an authenticated EL-template input. Its old
`IM_training_authorized: false` field describes that historical task; it is not
used as an authorization gate by the reused low-level epoch function. The
present user authorization and prospective EL10/IM20 protocol govern the new
experiment. All 3,428 IM labels are used only for the explicitly authorized
native IM fitting; external benchmark labels remain inaccessible to scoring.
