# Task 2.22 — Peptide-disjoint multi-epoch original-label IM baseline

This protocol is fixed before scientific training. Task 2.21 commit
`4340f785bbf49a9fa31969ea0fb282617e210ed7` was fetched and verified in
origin/main; local main was already identical. Work proceeds on
`task/2.22-peptide-disjoint-multiepoch-baseline`, without merge or push.

The research target is immunogenicity of novel peptide–HLA candidates. Only
the existing eligible human HLA-I 9-mer original-label observations are used.
Historical 383-row development results informed prior decisions and are excluded
from this task's input reader, selection and final fit. Independent neoepitope
outcomes remain sealed. No stability supervision, EL label changes, EL retraining,
new dependencies, data downloads or backups are authorized here.

## Frozen split

Use all 3,428 original IM rows (955 positive / 2,473 negative). Normalize peptide
by stripping outer whitespace and uppercasing; the authenticated prepared input
already contains canonical uppercase amino acids. Group exact sequence across
all HLAs and all labels. Sort group sequences lexically, shuffle once with local
Python `Random(42)`, then make a single greedy pass. Add a whole group to validation
only if it strictly reduces the sum over the two labels of squared relative
deviations from 20% of that label's original observation count. Keep remaining
groups in training. No swaps, seed search, scores, HLA balancing, or metrics guide
assignment. Preserve source order within each partition. This approximately
stratifies observation counts while allowing mixed-label peptide groups.

Save the exact observation manifest, all original coordinates/labels, group
membership and two native training-format CSVs as exclusive immutable writes.
Require zero exact peptide and peptide–HLA intersections, both classes in both
sets, and exact one-time coverage of all original observation IDs with unchanged
labels/provenance. Report per-HLA observation/positive counts and sequence counts.
Compute each validation sequence's minimum same-length Hamming distance to IM
training and enumerate one-AA neighbors. Do not change the split afterwards.

Scan the authenticated original 1,453,578-row EL population once for exact
validation-peptide matches across all HLAs and labels. Record every matched EL
prepared-row index and HLA/label plus its pinned population identity. This
population-level definition is conservative: not every original EL row was
necessarily sampled in the native EL epoch. Classify validation observations
as EL-exposed IM-novel or fully training-unseen; report both rows and peptides.
EL exposure is not IM-label leakage, but IM-disjoint does not imply global novelty.

## Frozen training and selection

Reuse only Task 2.17 A `checkpoints/el`, produced by commit
`02313b20da218dbcacdbb2cbee5f5d435b258a18`. Authenticate the pinned historical
matched-state identity, EL-stage receipt, all 36 tensor files, original-label
configuration and source/input hashes. Never load the old IM overlay.

Use the pinned authentic BigMHC defaults and native EL-to-IM transfer list:
`condenser.att.weight`, `condenser.att.bias`, `condenser.out.weight`,
`condenser.out.bias`. Keep other parameters and original model/dropout behavior.
CUDA FP32, deterministic execution, no AMP/TF32, seed42 Python/NumPy/Torch CPU
and CUDA, four CPU threads, batch16, zero loader workers. Reset scientific RNG
after loading the same EL parent separately for each fit; this restart does not
attempt to reproduce the RNG state after the historical EL run.

Use native `makebats(shuffle=True,negfrac=None)`, shuffled DataLoader and native
all-negative IM batch skip. AdamW lr 5e-5, betas (0.9,0.999), eps 1e-8,
weight_decay 0.01 and installed native defaults. One optimizer persists over
all epochs in a fit, as in pinned `train.py`; create a fresh optimizer on final
restart. The existing runner gains only an optional persistent optimizer with
strict parameter-order verification. Default one-epoch callers retain their
behavior. Preserve complete ordered source-row/label sequences, batch fingerprints,
skips, losses, RNG boundaries and cumulative per-parameter optimizer counters.

Run exactly 60 internal IM epochs, with no early stopping or automatic extension.
After every epoch evaluate source-order training and validation BCE in eval mode
using stable BCEWithLogitsLoss, and validation tie-aware AUROC/non-interpolated AP.
Training update BCE is separately row weighted over optimized batches; native
source-style loss is also retained. Evaluation/checkpoint verification must
preserve scientific RNG. Save all validation predictions and candidate overlays.

Candidate epochs are **1, 2, 5, 10, 20, 40, 60**, fixed in repository configuration.
Select highest candidate validation non-interpolated AP; exact ties select earlier.
Neither BCE nor noncandidate epoch results can select the model. Freeze selection
and all settings in an immutable report before the final fit. Restart from the
original EL parent and train once on all 3,428 rows for exactly that many epochs.
Save a complete 36-tensor baseline checkpoint, independent of parent availability.
Verify strict tensor reload and same-device inference on fixed first16 training
rows; this probe is not a performance evaluation. Also reload/verify the selected
internal overlay against its explicitly recorded original EL parent.

## Future independent benchmark specification

Use the published BigMHC neoepitope immunogenicity benchmark, initially eligible
human HLA-I 9-mers, following the cohort identity and assay provenance in the
[BigMHC publication](https://doi.org/10.1038/s42256-023-00694-6) and
[publisher source repository](https://github.com/KarchinLab/bigmhc).
The publication evaluates neoepitope and infectious-disease cohorts separately;
the planned primary cohort is the neoepitope cohort. This task reads no cohort
files, individual outcomes, or sealed predictions and computes no benchmark scores.

Before future unsealing, freeze the model/configuration and perform an independent
identity/provenance audit. Required checks: exact peptide and peptide–HLA overlap
against all 3,428 IM training rows (also flag historical development exposure),
exact peptide overlap against original EL pretraining, same-length Hamming and
general sequence similarity distributions, original study/patient/assay/source-row
overlap, exact human HLA compatibility, valid canonical 9-mers and known assay
label definitions. An authorized custodian must verify label availability and
class balance after eligibility rules are frozen. External origin alone proves
neither source independence nor sequence independence.

Primary cohort excludes exact peptide overlap with final IM training, unsupported
or ambiguous HLA, malformed/non-9-mer/nonhuman rows, missing/ambiguous outcomes,
and demonstrably reused training source observations. Define duplicate source-row
handling and conflicting-assay rules before outcome inspection: count each
documented assay observation once; retain distinct assays with provenance and
report peptide-level sensitivity analysis under a separately frozen aggregation
rule. Quarantine unresolved provenance/labels; do not infer negatives from absence
of a positive assay. Do not exclude by prediction score or adjust rules after
performance is known. Keep EL-exposed IM-novel rows in the primary IM-novel cohort
and stratify exposure, rather than silently claiming all are globally novel.

Primary metric: tie-grouped non-interpolated AP on eligible independent IM-novel
peptides, with the observation unit explicitly recorded (peptide–HLA assays).
Secondary: AUROC, precision at predeclared K = **10, 20, 50**, and PPVn where
applicable. K exceeding eligible cohort size is undefined, never replaced by a
post-hoc K. Break top-K score ties deterministically by canonical peptide, HLA,
then source-row identity. Define PPVn as precision within the top n predictions
for each predeclared n in 1..N eligible rows, reporting the curve and its arithmetic
mean over 1..N; explicitly distinguish this convention from precision at n equal
to the number of positives. Freeze any publication-specific comparison convention
before outcomes are released. Report EL-exposed and fully training-unseen strata
when each has both classes and at least 20 observations; otherwise report counts
and mark unstable/undefined metrics. No threshold or K is chosen using outcomes.

## Execution and interpretation

Artifacts live under resolved project runs /
`task-2_22-peptide-disjoint-multiepoch-baseline/`; code/configuration are in Git.
Use existing GPU environment with `PYTHONPATH=src`, `CUDA_VISIBLE_DEVICES=0`,
`CUBLAS_WORKSPACE_CONFIG=:4096:8` and `python -B -m
stability_label_curation.bigmhc_multiepoch preflight`, then `execute` from a clean
committed task branch. Exclusive stage receipts prevent silent retries. Focused
tests cover grouping/coverage, fixed selection, sequence proximity, persistent
AdamW equivalence, native negative-batch skips, RNG isolation and prior runner
contracts. Stop on nonfinite loss, source/hash mismatch, unexpected parameter
change, optimizer reset or incomplete sampling.

Compare epoch1 and selected/longer epochs on this same internal split to describe
longer IM training. A better independence protocol is not itself a measured
accuracy gain. This validation is used for selection and is not a final unbiased
test. Do not compare its AP with historical 383-row AP as a common population.
Only exposure-negative validation sequences support the narrower claim of being
absent from both original training populations. No stability-specific gain can be
inferred. The final all-data fit consumes internal validation labels for training;
its internal predictions are not a new test. A future frozen independent evaluation
is required. Longer EL pretraining may only be recommended, never launched here.
