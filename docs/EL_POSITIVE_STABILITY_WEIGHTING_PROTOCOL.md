# EL-positive stability weighting: prospective exploratory protocol v1

**Task 2.12; training approval: `decision_pending`.** This protocol specifies
one predictive-utility experiment. It asks whether a fixed stability-aware
allocation of EL-positive loss improves downstream experimentally assayed IM
prediction, compared with uniform loss and an HLA-matched permuted allocation.
It does **not** test whether detected EL positives are false positives or whether
low stability causes less reproducible detection. No model is trained here;
original EL and IM labels remain unchanged.

This is a versioned repository preregistration for a future comparison, not an
external registration or a claim that historical development outcomes were
unseen. Task 2.10 development performance was already known when this protocol
was written. No new IM development outcomes or predictions are inspected to
choose its strength, ranking, controls or eligibility. The exploratory design
requires scientific approval and an implementation task before training.

[Task 2.11](EL_POSITIVE_STABILITY_HYPOTHESIS.md) remains the evidence about the
biological hypothesis and missing replicate data. Its proposed repeat-detection
validation addresses a different question. A predictive-utility experiment can
be conducted without claiming that it resolves that evidence gap. This protocol
specifies **A/B/P loss weighting only**, not the earlier A–D pseudolabel-flipping
plan. Historical LOW/HIGH rules remain scientifically unapproved.

## Frozen populations and evidence

**Verified quantitative observation:** a provenance-backed, three-way join of
original EL rows, Task 2.5 ledger and frozen Task 2.4 scores recovers all
**70,069 original positives and 1,383,509 decoys: 1,453,578 rows, 49 HLAs**.
Every positive has a finite, nonnegative prediction from the frozen Teacher.
The pre-purge score population is 1,453,633; the existing leakage purge removed
55 rows (13 positives and 42 negatives). This task makes no new cohort selection.

The join authenticates original archive/member/index/hash, peptide, original HLA,
resolved HLA, original label and Teacher hash, plus contiguous derived-row
coordinates. It does not align by peptide/HLA alone. Each original observation
gets its own rank contribution; do not deduplicate repeated observations if a
future authorized version contains them. Duplicate source identities are errors.

The Teacher predicts kinetic half-life in **hours**, using allele-specific Ridge
regression fitted to `log1p(hours)`, with inverse predictions floored at zero.
Frozen model SHA256:
`a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99`.
It supports 67 trained HLA models; 49 occur in this EL cohort. No fuzzy HLA mapping,
C67S construct, Tm value, score recomputation or refitting is permitted.

Future IM transfer uses all **3,428 original-label rows** (955 positive,
2,473 negative). Evaluation uses the same frozen **383-row development cohort**
(120 positive, 263 negative, prevalence 120/383 = 0.313316; 31 HLAs). These IM
counts and file identities are carried forward from approved metadata, without
opening IM outcomes in this task. Portable paths and SHA256 identities are in
[the protocol configuration](../configs/el_positive_weighting_protocol_v1.json).
Original EL view SHA256 is
`5bf7fb7c25845aa171baae289a1bb8f00b185f1d5cce99c05609eabaca929fdf`;
frozen development CSV SHA256 is
`b4feb0c2765b99f6f845350c60be325895d6d33b184806fd2f2b28801687a2b1`.

Use the existing Task 2.5 sequence-purged populations in every arm. Authenticate
all training/development files and existing exact/one-substitution separation
before future execution. No new split, population filter or held-out test access
is authorized. Existing sequence protection does not establish study/donor
independence or eliminate all experimental-source confounding.

## Exact rank and weight definition

For each exact resolved HLA, take **only its original retained EL positives**.
Let n be their count, a the count of scores strictly below an observation's
score, and t the size of its tied-score group, including itself:

```
r = (a + t/2) / n
w_positive = 1 + 0.5 * (r - 0.5)
w_negative = 1
```

This is the empirical mid-distribution rank, equivalently `(ordinary 1-based
midrank - 0.5)/n`. It is deliberately not `midrank/n` or min/max scaling of ranks.
Compute ties by exact `Decimal` numeric equality of stored hour strings: `1`
and `1.00` tie; zero and negative zero tie. Do not round, jitter, tolerance-merge,
or break ties using row order. A predicted floor-zero tie is a model property,
not evidence of synthetic or biologically zero stability.

The aggregate analysis uses rational weights `(3*n + 2*a + t)/(4*n)`. Therefore
`sum(r)=n/2`, **mean positive weight is exactly 1 within every HLA**, and the
positive total is exactly 70,069. For unique scores the extremes are
`0.75 + 0.25/n` and `1.25 - 0.25/n`; tied extremes are closer to 1.
For n=1 or all scores tied, every weight is 1. For n=2 with distinct scores the
weights are 0.875 and 1.125. No minimum-n exclusion or shrinkage is introduced.
Flag n<10 descriptively, retaining identical rows across A/B/P. Sparse HLA
rankings are unstable estimates of an underlying distribution, not validated
reliability measures.

**0.5 is a predetermined exploratory perturbation strength.** Neither its value
nor the rank's direction has been validated as an optimal biological rule. Do
not select another strength using IM development results. All weights remain
positive, all targets retain their original binary values, and no observation
changes class membership or sampler eligibility.

Unexpected missing, nonfinite, unsupported or ambiguous positive scores **abort
the matched experiment preflight**. Do not drop rows, substitute another HLA or
supply fabricated scores. The present cohort has no such cases. Any future
neutral-weight fallback or expanded population needs a new, approved protocol
version before training. Ranks are computed once on the full eligible positive
population, not per batch, epoch, sampled subset, validation cohort or IM labels.

## Model-derived weight feasibility

The aggregate-only design calculation gives:

| Quantity | Value |
| --- | ---: |
| Positive score coverage | 70,069 / 70,069 (100%) |
| Observed ordinary HLA identifiers | 49 |
| Minimum / maximum weight | 0.750057 / 1.249965 |
| p5 / p25 / median / p75 / p95 | 0.774997 / 0.875 / 1 / 1.125 / 1.225003 |
| Below / equal to / above 1 | 35,021 / 27 / 35,021 |
| Total positive weight / HLA-wise means | 70,069 / exactly 1 each |
| Positives belonging to tied score groups | 353 |
| Weight-only effective sample size | 68,639.049 (97.96% of 70,069) |

`ESS=(sum w)^2/sum(w^2)` describes weight dispersion only. It is not the number
of independent experiments, a power estimate, or the effective sample size of
AdamW gradients. Type-7 interpolated quantiles summarize the calculated weights;
they do not introduce a curation cutoff.

The full 49-HLA table appears below. A*02:01 has a tied group of 36 predictions;
B*08:01 has 74 tied predictions. Ties receive equal weights. Permutation can
leave assignments unchanged by chance or because of ties; do not redraw a
permutation to make the intervention stronger.

| HLA | EL positives | Weight min–max | DTU validation n | Validation Spearman |
| --- | ---: | ---: | ---: | ---: |
| HLA-A*01:01 | 2,017 | 0.752107–1.249876 | 40 | 0.738 |
| HLA-A*02:01 | 7,088 | 0.751270–1.249965 | 193 | 0.584 |
| HLA-A*02:03 | 1,654 | 0.750151–1.249849 | 65 | 0.703 |
| HLA-A*02:11 | 94 | 0.752660–1.247340 | 65 | 0.607 |
| HLA-A*03:01 | 2,025 | 0.755062–1.249877 | 175 | 0.749 |
| HLA-A*11:01 | 1,953 | 0.752944–1.249872 | 123 | 0.839 |
| HLA-A*23:01 | 647 | 0.750386–1.249614 | 81 | 0.728 |
| HLA-A*24:02 | 2,968 | 0.751600–1.249916 | 127 | 0.721 |
| HLA-A*24:07 | 864 | 0.750868–1.249711 | 80 | 0.641 |
| HLA-A*25:01 | 314 | 0.751592–1.249204 | 67 | 0.461 |
| HLA-A*26:01 | 533 | 0.750938–1.249531 | 51 | 0.489 |
| HLA-A*29:02 | 4,473 | 0.750224–1.249944 | 67 | 0.564 |
| HLA-A*30:01 | 279 | 0.752688–1.249104 | 82 | 0.730 |
| HLA-A*30:02 | 105 | 0.752381–1.247619 | 70 | 0.577 |
| HLA-A*31:01 | 706 | 0.750354–1.249646 | 83 | 0.774 |
| HLA-A*32:01 | 852 | 0.750293–1.249707 | 4 | 1.000 (sparse DTU) |
| HLA-A*33:03 | 1,384 | 0.750181–1.249819 | 81 | 0.806 |
| HLA-A*66:01 | 98 | 0.752551–1.247449 | 70 | 0.463 |
| HLA-A*68:01 | 588 | 0.750425–1.249575 | 84 | 0.766 |
| HLA-A*74:01 | 1,085 | 0.750230–1.249770 | 78 | 0.723 |
| HLA-B*07:02 | 5,072 | 0.750148–1.249951 | 133 | 0.624 |
| HLA-B*08:01 | 2,543 | 0.757275–1.249902 | 94 | 0.695 |
| HLA-B*15:01 | 3,969 | 0.750063–1.249937 | 186 | 0.727 |
| HLA-B*15:02 | 1,497 | 0.750334–1.249833 | 60 | 0.662 |
| HLA-B*15:10 | 1,075 | 0.750233–1.249767 | 75 | 0.448 |
| HLA-B*15:17 | 77 | 0.753247–1.246753 | 72 | 0.697 |
| HLA-B*18:01 | 849 | 0.750294–1.249706 | 73 | 0.662 |
| HLA-B*27:02 | 1,164 | 0.750215–1.249785 | 80 | 0.829 |
| HLA-B*27:03 | 424 | 0.752948–1.249410 | 80 | 0.757 |
| HLA-B*27:05 | 2,433 | 0.755138–1.249897 | 76 | 0.582 |
| HLA-B*35:01 | 1,063 | 0.751646–1.249765 | 136 | 0.540 |
| HLA-B*35:03 | 853 | 0.750293–1.249707 | 81 | 0.524 |
| HLA-B*35:08 | 95 | 0.752632–1.247368 | 2 | -1.000 (sparse DTU) |
| HLA-B*39:01 | 595 | 0.751261–1.249580 | 134 | 0.607 |
| HLA-B*39:10 (sparse EL) | 2 | 0.875000–1.125000 | 83 | 0.754 |
| HLA-B*40:01 | 1,548 | 0.750161–1.249839 | 60 | 0.633 |
| HLA-B*41:01 | 293 | 0.750853–1.249147 | 74 | 0.592 |
| HLA-B*42:01 | 1,813 | 0.750138–1.249862 | 76 | 0.779 |
| HLA-B*44:05 (sparse EL) | 2 | 0.875000–1.125000 | 71 | 0.541 |
| HLA-B*45:01 | 916 | 0.750546–1.249727 | 76 | 0.521 |
| HLA-B*46:01 | 1,215 | 0.750206–1.249794 | 62 | 0.465 |
| HLA-B*51:01 | 1,915 | 0.753655–1.249869 | 81 | 0.687 |
| HLA-B*54:01 | 640 | 0.751172–1.249609 | 80 | 0.646 |
| HLA-B*55:01 | 773 | 0.752911–1.249677 | 83 | 0.526 |
| HLA-B*56:01 | 970 | 0.753093–1.249742 | 83 | 0.583 |
| HLA-B*57:01 | 4,371 | 0.750057–1.249943 | 71 | 0.606 |
| HLA-B*57:02 (sparse EL) | 5 | 0.800000–1.200000 | 69 | 0.791 |
| HLA-B*57:03 | 2,526 | 0.750099–1.249901 | 72 | 0.739 |
| HLA-B*58:01 | 1,644 | 0.750456–1.249848 | 75 | 0.757 |

### Teacher limitations and confounding

**Prior held-out DTU evidence:** overall internal validation has Spearman
0.768499 and MAE 3.972386 hours. These are not EL repeat-detection calibration
metrics. For B*08:01, validation n=94 and Spearman=0.695193 support useful
within-allele ordering, despite its low absolute scale; its EL-positive predicted
median is about 0.410 hours. This does not validate its rank as presentation or
repeat-detection probability. B*35:08 has only two validation rows; A*32:01 has
four. Their reported correlations are not adequate reliability estimates.

All supported observations remain in all arms; these uncertainties are flags,
not post-hoc eligibility rules. Ranking removes cross-HLA absolute scale from
the weighting equation but cannot correct wrong within-HLA ordering, extrapolation,
selection bias, allele-dependent prediction errors or finite-sample noise. It
can amplify Teacher error by assigning larger weights to wrongly high scores.

The existing analysis identified 305 positive peptides exactly exposed to Teacher
fitting sequences and 39 additional positives within one substitution. These
remain exposure warnings, not independently validated stability predictions.
No intervention or subgroup is selected using their IM outcomes. No calibrated
per-observation prediction uncertainty or repeated-detection outcome is available.

The released EL schemas lack study/run/replicate, abundance, sampling depth and
acquisition-opportunity linkage. Study-specific score distributions or assay
bias could affect which positives are upweighted. HLA-only permutation does not
control those unobserved factors. Technical MS variability, biological
presentation and IM responses remain different quantities. Positive rank is
neither a calibrated presentation probability nor proof of label reliability.

## A/B/P conditions and separate random streams

| Arm | EL labels/population | EL positive weight | EL negative weight | IM transfer |
| --- | --- | --- | --- | --- |
| A | Original, unchanged | 1 | 1 | Original labels; native unweighted loss |
| B | Same rows and original labels | Defined stability midrank weight | 1 | Identical procedure |
| P | Same rows and original labels | Same B weights, reassigned within HLA | 1 | Identical procedure |

P is a **permuted-weight control**, not a change to any original negative or
positive target. Its per-HLA and global multisets, sums, quantiles and ESS must
match B exactly before FP32 conversion. The one fixed permutation need not
remove every incidental score/weight association. It is a single realization,
not a permutation-test null distribution.

For each HLA independently, sort immutable `source_row_id` strings
lexicographically. Seed a local Python `random.Random` instance from the big-endian
integer of SHA256 of the following UTF-8 bytes:

```python
(b"el_positive_weighting_preregistration_v1" + b"\x00" + b"permutation"
 + b"\x00" + b"42" + b"\x00" + HLA.encode("utf-8"))
```

Here `b"\x00"` is one NUL byte; `42` is decimal seed text.
Apply descending Fisher–Yates (`j=n-1..1`, `k=local_rng.randrange(j+1)`) to B's
ordered weights and assign back to these same source IDs. Pin Python version;
no draws from global Python, NumPy, Torch CPU or CUDA RNGs are allowed. Tied or
identity assignments are accepted without redrawing. An HLA's permutation must
not depend on the order in which other HLAs are processed.

Store stable assignment digests and, in a future authorized implementation,
authenticated weight ledgers. This task exports only aggregate distributions
and assignment hashes, not row-weight files or training-ready data. Weight and
permutation computation must occur outside model/sampler RNG streams. Reinitialize
and restore the same training RNG states at corresponding arm boundaries.
Do not insert extra randomized model construction, DataLoader creation or
validation calls into one arm only.

## Loss, sampler and gradient interpretation

The future adapter will use **external per-example weights**, not
`BCEWithLogitsLoss(pos_weight=...)`. For batch size m:

```
l_i = BCEWithLogits(logit_i, original_binary_target_i, reduction="none")
L_EL = sum(w_i * l_i) / m
L_IM = native mean BCEWithLogits with all weights 1
```

Do **not** divide by sum of weights, normalize positives separately, change the
negative coefficient, or add weight-dependent sampling. Compute rational B/P
weights once, convert to FP32 once, and verify each HLA's positive total in
float64 diagnostic accumulation with `abs(total-n) <= 1e-6 * max(1,n)`.
Do not re-center rounded weights in training; record their rounding residuals.

The pinned BigMHC `Dataset.makebats(shuffle=True, negfrac=0.99)` and batch-size
argument 16 produce **one positive plus 16 negatives** per EL update for this
nine-mer population. All 70,069 positive anchors are consumed once; 1,121,104
negative instances are consumed, leaving 262,405 negative rows unused in that
epoch. These are static expectations from the current native contract, not
newly executed sampling. The exact realized IDs and order must be audited.

For such a batch, `L=(w*l_pos + sum(16 negative losses))/17`. Negative example
coefficients stay 1/17. The positive coefficient ranges approximately
0.04412–0.07353, against baseline 1/17=0.05882. Per-batch total coefficient is
`(16+w)/17`, approximately 0.98529–1.01471. Thus preserving epoch total positive
weight is not the same as preserving every batch's loss scale. If expressed as
a fraction of the total *nominal* coefficient, `w/(16+w)` ranges about
4.48%–7.25%, versus 1/17≈5.88%; this is not a measured gradient share.

Because each positive is used once and each HLA's sum is its positive count,
the epoch positive coefficient total is 70,069/17, while the negative total is
1,121,104/17 in A/B/P. This preserves the aggregate nominal 1:16 budget and
HLA-wise positive budget. It does **not** preserve gradient norms, gradient
direction, correlations with prediction error, AdamW moments or fitted parameters.
Those changes are part of the intended intervention; report them if instrumented,
without adding optimizer-step equalization or a redesigned sampler.

The authentic BigMHC architecture, encoded HLA/peptide inputs, BCE targets,
AdamW family and complete optimizer defaults stay fixed. Only EL loss aggregation
changes. No model input receives the stability score. Learning rate stays 5e-5;
seed 42; FP32; one EL epoch and one IM epoch; unchanged batch-size argument 16,
controlled workers, transfer-layer selection and checkpoint layout. Record all
runtime/library/device/determinism settings; use the same environment for A/B/P.

## Necessary implementation and no-op gates before training

No training runner change is implemented in this task. A subsequent approved
implementation must:

1. Carry stable source-row identity alongside native dataset row reordering and
   batching. Join weights by authenticated source ID, never mutable DataFrame
   position or peptide/HLA alone; reject duplicate, missing or mismatched joins.
   Identity columns are auxiliary, not model features or grouping keys. Verify
   original encoded tensors, targets and eligible row order are unchanged.
2. Add unreduced BCE and external positive weights only in EL training. Retain the
   native sampler and DataLoader behavior, all IM labels/loss, parameter list,
   all-negative IM batch skip rule and optimizer defaults. Sampling must continue
   to use original targets, never scores or weights.
3. Separate weight/permutation randomness. Authenticate and store the same initial
   36-tensor full EL state for every arm. Record initial tensor hashes and restore
   the same RNG state before corresponding construction, shuffle and training
   calls. Do not seed using the arm name.
4. Instrument native sampled original IDs: ordered batch/row digest, positive-anchor
   identities, negatives including reuse, DataLoader order, batch sizes and skip
   mask. Require the EL schedule and 70,069 updates to match across A/B/P.
   Require IM order/skip mask and expected 214 updates to match across all arms;
   investigate and stop on a mismatch rather than silently compensating.
5. Transfer each trained EL model into its own IM child. The trained EL parent is
   intentionally different across arms; the initial pre-EL state is common.
   Preserve authentic four-tensor IM overlay inheritance from the corresponding
   full 36-tensor EL checkpoint, updated-layer list and fresh IM optimizer policy.
   Record configuration, source and dataset hashes, parent/child hashes, RNG
   boundary states and saved/reloaded prediction consistency.
6. Perform a **no-op regression check**: on the same fixed mini-batches, parameters
   and RNG state, all-one adapted weights must reproduce the native loss,
   gradients and parameter updates, sampled IDs and unchanged IM path. Use the
   same device/FP32 environment. Prefer exact identity; if reduction kernels give
   rounding differences, record them and require `rtol=1e-6, atol=1e-7` for the
   numerical no-op smoke checks. This tolerance is an engineering check, not
   proof that long training trajectories are equivalent. No no-op training or
   actual BigMHC gradient test is performed in Task 2.12.

**A fresh matched A is required for the principal B/P comparison.** Task 2.10
is historical context, not an automatically exact control. Its reported 0.476174
IM AP and 0.693124 AUROC are approved execution-summary values, not newly
recomputed here. Local Task 2.10 checkpoint/log authentication and equality of
adapted loss reductions, RNG consumption and schedules have not been established.
Even successful miniature no-op checks do not establish full historical
trajectory identity. Run A/B/P through the same reviewed implementation and
matched initial state; preserve the original Task 2.10 artifacts untouched.

## Frozen evaluation and interpretation

Evaluate every arm's trained EL model as an EL proxy for IM, and its transferred
IM model, on the same frozen 383 original development observations. Require
383/383 finite predictions for both score types; missing coverage is an execution
failure, not permission to choose a more favorable intersection. Save original
row IDs, HLA, original outcomes and scores with cohort/model hashes in a future
authorized run. Do not use development outcomes for early stopping or checkpoint
selection: use the fixed one-epoch checkpoints.

**Primary outcome:** IM **average precision** (AP), often called AUPRC.
Compute AP as `sum((recall_k-recall_(k-1))*precision_k)` over distinct score
thresholds in descending order, grouping tied scores together. Do not substitute
trapezoidal PR area. Secondary outcomes are IM AUROC, EL-proxy AP and EL-proxy
AUROC. AUROC gives tied positive/negative scores half credit. Higher logits or
sigmoid probabilities indicate higher predicted positivity; use a consistent
stored score representation and record it across arms.

Report the same predeclared paired differences for every metric:

| Contrast | Interpretation to investigate |
| --- | --- |
| B − A | Utility of the particular stability-aware weighting versus uniform learning |
| B − P | Whether stability assignment adds benefit beyond the same HLA-specific weight distribution |
| P − A | Nonspecific effect of this particular weight perturbation/control realization |

Report all three, without choosing the most favorable contrast after outcomes.
Positive B−A together with positive B−P is the directional pattern motivating a
larger test; it is not a significance or generalization claim. If B does not
improve AP versus A, or is no better than P, that is evidence against utility or
stability specificity **for this one configuration**, not proof against every
stability-related hypothesis. A larger P−A improvement than B−A argues against
attributing the improvement to the ordering used in B. No effect can also reflect
small cohort size, noisy Teacher scores or insufficient training.

Per-HLA metrics are descriptive only: report n, original class counts and
prevalence; compute AP/AUROC only with at least five positives and five negatives,
otherwise mark unavailable with reason. This reporting-support rule never removes
rows from global metrics or changes training. Do not tune it using outcomes.
Do not treat correlated peptide/HLA observations as independent replicates.

One seed, one P assignment, one epoch per stage and a previously viewed
**development** cohort provide an exploratory engineering/scientific comparison.
Do not claim statistical significance, biological reproducibility, population-wide
superiority or independent external-test performance. No outcome-driven weighting
strength search, resampling of P, cohort selection, thresholds, additional seeds
or model configurations is permitted under this version. Sealed independent
tests remain untouched. A separate approved study would be required to assess
robustness, uncertainty and external utility.

## Reproduce the design analysis on Mac

The standard-library module reuses the existing frozen-score/provenance reader.
It holds only positive score/ID lists, counts negatives and produces **aggregates
only**; it neither refits the Teacher nor writes weight ledgers or training data.
All 23 actual external inputs are hashed and linked to Task 2.11's canonical run
and its Task 2.3–2.5 source evidence. IM/development CSVs are not opened. The
existing analysis configuration is reused for provenance; historical threshold
fields in that parent are not consumed to construct any new threshold rule.

```sh
PYTHONPATH=src python3 -m stability_label_curation.el_positive_weighting_design \
  --config configs/el_positive_weighting_protocol_v1.json
```

Default inspection is read-only. With an existing canonical run recording the
current code, protocol configuration, seed and actual input hashes, use
`--out <project-run-directory>` to write `reports/weighting_design_feasibility.json`
and `reports/execution_verification.json`. Repeat with `--verify-existing` to
verify byte-identical offline aggregate output, without overwriting it. Input
storage resolves through `stability_label_curation.paths`; configurations contain
project-relative paths, not a particular user's home directory.

Canonical design run: `task-2_12-el-positive-weighting-preregistration` under the
project runs root. Source inputs, original labels, previous runs and the
interrupted Task 2.8 worktree must remain unchanged. This prospective protocol
is the only new proposed scientific intervention; no training command is supplied
because its loss adapter has not yet been implemented or approved.

## Explicit decisions before any training

All six remain **`decision_pending`**:

1. Approve the narrow predictive-utility hypothesis and the invalidity of biological
   mislabeling/repeat-detection conclusions from this experiment.
2. Approve the exact rank/tie/sparse-group/missing-score rules and fixed exploratory
   strength 0.5, including retaining the uncertain Teacher alleles without a
   post-hoc reliability filter.
3. Approve A/B/P, the one independent per-HLA permutation and its fixed RNG contract.
4. Approve mean-by-row weighted BCE, unchanged native sampler/optimizer semantics,
   no-op gates and a new matched A rather than automatic historical-baseline reuse.
5. Approve frozen cohorts, matched initialization and schedules, FP32, seed 42,
   one epoch per stage, original IM labels and no model-selection loops.
6. Approve the common development-only metric/contrast plan, its exploratory
   limitations and continued sealed-test isolation.

The smallest next task, **only after review**, is to implement the source-ID-safe
loss-weight adapter and scheduling/no-op tests without training corrected models.
A later separately authorized A/B/P execution would then use the reviewed protocol.
