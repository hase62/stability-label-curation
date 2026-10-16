# Task 2.13: source-ID-safe EL loss adapter

This is engineering preparation for the [approved A/B/P protocol](EL_POSITIVE_STABILITY_WEIGHTING_PROTOCOL.md).
No real EL/IM training, development predictions, label changes or new scientific
choice is part of this task. The shipped configuration has
`loss_adapter.training_authorized=false` and refuses to start a training worker.
Historical LOW/HIGH overrides and corrected views remain forbidden.

## Score sidecar and alignment

The score-only artifact contains exactly **70,069 original EL positives from 49
HLAs**, aligned to the **1,453,578-row original-label Task 2.5 cohort**. The frozen
Task 2.3 Teacher's predictions were saved by Task 2.4; they are reused, not
recomputed. The existing Task 2.5 purge accounts for the 55 removed scored rows
(13 positives, 42 negatives). Original labels and observations remain intact.

Canonical run, relative to the project runs root:
`task-2_13-el-stability-weight-adapter/`.

- `processed/el_positive_teacher_scores.csv.gz`: deterministic gzip, mtime 0,
  no source filename embedded; compressed size **7,272,684 bytes**.
- `reports/positive_score_manifest.json`: schema, counts, units, original source
  identities, portable paths, input hashes, Teacher hash and artifact hash.
- `reports/weight_invariants.json`: A/B/P distributions, exact rational totals,
  FP32 residuals and source-ID assignment digests.
- `reports/authentic_noop_equivalence.json`: authenticated-source CPU synthetic
  forward/backward and native sampler checks, zero authentic optimizer steps.
- `reports/execution_verification.json`: committed code, actual inputs and outputs.

Sidecar CSV fields:
`prepared_row_index,source_row_index,source_row_id,source_row_sha256,original_hla,resolved_hla,original_peptide,original_label,predicted_half_life_hours`.
The manifest fixes `source_member=el_train.csv`, `original_label=1`, units `hours`
and scale `untransformed_kinetic_half_life_hours`. It records the frozen Teacher
hash; the numeric text is retained. A predicted zero is a model output, not a
claim of instantaneous dissociation or an incorrect EL label.

Preparation reuses the Task 2.11 three-way alignment: archive/member/original-row
index and raw-row hash, all original fields, validated HLA, Teacher identity and
contiguous retained-row index must agree. Peptide/HLA alone never replaces an
observation identity. The sidecar does not contain development outcomes, test
labels, scores for IM, corrected labels or fitted Teacher weights.

The manifest uses `data`/`runs` areas and project-relative paths. Its historical
input references document provenance; they are not instructions to transfer the
Teacher's training artifacts. WSL2 needs the existing 21 baseline inputs plus
**only the score CSV and its manifest**. The native runner's full input manifest
will additionally record its matched A reference for B/P.

## Weighting and sampling contract

`el_stability_loss_adapter.LossAdapter` reuses the protocol's exact Decimal ties,
rational midrank calculation and per-HLA domain-separated permutation. Mode A is
unit weights. B uses `r=(below+tied/2)/n`, `w=1+0.5*(r-0.5)` for original positives.
P uses exactly the same per-HLA weight multiset, with source-ID-based reassignment.
Every negative weight is 1; no target, class membership or selection probability
changes. Sparse HLA groups remain included; singleton or all-tied groups have
unit weights. Unexpected unsupported, missing, duplicate, ambiguous or nonfinite
positive scores fail closed, including in adapted A.

Rational totals are exactly n per HLA. Weights are converted to FP32 once;
float64 diagnostic totals must satisfy `abs(sum-n)<=1e-6*max(1,n)` without
recentering. The Python version for the local permutation is pinned in the
sidecar manifest (**3.13.5** for this preparation). A different Python version
fails closed; it requires a matching runtime or a separately approved protocol
amendment, not an unrecorded change of permutation. No global Python, NumPy or
Torch RNG is used to assign weights. B/P assignment digests match Task 2.12.

`IdentityDataset` delegates native `makebats`, `__getitem__` and encoding. Two
auxiliary columns carry source ID and a binding digest through native DataFrame
shuffle/reset operations. They are not model features or grouping keys. It
checks original source coordinates and labels before binding; sampled fields,
encoded target order and identity are checked again before loss computation.
Duplicate peptide/HLA strings can remain distinct observations. Weights are
looked up by source ID after sampling, never by the mutable DataFrame position.

For EL only, loss is `mean(weight * unreduced_BCEWithLogits)` over batch rows.
It is not divided by sum of weights and does not use `pos_weight` or a weighted
sampler. The current full population still yields one positive plus sixteen
negatives per native batch (nominal batch size 16), 70,069 EL updates. Architecture,
AdamW defaults, parameter lists and native IM mean loss/all-negative skip rule
remain unchanged. The IM identity wrapper carries no loss weights. Unconfigured
legacy runner paths still use the original Dataset and native mean BCE directly.

## Future matched run configuration

[el_stability_weight_adapter_v1.json](../configs/el_stability_weight_adapter_v1.json)
is an original-label, full-population CUDA profile for adapted A, with pinned
sidecar inputs and execution deliberately disabled. The exact adapter block is:

```json
{
  "schema_version": 1,
  "version": "el_stability_loss_adapter_v1",
  "mode": "A",
  "protocol_version": "el_positive_weighting_preregistration_v1",
  "strength": "0.5",
  "seed": 42,
  "training_authorized": false,
  "matched_reference": null
}
```

After separate execution approval, a new A must define the reference. For B/P,
set both the top-level condition and adapter mode to B/P and pin A's
`reports/matched_state.json` using `area=runs`, `relative_path` and SHA256.
An unresolved or absent A reference cannot authorize B/P. All base populations,
sidecar identities, seed 42, learning rate 5e-5, FP32, one epoch per stage, batch
size argument 16, zero workers, native sampling and original IM labels stay fixed.

The runner verifies more than the seed:

- All 36 initial tensor hashes must equal the new adapted A reference.
- Python/NumPy/Torch CPU/CUDA RNG boundary hashes before EL and IM must match A.
- Each batch's ordered `(source_row_id,original_label)` digest must match A
  **before that batch's optimizer update**. A count/sequence mismatch aborts.
- EL/IM update counts (70,069 / 214), full native skip masks, complete optimizer
  defaults and updated-parameter lists must match the reference.
- Committed code, pinned source, all original input hashes, relevant training
  configuration, package versions and device must match.
- Each IM child inherits its own trained EL parent through the existing four-tensor
  overlay on the full 36-tensor checkpoint. Existing tensor-only CPU-map loading
  and same-device prediction reload checks remain in force.

B/P have deliberately different trained EL weights, not different pre-EL initial
weights. There is no attempt to force equal gradients or to reuse Task 2.10 as an
exact matched baseline. Native sampler behavior is not redesigned. A training
failure or mismatch is not permission to alter population, skip schedule or loss
normalization. No future training has been exercised by this task.

## Reproduction and CPU checks

Inspect deterministic sidecar metadata without writing:

```sh
PYTHONPATH=src python3 -m stability_label_curation.el_stability_loss_adapter
```

With an existing clean committed audit run recording all actual inputs, pass
`--out <run-directory>` to publish the score CSV, manifest and weight evidence
without overwriting existing files. `--out ... --verify-existing` recomputes bytes
and hashes without replacement. Use the existing project path resolver on both
Mac and WSL2; imports and default inspection create no directories.

Run focused tests in the existing CPU BigMHC environment:

```sh
PYTHONPATH=src <bigmhc-runtime-python> -m unittest discover -s tests \
  -p test_el_stability_loss_adapter.py -v
```

Standard-library tests use synthetic score/provenance fixtures. Tensor tests
need the existing CPU PyTorch/pandas environment and otherwise skip explicitly;
no packages are installed. The complete suite is also exercised with those
runtime packages and the existing Teacher environment's scientific packages
available together, so tensor checks are not left unexecuted.

The optional `synthetic_noop_evidence()` function authenticates four existing
pinned source files and runs the authentic architecture on a **synthetic** fixed
17-row batch. It compares legacy and adapted-A forward/backward on the same
initial state and dropout RNG state. Native batching of 272 unique synthetic
peptides verifies the one-positive/sixteen-negative layout and A/B/P schedules.
Authentic model parameters are never optimized or saved; no development
predictions are generated. A separate tiny linear fixture checks identical
AdamW parameter updates. These are engineering equivalence checks, not scientific
training or performance estimates.

## Dropbox handoff and remaining approval

The optional Downloads archive contains exactly two regular files with
`codex/runs/stability-label-curation/task-2_13-el-stability-weight-adapter/...`
member paths: the score CSV and score manifest. It excludes raw archives,
Teacher models, historical overrides, corrected views and all evaluation files.
A Linux-compatible `.sha256` sidecar authenticates the archive. On WSL2, verify
with `sha256sum -c <archive>.sha256`, inspect its members, and extract with
`tar -xzf <archive> -C ~`. A portable transfer inventory is recorded under reports.
The existing 21 baseline inputs are not duplicated or changed.

No WSL2/CUDA validation has been performed on Mac. Deployment still requires
approved publication of this task's code, transfer/checksum verification,
matching the pinned Python permutation runtime, and a separately authorized
fresh A followed by matched B/P. Scientific training approval remains pending;
no evidence here establishes improved IM prediction or EL-positive mislabeling.
