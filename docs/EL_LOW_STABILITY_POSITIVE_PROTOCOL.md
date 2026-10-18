# Task 2.18: low-stability-only EL-positive intervention

Status: **exploratory protocol; scientific approval pending; no training authorized**.
Designed on Z790 WSL2 from approved main
`02313b20da218dbcacdbb2cbee5f5d435b258a18`, on branch
`task/2.18-low-stability-positive-design`.

## Rationale and chronology

Test whether reducing the training contribution of relatively lower predicted
kinetic-stability EL positives improves downstream BigMHC immunogenicity (IM)
prediction. This is a predictive-utility experiment, not a correction of EL labels
or an estimate of their reliability. Human HLA-I only; predicted kinetic
half-life is kept separate from measured half-life and thermal melting temperature.

The [Task 2.11 hypothesis](EL_POSITIVE_STABILITY_HYPOTHESIS.md) suggests some
lower-stability detections might be less reproducible under comparable conditions.
No suitable repeat-detection/opportunity data are available. This experiment
cannot test that biological hypothesis directly.

Task 2.17 combined lower-positive downweighting with higher-positive upweighting.
Its completed single-seed, 383-observation development results were:

| Condition | IM non-interpolated AP |
| --- | ---: |
| A | 0.4761744527124684 |
| B (two-sided weights) | 0.4566148858867259 |
| P (two-sided permuted weights) | 0.4753169901616688 |

The deterioration cannot identify which component caused it, or exclude an
interaction between the two. **This one-sided proposal was made after observing
those development outcomes.** It is exploratory and cannot be called an
independent confirmatory test. The formula, coefficient, midpoint and controls
below are fixed by this task; they were not fitted to those scores and must not
be adjusted after viewing future scores. There is no additional weighting variant.

Reviewed sources: the [Task 2.12 protocol](EL_POSITIVE_STABILITY_WEIGHTING_PROTOCOL.md),
[Task 2.13 adapter](EL_STABILITY_LOSS_ADAPTER.md),
[Task 2.17 execution specification](BIGMHC_ABP_TASK2_17.md), and the existing
`task-2_17-abp-comparison/reports/task2_17_completion.json` under resolved project
runs. Completion-report evidence is reused; no checkpoint audit, model replay,
new evaluation, downloads or regeneration was performed for this design.

## Exact fixed rule

Use all original retained EL positives within each exact resolved HLA. For n
positives, a scores strictly below a score, and a tied group of size t:

```text
r = (a + t/2) / n
w_old = 1 + 0.5 * (r - 0.5)
w_low = min(1.0, w_old) = min(1, (3*n + 2*a + t)/(4*n))
w_negative = 1
```

Larger r means higher Teacher-predicted kinetic stability. Reuse Task 2.12's
empirical mid-distribution rank, not ordinary rank/n. Numeric ties use exact
`Decimal` equality of stored score strings (including `0` and `-0.0`, or `1`
and `1.00`). Use rational arithmetic for design invariants and convert each
weight once to FP32 for future training. Do not round scores, jitter ties,
recompute ranks per batch, or use development/IM observations in ranking.

Weights below the midpoint retain the original slope 0.5; weights at/above it
are 1. All original labels remain unchanged. No positive is upweighted or
excluded. Every negative has weight 1. There is no absolute half-life cutoff.
**The rank midpoint 0.5 is inherited from the previous mathematical rule; it is
not an established biological reliability cutoff.** Ranks are not calibrated
detection, repeat-detection, presentation or immunogenicity probabilities.

For unique scores, the lowest weight is `0.75 + 0.25/n`; the upper half is capped
at 1. Ties crossing the midpoint are kept intact, so exactly half need not be
affected. Singleton/all-tied groups remain unit-weighted. For n=2 distinct scores
the weights are 0.875 and 1. Sparse groups remain included without shrinkage or
exemptions. Missing, duplicate, unsupported, nonfinite, negative or ambiguous
positive scores must abort preflight; no fallback, relabeling or eligibility change.

## Existing bindings and aggregate calculation

The standard-library analysis in
[`el_low_stability_design.py`](../src/stability_label_curation/el_low_stability_design.py)
reuses only the existing `EL`, `positive_scores`, and `positive_score_manifest`
bindings in `configs/bigmhc_abp_task2_14b.json`. These input identities are checked
for this calculation; historical artifact audits are not rerun. It reads the
70,069-positive score-only sidecar and streams the original EL CSV, checking
prepared-row coordinates, immutable archive/member/source-row IDs, raw-row hashes,
HLA, peptide and original label. It retains positive scores in memory and counts
negatives. It never exports row weights or another complete training-data copy.
No actual permutation is generated during design.

Existing runs-relative bindings:

| Input | Relative path | SHA256 |
| --- | --- | --- |
| Original EL | `task-2_5-bigmhc-pilot-preparation/processed/el_train_original.csv` | `5bf7fb7c25845aa171baae289a1bb8f00b185f1d5cce99c05609eabaca929fdf` |
| Positive scores | `task-2_13-el-stability-weight-adapter/processed/el_positive_teacher_scores.csv.gz` | `ab0473b669f61792ff63a926185a5e737544209537c5de938b30e519a232e884` |
| Score manifest | `task-2_13-el-stability-weight-adapter/reports/positive_score_manifest.json` | `e79fb60b1c04f33889e9d3ecd6a7bd145255c156487cd4d4873a90c8ab715862` |

The manifest binds the frozen Teacher identity
`a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99`;
the Teacher itself is not opened or executed. Historical references in the
manifest do not authorize fetching other artifacts. Neither IM training nor
development payloads are needed for this aggregate analysis; sealed outcomes
are never opened.

Canonical small output, outside Git:
`~/codex/runs/stability-label-curation/task-2_18-low-stability-positive-design/weight_exposure.json`
under default storage resolution. Use `resolve_paths().project_runs_dir` in code;
no machine-specific absolute paths are embedded. The output records all three
input bindings, configuration/source hashes and actual host/runtime. Default
inspection writes nothing; `--write` creates this fixed run exclusively and
refuses an existing destination.

```sh
PYTHONPATH=src python3 -B -m stability_label_curation.el_low_stability_design
# Explicit aggregate publication, only for a new destination:
PYTHONPATH=src python3 -B -m stability_label_curation.el_low_stability_design --write
PYTHONPATH=src python3 -B -m unittest discover -s tests -p 'test_el*design.py' -v
```

Actual execution: Z790 Linux WSL2, CPU standard-library aggregate analysis;
**32 relevant tests passed, zero failures/skips** (6 new tests, 26 existing design
tests). Synthetic tests exercise clipping, numeric ties, midpoint ties, sparse
cases, exact reductions, fixed batch denominator, invalid scores and RNG isolation.
No CUDA execution or future L/P training behavior is claimed by these checks.

## Weight and exposure estimates

These are model-derived descriptive calculations, not measured reliability.
All 70,069 EL positives in 49 HLA groups have existing scores; the unchanged
original cohort also has 1,383,509 negatives (1,453,578 rows total).

| Positive-weight quantity | A | L and P |
| --- | ---: | ---: |
| Affected positives | 0 | 35,021 (49.980733%) |
| Unit-weight positives | 70,069 | 35,048 |
| Minimum | 1 | 0.750057195150 |
| Median | 1 | 1 |
| Mean | 1 | 0.937500229371 |
| Maximum | 1 | 1 |
| Total positive weight | 70,069 | 65,689.703571766 |
| Total positive-weight reduction | 0 | 4,379.296428234 (6.249977063%) |

Unlike Task 2.17, mean positive weight is below 1. Do not recenter/rescale to
restore the positive total. FP32 totals can differ slightly from the exact
rational totals; log residuals against the exact L totals, with
`abs(sum_FP32 - sum_exact) <= 1e-6 * max(1,n)` per HLA. L/P FP32 weight
multisets must also match exactly. Do not retain the old adapter's `sum(weights)=n`
validation for L/P.

The native EL sampler still supplies one positive anchor and sixteen negatives
per batch, with 70,069 updates, 70,069 positive and 1,121,104 negative exposures
(1,191,173 sampled row instances). All original negatives remain eligible; an
epoch does not consume all 1,383,509 negatives. The other 262,405 negatives are
not removed from the population. Each original positive remains an anchor.

For a batch with positive BCE b+ and negative BCE values b-j:

```text
loss_A = (b+ + sum_j b-j) / 17
loss_L_or_P = (w*b+ + sum_j b-j) / 17
```

Retain the original batch-row mean denominator 17, not `16+w` or the sum of
weights. Negative loss coefficients stay 1/17; the positive coefficient becomes
w/17. For a fixed logits/targets comparison the positive logit derivative is
scaled by w, but gradients, loss values and AdamW updates along different
trajectories cannot be inferred from these static weight sums.

| Native one-epoch coefficient accounting | A | L and P |
| --- | ---: | ---: |
| Positive coefficient sum | 4,121.705882353 | 3,864.100210104 |
| Negative coefficient sum | 65,947.294117647 | 65,947.294117647 |
| Positive:negative coefficient ratio | 1:16 | 0.937500229371:16 |
| Mean sum of batch coefficients | 1 | 0.996323542904 |

The positive coefficient total decreases by 257.605672249; the combined
coefficient total decreases by 0.367645710% relative to A. These are coefficient
exposures, not empirical loss reductions or gradient norms. Effective class
balance and overall loss scale change even though labels, sampler probabilities,
row sequences and optimizer steps stay fixed. No class-balance compensation is
introduced. L/P preserve the same epoch totals, but assign weights at different
steps; they need not have identical loss or optimization trajectories.

### All observed HLA groups

Affected fraction uses each HLA's original positive count. Reduction is in
positive-loss weight units before the batch denominator. All groups retain
maximum weight 1. Detailed min/median/mean/max and exact rational totals are in
the external JSON. Table values below are rounded; global sums use exact values.

| HLA | Original EL+ | Affected n | Affected % | Weight reduction | Reduction % |
| --- | ---: | ---: | ---: | ---: | ---: |
| HLA-A*01:01 | 2,017 | 1,008 | 49.9752 | 126.062469 | 6.249998 |
| HLA-A*02:01 | 7,088 | 3,544 | 50.0000 | 443.000000 | 6.250000 |
| HLA-A*02:03 | 1,654 | 827 | 50.0000 | 103.375000 | 6.250000 |
| HLA-A*02:11 | 94 | 47 | 50.0000 | 5.875000 | 6.250000 |
| HLA-A*03:01 | 2,025 | 1,012 | 49.9753 | 126.562469 | 6.249998 |
| HLA-A*11:01 | 1,953 | 976 | 49.9744 | 122.062468 | 6.249998 |
| HLA-A*23:01 | 647 | 323 | 49.9227 | 40.437403 | 6.249985 |
| HLA-A*24:02 | 2,968 | 1,484 | 50.0000 | 185.500000 | 6.250000 |
| HLA-A*24:07 | 864 | 432 | 50.0000 | 54.000000 | 6.250000 |
| HLA-A*25:01 | 314 | 157 | 50.0000 | 19.625000 | 6.250000 |
| HLA-A*26:01 | 533 | 266 | 49.9062 | 33.312383 | 6.249978 |
| HLA-A*29:02 | 4,473 | 2,236 | 49.9888 | 279.562486 | 6.250000 |
| HLA-A*30:01 | 279 | 139 | 49.8208 | 17.437276 | 6.249920 |
| HLA-A*30:02 | 105 | 52 | 49.5238 | 6.561905 | 6.249433 |
| HLA-A*31:01 | 706 | 353 | 50.0000 | 44.125000 | 6.250000 |
| HLA-A*32:01 | 852 | 426 | 50.0000 | 53.250000 | 6.250000 |
| HLA-A*33:03 | 1,384 | 692 | 50.0000 | 86.500000 | 6.250000 |
| HLA-A*66:01 | 98 | 49 | 50.0000 | 6.125000 | 6.250000 |
| HLA-A*68:01 | 588 | 294 | 50.0000 | 36.750000 | 6.250000 |
| HLA-A*74:01 | 1,085 | 542 | 49.9539 | 67.812442 | 6.249995 |
| HLA-B*07:02 | 5,072 | 2,536 | 50.0000 | 317.000000 | 6.250000 |
| HLA-B*08:01 | 2,543 | 1,271 | 49.9803 | 158.937475 | 6.249999 |
| HLA-B*15:01 | 3,969 | 1,984 | 49.9874 | 248.062484 | 6.250000 |
| HLA-B*15:02 | 1,497 | 748 | 49.9666 | 93.562458 | 6.249997 |
| HLA-B*15:10 | 1,075 | 537 | 49.9535 | 67.187442 | 6.249995 |
| HLA-B*15:17 | 77 | 38 | 49.3506 | 4.811688 | 6.248946 |
| HLA-B*18:01 | 849 | 424 | 49.9411 | 53.062426 | 6.249991 |
| HLA-B*27:02 | 1,164 | 582 | 50.0000 | 72.750000 | 6.250000 |
| HLA-B*27:03 | 424 | 212 | 50.0000 | 26.500000 | 6.250000 |
| HLA-B*27:05 | 2,433 | 1,216 | 49.9794 | 152.062474 | 6.249999 |
| HLA-B*35:01 | 1,063 | 531 | 49.9530 | 66.437441 | 6.249994 |
| HLA-B*35:03 | 853 | 426 | 49.9414 | 53.312427 | 6.249991 |
| HLA-B*35:08 | 95 | 47 | 49.4737 | 5.936842 | 6.249307 |
| HLA-B*39:01 | 595 | 297 | 49.9160 | 37.187395 | 6.249982 |
| HLA-B*39:10 | 2 | 1 | 50.0000 | 0.125000 | 6.250000 |
| HLA-B*40:01 | 1,548 | 774 | 50.0000 | 96.750000 | 6.250000 |
| HLA-B*41:01 | 293 | 146 | 49.8294 | 18.312287 | 6.249927 |
| HLA-B*42:01 | 1,813 | 906 | 49.9724 | 113.312466 | 6.249998 |
| HLA-B*44:05 | 2 | 1 | 50.0000 | 0.125000 | 6.250000 |
| HLA-B*45:01 | 916 | 458 | 50.0000 | 57.250000 | 6.250000 |
| HLA-B*46:01 | 1,215 | 607 | 49.9588 | 75.937449 | 6.249996 |
| HLA-B*51:01 | 1,915 | 957 | 49.9739 | 119.687467 | 6.249998 |
| HLA-B*54:01 | 640 | 320 | 50.0000 | 40.000000 | 6.250000 |
| HLA-B*55:01 | 773 | 386 | 49.9353 | 48.312419 | 6.249990 |
| HLA-B*56:01 | 970 | 485 | 50.0000 | 60.625000 | 6.250000 |
| HLA-B*57:01 | 4,371 | 2,185 | 49.9886 | 273.187486 | 6.250000 |
| HLA-B*57:02 | 5 | 2 | 40.0000 | 0.300000 | 6.000000 |
| HLA-B*57:03 | 2,526 | 1,263 | 50.0000 | 157.875000 | 6.250000 |
| HLA-B*58:01 | 1,644 | 822 | 50.0000 | 102.750000 | 6.250000 |

### HLA-B*08:01 and sparse groups

B*08:01 has 2,543 positives, of which 1,271 (49.980338%) are downweighted.
Weights range from 0.757274872198 to 1, median 1, mean 0.937500009665;
its total falls from 2,543 to 2,384.062524577, a reduction of 158.937475423
(6.249999034%). Its positive predicted median was about 0.410 hours, and the
previous descriptive 1-hour region contained 2,530 positives. That historical
absolute region is not used here: the rank rule affects about half this allele,
not almost all of it. Its 74 tied predictions retain equal weights.

Prior internal DTU validation for B*08:01: n=94, Spearman about 0.695, MAE
0.214 hours. These support some ordering on that assay split but supply no EL
repeat-detection calibration; error is material relative to its short timescale.
The rule removes cross-HLA absolute scale from assignment, not Teacher uncertainty.

B*39:10 and B*44:05 each have n=2: exactly one positive is weighted 0.875,
reducing each group's total by 0.125 (6.25%). B*57:02 has n=5: two affected,
minimum 0.8, reduction 0.3 (6%). These three groups together contribute only
0.55 weight units of reduction. There is no disproportionate *fractional total*
reduction relative to larger groups, but one uncertain ranking can determine
half the assignments in n=2 groups; finite-sample ranks and coarse weights make
individual-observation effects particularly unstable. No group is excluded or
shrunk. Even large EL groups can have weak Teacher support: B*35:08 has only
two internal validation measurements; A*32:01 has four. Keep those warnings
without outcome-selected reliability filtering.

## Exactly three candidate conditions and the permutation contract

| Condition | EL positive weights | EL negatives | Original populations/labels | IM |
| --- | --- | --- | --- | --- |
| A: original baseline | All 1 | All 1 | Unchanged | Native unweighted transfer |
| L: low-stability-only | Fixed w_low above | All 1 | Unchanged | Same procedure from own EL parent |
| P: permuted-weight control | L multiset reassigned within each HLA | All 1 | Unchanged | Same procedure from own EL parent |

No fourth condition, new two-sided comparison, additional seed or alternative
permutation realization is authorized. Task 2.17 P cannot stand in for this P:
its multiset includes weights above 1 and conserves the positive total.

For the single future P assignment, reuse the Task 2.12 deterministic permutation
algorithm/stream unchanged, applying it to **L** weights rather than old weights:

1. Sort immutable positive `source_row_id` strings lexicographically per HLA.
2. Seed a local `random.Random` using the big-endian integer of SHA256 of the
   following UTF-8 bytes (NUL separators, seed text `42`, exact resolved HLA):

   ```python
   f'el_positive_weighting_preregistration_v1\0permutation\0{42}\0{hla}'.encode()
   ```

3. Apply descending Fisher–Yates (`j=n-1,...,1`, `k=rng.randrange(j+1)`) to the
   canonically ordered L weight list, then restore source-ID association.
4. Pin Python 3.13.5, as in the existing score manifest/Task 2.17 runtime, and log
   per-HLA assignment digests. No global Python, NumPy or Torch RNG draws,
   reseeding or model/sampler stream advancement are permitted.

Reusing this existing stream fixes one assignment mechanism; it does not execute
another permutation experiment during design. The stream is independent of
training randomness and domain-separated by HLA. It is not a newly sampled
independent replicate of Task 2.17 P. Never redraw to improve apparent decorrelation
or scores; ties/chance may leave assignments unchanged, especially in tiny groups.

Before future execution, require exact per-HLA multisets, sums, downweighted
counts, labels and population equality between L/P (both rational and FP32
multisets). P preserves the global positive total as a consequence. P isolates
the stability-specific ordering from the generic effects of lowering positive
contributions and perturbing their optimization timing. One realization is not
a permutation-test null distribution and does not control unobserved study/donor
or acquisition effects within HLA.

## Matched future GPU experiment

Use the Task 2.17 framework and original data bindings wherever possible, with
only the approved one-sided assignment and condition metadata added in a later
engineering task. This design adds no runnable GPU condition or training config.
Task 2.17's historical training authorization does not authorize A/L/P.

Freeze these requirements before execution:

- EL: all 1,453,578 original observations (70,069 positives, 1,383,509 negatives).
  IM: all 3,428 original observations (955 positives, 2,473 negatives).
- Seed 42; one EL epoch followed by one IM epoch; no resume/checkpoint selection.
  CUDA device 0 FP32, no AMP/TF32, deterministic algorithms and existing
  `CUBLAS_WORKSPACE_CONFIG=:4096:8` setup.
- Authentic pinned BigMHC source `199e890fa69a63646730bcecea0a520e08ca4f02`:
  default mhclen414/minpep8/enclen20/hidlen1024/layers2, 87,444,881 parameters,
  36 state tensors. No architecture or encoding changes.
- Original AdamW: learning rate 0.00005, betas (0.9,0.999), eps 1e-8,
  weight_decay 0.01, amsgrad=False, maximize=False, foreach=None, fused=None,
  capturable=False, differentiable=False, decoupled_weight_decay=True in the
  recorded runtime. Same parameter lists; no scheduler or compensation.
- Native positive-anchored EL sampling, nominal batch size 16 with actual 17-row
  nine-mer batches; batch-row mean weighted BCE. Original IM mean BCE and native
  all-negative skip remain unchanged. Four CPU threads, interop threads 1,
  num_workers=0, persistent_workers=False.
- Identical pre-EL initialization (every tensor hash), Python/NumPy/Torch CPU/CUDA
  RNG boundaries, every ordered sampled source-row/label batch, optimizer-step
  counts, parameter lists and skip masks against A. Check each sampled batch
  before its optimizer update. Retain original identity collation/binding checks.
- 70,069 EL optimizer steps; IM has 215 sampled batches/3,428 observations and
  214 updates, skipping the same all-negative batch 48 (16 negatives), leaving
  955 positive/2,457 negative optimized IM exposures.
- IM loads its own arm's fixed EL checkpoint; identical *procedure* does not
  mean identical trained EL tensors across arms. Only the four original
  `condenser.att`/`condenser.out` weight/bias tensors are optimized in IM.
- Same frozen 383-row development cohort (120 positives, 263 negatives), original
  labels and evaluator in all arms. Development CSV SHA256
  `b4feb0c2765b99f6f845350c60be325895d6d33b184806fd2f2b28801687a2b1`.
  No cohort selection, sealed outcomes or new development predictions in this task.

### Can completed Task 2.17 A be reused?

**Yes, it is an eligible exactly matched baseline for this design, conditional
on preserving and proving the following compatibility at implementation/execution.**
A new A is not scientifically required solely because the positive assignment
changes in L/P. This does not assert that future, unimplemented L/P already match.

Evidence inspected in this task:

- A completed at the exact approved main commit used here. Its saved
  `A/reports/training_configuration.json` equals the current base configuration
  in full, including all input hashes and experimental settings.
- The current adapter SHA256 is
  `0df40226b5a4c3ae4581daa84caf3d82078599270769cf2cdf3561413fc796bf` and runner
  SHA256 is `1599d83613a94801d0563f7a33b31cc738a4c7102b712f72f752db1f6493b65d`.
  Both match the existing Task 2.17 CUDA no-op receipt: unit-weight A and native
  loss/gradients/two synthetic AdamW updates were exactly equal, and RNG/sampler
  identities agreed. Those are historical CUDA checks, not rerun here.
- Task 2.17's completion report records identical 36-tensor initial identities,
  EL/IM RNG boundaries, ordered sampled rows, optimizer settings/parameters and
  skip masks across its arms, with no deviations or failures. A's initial tensor
  digest is `93a6f9104639a93ae41c2b559baf0d2b3a2e433da911c7339d53660ae79d2715`.
- A's saved per-stage source-batch digest sequences, optimizer settings and RNG
  states exist in `A/reports/matched_state.json`. Ordered EL batch-list digest:
  `32a9e94677ef4e1b1f3e7863601155843b623da92e074f4e5802f6a0d7c2e886`;
  IM: `2d84f5d5d6b29ad5c1538c01f297e9a6fa9b2c0fd767d3414ecccef473a1215e`.
- A used Python 3.13.5, Torch 2.13.0+cu130, CUDA 13.0, cuDNN 92000,
  NumPy 2.5.4, pandas 3.0.6, psutil 7.2.2, RTX 4090 on Z790 WSL2.
  Its recorded scientific configuration identity is
  `fcc1d7b396d7ac4cecf47b2d123f8ec549074b3defb63fee0ffd79dfa4c416c1`.
  Its comparison to Task 2.10 had zero loss/prediction differences, though the
  actual reference proposed here is Task 2.17 A.

Pin these existing runs-relative evidence hashes in the future execution record:

| File under `task-2_17-abp-comparison/` | SHA256 |
| --- | --- |
| `A/reports/matched_state.json` | `bfcbdc71c98c732650214c7592e396e526094596329bd0e5aa016aa9823c5cb2` |
| `reports/task2_17_completion.json` | `f5c8bca9daeba69d1f8c35fb07d7d35564b5b8ae2e95120f5db5da27b82df3b0` |
| `reports/cuda_noop_equivalence.json` | `bdcda37c479c91f35300c3b7240f9d7e5c807069d8c509380b3ecfb02a8ea38c` |

**Engineering blocker:** the current runner requires an identical `code_commit`
and adapter version in matched references; validators and launcher recognize
A/B/P and conserve total weight n. They cannot run this design unchanged. A later
approved implementation must preserve A's unit-weight branch and native training
semantics, provide an explicit reviewed cross-commit compatibility record for
this baseline, update only L/P-specific invariants/metadata, and retain all
scientific configuration, tensor, runtime, RNG and batch gates. Never edit old
receipts, spoof commit identity, or disable all reference checks. Separate current
execution provenance from the pinned baseline's historical provenance.

Before any authorized full training, require new focused engineering/no-op
checks on the implementation, with original A loss/gradients/updates and RNG
behavior preserved, and exact reference checks for L/P. If the A path, relevant
runtime, data, sampler, optimizer, precision, schedule or cohort changes, or a
reviewed compatibility proof cannot be provided, **a new matched A is required**
and becomes the sole A reference for L/P. This is a baseline-reuse decision,
not a fourth scientific condition. Neither fallback A nor other training is
executed or authorized by Task 2.18.

## Evaluation and frozen interpretation

Primary endpoint: IM **non-interpolated average precision**, grouping tied scores
at distinct thresholds and summing recall increments times precision, using the
existing evaluator. Do not substitute trapezoidal PR area. Secondary endpoints:
IM AUROC, EL-proxy AP and EL-proxy AUROC. AUROC gives half credit for tied
positive/negative scores. Use fixed one-epoch checkpoints and the same score
representation and evaluator across arms; no score-based checkpoint selection.

Report all four metrics and all three predefined signed contrasts:

| Contrast | Question |
| --- | --- |
| L − A | Does this fixed one-sided intervention improve development prediction? |
| L − P | Does stability-specific assignment add utility beyond this matched reduction? |
| P − A | What is the nonspecific effect of reduced positive contribution and this reassignment? |

Positive L−A and L−P is the directional pattern motivating a separately approved
robustness study. Improvement versus A alone, especially if P does as well or
better, does not establish stability-specific benefit. No significance claim,
permutation-test p-value or generalization conclusion follows from one seed,
one control realization and 383 previously viewed development observations.

A null/negative L−A challenges utility for this exact rule and training budget;
L no better than P challenges assignment specificity. Neither result falsifies
all stability hypotheses: Teacher noise, short training, limited cohort and
optimization variation remain possible explanations. A positive result establishes
at most exploratory development utility for the fixed intervention; it does not
prove label error, estimate reliability or repeat-detection probability, or
establish improved independent-test immunogenicity prediction.

Do not alter formula, coefficient, rank midpoint, controls, permutation, cohort,
training budget or metric definitions after future development scores. No extra
variants, seeds, reshuffling experiments, tuning or sealed independent outcomes.
Any future per-HLA development metrics remain descriptive under Task 2.12's
existing support rule (at least five positives and five negatives); no row is
removed from global metrics for that reporting rule.

## Scientific limitations and approval boundary

1. An MS EL-positive observation records detection. A low predicted kinetic
   stability does not reverse that event or identify a false-positive label.
   Supply, processing, HLA abundance, turnover and acquisition can affect detection;
   presentation, repeat detection and T-cell response are different outcomes.
2. The frozen Teacher consists of allele-specific Ridge models of log1p kinetic
   half-life. It lacks calibrated per-observation uncertainty and EL-domain
   reliability calibration. Ranking noisy predictions can downweight useful true
   positives; capping high weights does not solve incorrect low ranking.
3. Within-HLA ranks remove absolute allele scale but depend on the selected
   positive reference population. Allele-specific support, ranking quality,
   extrapolation, floor ties and assay/source differences remain. The same
   percentile need not have the same biological meaning across alleles. Prior
   Teacher-fitting exposure warnings (305 exact positive peptides and 39 additional
   one-substitution positives) remain; no new filter or audit is introduced.
4. Downweighting positives shifts the positive/negative objective and slightly
   lowers total loss scale under the fixed denominator. Unchanged row counts do
   not imply unchanged effective class balance or training dynamics.
5. The within-HLA matched permutation is necessary to compare assignment against
   generic weight reduction. It cannot equalize every per-step gradient or
   control unobserved study/donor confounding; a single P is a limited control.
6. Null/negative predictive utility does not test whether genuinely measured
   kinetic stability predicts repeated EL detection. A positive result likewise
   does not validate a biological label-correction rule.
7. No run-linked replicate detections, comparable conditions, nondetections or
   acquisition-opportunity denominators are available. The original repeat-detection
   hypothesis remains untested under every possible A/L/P development result.

**Ready for scientific protocol review; not ready for training execution.** Before
training, obtain explicit scientific approval of the exploratory utility claim,
exact rule and unchanged labels/population, A/L/P with reduced positive totals,
fixed independent training-RNG permutation stream, denominator/optimizer/sampler
requirements, baseline reuse gates or new-A fallback, and frozen development-only
endpoints/interpretation. Then separately authorize minimal adapter/launcher work,
validate it, and obtain explicit execution authorization. All those approvals are
pending. No new GPU condition, scientific model training, IM development
predictions, sealed-test access, downloads, backups, merges or pushes occur here;
Task 2.17 results remain untouched.
