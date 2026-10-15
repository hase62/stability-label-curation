# Stability Teacher v0: first kinetic pilot

Task 2.3 authorizes the first actual Stability Teacher training, using the
approved canonical registry. It does not authorize EL/IM corrections, BigMHC
training or a final D4 split decision. The future study retains the four
original/corrected EL × original/corrected IM conditions from Task 2.2. Original
experimental labels and independent IM test outcomes remain preserved.

## Population and fixed model

[stability_teacher_v0.json](../configs/stability_teacher_v0.json) pins the
Task 1.8 parent run, registry SHA256, source DTU artifact identity and documentary
evidence. Each registry observation is validated using the existing schema.
The selected population must contain exactly 27,031 ordinary human HLA-A/B
nine-mers, 72 identifiers, 4,711 reported zeros and 22,320 positive values.
C67S constructs, Jappe Tm and other sources are outside this pilot. SPEARMINT
aliases never add observations. A mismatch fails rather than forcing totals.

Targets are `log1p(source_reported_half_life_hours)`. Source zeros remain zero;
their underlying measurement/reporting mechanisms remain unresolved. Canonical
records, raw numeric strings and raw source artifacts are never rewritten.

Each exact HLA identifier gets its own `sklearn.linear_model.Ridge`, with:

- 180 float64 positional one-hot features, ordered by position then alphabet
  `ACDEFGHIKLMNPQRSTVWY`; nine residues and 20 canonical amino acids.
- Fixed `alpha=10.0`, unpenalized intercept, `solver="cholesky"`, CPU only.
- No sequence interactions, MHC-sequence features, shared-allele model, ensembling,
  model search or validation-selected hyperparameters.
- Minimum 20 training rows; smaller groups receive an explicit unsupported
  status. Per-allele validation counts below 10 are marked sparse; correlations
  are null whenever sample size or variance cannot support them.

The Ridge objective is squared log-target error plus `alpha * ||weights||²`, as
defined by the [pinned sklearn documentation](https://scikit-learn.org/1.6/modules/generated/sklearn.linear_model.Ridge.html).
Linear algebra is limited to one thread during fitting. Seed 42 controls the
partition; the Cholesky solver itself is deterministic.

Deployed predictions use `expm1(max(0, linear_log_prediction))` in hours. This
prediction floor ensures nonnegative output; it changes no training observations.
MAE in log space uses the deployed, floored prediction, consistent with the
hours prediction. Clipping counts are reported. A predicted zero is a model
output, not evidence about physical instantaneous dissociation.

## Provisional internal hard split

Reuse Task 2.0's complete masked-position index to connect distinct nine-mers
with aligned Hamming distance at most one. Its deterministic connected components
group sequences globally across HLA. Identical peptides on different alleles
therefore always share a partition; transitive component membership is preserved.

Shuffle the deterministic component list with Python `random.Random(42)`.
Traverse it once, adding an entire component to validation only if doing so moves
its observation count closer to the rounded 20% target. Other components go to
training. This uses component sizes, not observed half-life values or predictive
performance. It is not allele-stratified. Infeasible two-partition inputs fail.

The saved partition references immutable observation IDs and component IDs.
A separate complete indexed pass checks exact-peptide and one-mismatch crossings.
Any prohibited crossing fails. Actual row/allele/zero counts, sparse support and
component sizes are retained outside Git. This is the user-authorized pilot rule,
not final D4 approval or proof of study, donor, antigen-family or external-test
independence. Existing DTU/EL/IM exposure from Task 2.2 must still be considered
before later corrections and evaluation.

## Validation and baselines

Report overall, positive-only, reported-zero-only and per-allele validation
metrics: MAE in log1p hours and hours, Spearman in hours, Pearson in hours and
Pearson in log1p hours. Spearman uses average ranks for ties. Constant targets
(including the zero-only subset), constant predictions and fewer than two rows
produce null correlations, not invented values.

Two simple training-only allele-mean baselines clarify the target-space choice:
the mean training log1p target followed by inverse transform, and the arithmetic
mean training hours. Both are evaluated on exactly the Teacher-scored validation
rows. Unsupported validation rows are counted explicitly. No validation values
enter fitting or either baseline. No performance improvement is required for
engineering completion, and results must not prompt repeated tuning here.

## Environment and safe serialization

Optional training dependencies are pinned in
[requirements-teacher-v0.txt](../configs/requirements-teacher-v0.txt): NumPy
2.2.6, SciPy 1.15.3, scikit-learn 1.6.1, joblib 1.5.1 and threadpoolctl 3.6.0.
The actual macOS pilot uses Python 3.13 in the isolated resolver-relative
`data/stability-label-curation/environments/stability-teacher-v0-py313/` environment.
Global Python and unrelated environments are unchanged. Install only into a
new isolated environment using `python -m pip install --only-binary=:all: -r
configs/requirements-teacher-v0.txt`; no PyTorch or pretrained weights are used.

Imports, JSON reload and inference need only the standard library. The model
contains explicit numeric coefficient lists, intercepts, training means, support
statuses, schema/version metadata, input/config/split hashes, committed code
identity and runtime versions. JSON loading validates finite weights and the
supported schema; no pickle, executable payload or external code is loaded.

Synthetic tests on this Mac exposed Accelerate matrix-multiplication warnings
consistent with [NumPy issue 28687](https://github.com/numpy/numpy/issues/28687).
Warnings are captured in `teacher_training_diagnostics.json`, not discarded.
Every fit must have finite weights and pass an independent non-BLAS reduction
check of the Ridge normal equations and intercept stationarity. This is a
numerical verification, not evidence of predictive quality. Actual warnings and
check residuals remain reviewable. Bitwise reproduction across different BLAS,
operating systems or package versions is not guaranteed by macOS testing.

## Commands and run provenance

Use the isolated environment's Python executable with `PYTHONPATH=src`.
First commit the implementation and create one run using the established
`runs create` command or `run_manifest.create_run` API, with:

- Kind `stability_teacher_training`, seed 42 and configuration
  `configs/stability_teacher_v0.json`.
- Explicit inputs: the Task 1.8 canonical observations JSONL, parent manifest and
  source evidence manifest, all identified by the configuration's pinned hashes.

Paths are resolved using `stability_label_curation.paths`, without machine-specific
home directories. An example run creation using the supported API is:

```python
import sys
from stability_label_curation import run_manifest as runs
from stability_label_curation import stability_teacher as teacher
from stability_label_curation.paths import resolve_paths
p = resolve_paths()
c = teacher.load_config(p.repository_root / teacher.CONFIG)
parent = p.project_runs_dir / c['parent_registry_run_id']
inputs = [parent / c['registry_relative_path']]
inputs += [parent / e['relative_path'] for e in c['parent_evidence']]
run = runs.create_run(paths=p, kind='stability_teacher_training', seed=c['seed'],
    config=p.repository_root / teacher.CONFIG, inputs=inputs, argv=sys.argv)
print(run)
```

Then use the printed directory:

```sh
PYTHONPATH=src python -B -m stability_label_curation teacher train --config configs/stability_teacher_v0.json --out <run-directory>
PYTHONPATH=src python -B -m stability_label_curation runs validate <run-id>
PYTHONPATH=src python -B -m unittest discover -s tests -v
```

Training refuses existing model/report artifacts. Generated files include
`checkpoints/teacher_model.json` and reports for the train/validation partition,
validation metrics, allele coverage, leakage audit, numerical diagnostics and
execution checksums. Model reload must reproduce predictions for every authorized
observation. The run records derived registry inputs; it does not claim to have
trained directly from independently re-audited raw measurements.

`teacher evaluate --model <model.json> --out <evaluation-run-directory>` evaluates
the saved partition without fitting. Its separate output run must record hashed
inputs for the model, saved partition and all registry/evidence inputs. An
explicit `--partition` override remains gated by the model's saved partition hash.
Direct `evaluate()` permits reproduction inside the original run without creating
an unnecessary second canonical run.

`teacher predict --model <model.json> --input <small.csv> --out
<prediction-run>/predictions/output.csv` accepts exactly `peptide,hla` columns,
not scientific labels. Its run must record the model and input CSV hashes.
Explicit registry overrides for training/evaluation remain configuration-checksum
gated and support temporary synthetic fixtures.

## Inference contract and limitations

`Teacher.predict_stability(peptide, hla)` and `predict_batch()` return predicted
hours, model status, exact resolved HLA, version and an unsupported reason.
Only a trained exact ordinary HLA-A/B identifier, nine residues and canonical
amino acids are supported. No nearest HLA, mutant-to-wild-type conversion, padding,
truncation or zero substitution occurs. Unsupported values have null predictions.
The future correction pipeline must leave them unchanged by default; this task
implements no correction pipeline.

A per-allele additive pilot cannot predict unseen alleles or learn residue
interactions. Short-sequence component separation does not recover unavailable
study metadata. No predictive result establishes zero semantics, independently
verified experimental traces, calibration outside the source or a correct EL/IM
pseudolabel threshold. Engineering completion and sufficient information for a
correction pilot are separate judgments to report after the single held-out run.
