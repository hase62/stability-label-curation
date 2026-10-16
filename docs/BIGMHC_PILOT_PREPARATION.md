# Task 2.5: leakage-controlled nine-mer BigMHC pilot preparation

This task prepares data for four future conditions, without training a model:
A original EL → original IM; B candidate EL → original IM; C original EL →
candidate IM; D candidate EL → candidate IM. Original experimental/publisher
labels remain in the immutable archive and the derived provenance ledgers.
A candidate IM target does not supersede an experimentally assayed outcome.

## Frozen inputs and scope

[bigmhc_pilot_v0.json](../configs/bigmhc_pilot_v0.json) pins the Task 2.4 input
configuration and additional source/score/report checksums. Paths use the project
resolver; there are no machine-specific paths in configuration. Inputs include
the frozen Teacher and fitting partition, canonical DTU registry, validated HLA
mapping, publisher archive, receptor reference, both training score ledgers and
sparse overrides, parent receipts, saved Teacher metrics, and the pinned
BigMHC `dataset.py` and `cli.py`. The parent scoring receipt authenticates the
score artifacts. The Teacher receipt authenticates its saved validation metrics.
No Teacher fitting or complete rescoring occurs.

Only canonical nine-mers with explicitly mapped ordinary HLA-A/B identifiers,
one unambiguous receptor-reference entry and a trained Teacher model are eligible.
The 67 trained Teacher alleles define a support ceiling, not an assertion that
all appear in every selected source. No fuzzy fallback or mutant mapping occurs.
Unsupported rows are counted with mutually exclusive reasons. Missing scores for
otherwise eligible rows cause failure rather than silent exclusion or rescoring.

Only `im_val.csv`, `el_train.csv`, and `im_train.csv` payloads are opened.
Central-directory inspection and hashing archive bytes do not parse sealed test
payloads. `el_val.csv`, `el_test.csv`, `im_test.csv`, `iedb.csv`, and `manafest.csv`
are not opened by this preparation command.

## Provisional development cohort and training purge

The fixed rule is global nine-mer Hamming distance ≤1, across all HLA identifiers.
It is a pilot protection rule, not final approval of a hard-split methodology.

1. Test IM validation sequence/HLA eligibility without using its label.
2. Exclude eligible validation peptides with exact or one-substitution exposure
   to the frozen Teacher's **actual fitting** peptides. DTU rows assigned to a
   sparse, untrained allele are not actual fitting observations.
3. Retain the remaining development rows, unchanged, including their labels.
4. Remove every eligible EL/IM training row with exact or one-substitution
   sequence proximity to any retained development peptide.
5. Independently verify Teacher/development separation by enumerating canonical
   single-residue substitutions against fitting-peptide membership. Verify every
   training purge decision against a separately constructed complete substitution
   neighborhood of the retained development peptides.

The masked-position index reuses Task 2.0/2.4 sequence primitives. The independent
substitution checks avoid all-pairs comparisons. Transitive cluster closure is
not imposed by this task: it protects direct development exposure under the
specified rule, without constructing final training/validation/test splits.
No donor/study independence is established; such metadata remain unavailable.

The preliminary read-only cohort check found 383 retained rows, 380 unique
peptides, 31 HLA identifiers, 120 positives and 263 negatives. Of 688 source rows,
17 have exact fitting-peptide exposure, one has one-mismatch exposure, and 287
fail sequence/HLA eligibility. These counts are verified again during canonical
execution. This is a restricted development cohort, dominated by HLA-A*02:01;
it is not the final independent experimental evaluation population.

## Reversible views and source-row authentication

For each training member the adapter streams original publisher rows and the
sorted, authenticated Task 2.4 scores/overrides. It verifies:

- Archive/member SHA256, source data-row index and physical CSV line number.
- Original HLA, peptide, label and a SHA256 of the complete original CSV fields,
  including IM `rand`, together with the original header.
- Exact validated HLA resolution, Teacher/rule identity and fixed threshold action.
- Every eligible row has exactly one score; every changing score has exactly one
  identical sparse override. Duplicate, extra, missing and mismatched joins fail.

Selection/purging occurs once. All label views write the same retained rows in
source order, using `mhc,pep,tgt`. `mhc` is the validated ordinary HLA identifier;
raw HLA spelling remains in provenance. Original, LOW-only and LOW+HIGH views are
all materialized. LOW means predicted hours strictly below 1; HIGH means at least
10 hours. The thresholds are frozen, unvalidated engineering defaults.

The provenance CSVs retain original fields, source-row identities/hashes,
source/derived row indices, prediction, candidate reason, original label, both
alternative labels, and retained/purged status. Unsupported source rows are
counted by reason, while their immutable original contents remain in the archive.
The development provenance ledger records all validation rows and exclusions.
Training overrides are forbidden for development/test rows or purged rows.

## Artifacts and integrity

Under the selected run's `processed/` directory:

- `el_train_{original,low_only,low_and_high}.csv`
- `im_train_{original,low_only,low_and_high}.csv`
- `el_train_provenance.csv.gz`, `im_train_provenance.csv.gz`
- `im_development.csv`, `im_development_provenance.csv.gz`

Reports include training inventories, development inventory, independent leakage
checks, the A–D experiment manifest, focused B*08:01 diagnostic, loader contract,
and execution receipt. All generated files stay outside Git. Atomic publication
never replaces an existing artifact; gzip uses zero timestamp and no filename.
A hash-only replay regenerates all bytes without rewriting outputs. Inputs are
hashed before and after execution. A failed run is not a completed preparation;
use the complete execution receipt and successful replay as completion evidence.

## B*08:01 and extreme-shift review

The focused diagnostic reads the DTU registry's original B*08:01 values and the
saved Teacher validation metrics; it does not evaluate a refitted model. It
summarizes saved positive-training predictions before purging, confirms explicit
HLA mapping and reports allele/direction changes after purging. Groups changing
at least 20% of an original class are flagged; groups changing at least 90% are
marked extreme in the experiment manifest. Neither threshold changes eligibility
or correction thresholds. All such observations remain present in every view.

Task 2.4 reported LOW candidates for 2,530/2,543 EL B*08:01 positives and 22/22 IM
positives. Low predictions do not prove those experimental positives wrong.
**Review extreme groups before using candidate labels in an actual training run.**
The preparation can be complete while that scientific decision remains pending.

## BigMHC loader contract and next execution requirements

The input contract follows pinned BigMHC commit
`199e890fa69a63646730bcecea0a520e08ca4f02`, `Dataset.readPMHCs` in
`src/dataset.py:195–295`: header skipped once, allele/peptide/target positional
columns 0/1/2, uppercase peptide, numeric binary target. Reference inspection
validates 414 binary features and unique HLA identities. A bounded standard-library
CSV contract smoke check reads up to 128 rows from each generated CSV. No BigMHC
module is imported or executed; the full PyTorch/pandas loader remains to be tested
in an authorized compatible training environment. No dependencies are installed.

The pinned sampler groups by peptide length, not by allele. Every materialized
view must retain both classes in the nine-mer group. Per-allele class shifts are
reported but not automatically repaired. Equal epochs do not imply equal data
exposure; sampler equalization and optimizer-step controls are deferred.

The intended seed is 42. Pinned `cli.py:238–242` hardcodes seed 1, so a future
training entry point must explicitly set/verify seed 42 instead of assuming an
unsupported `--seed` flag. Establish common initialization for original/candidate
EL models. Transfer from the corresponding EL parent with the selected IM view;
the pinned transfer loader's parent-directory weight inheritance must be preserved
and recorded. Do not start from an already IM-trained published checkpoint.

For a subsequent authorized training task, use the A–D manifest to select paths;
loader arguments are `--input <view.csv> --tgtcol 2 --hdrcnt 1 --pseudoseqs
<verified-reference.csv>`. EL training starts without `--models`; IM transfer uses
`--models <corresponding-EL-parent>`. A seed-controlled wrapper, the compatible
training environment, an explicit training budget and extreme-shift review are
still required. Task 2.5 runs none of those commands and chooses no budget.

## Reproduce offline

After committing code, create exactly one canonical run and prepare it:

```python
from stability_label_curation.paths import resolve_paths
from stability_label_curation import bigmhc_pilot_adapter as adapter, run_manifest

paths = resolve_paths()
config_path = paths.repository_root / adapter.CONFIG
config = adapter.load_config(config_path)
_, inputs = adapter.resolve_inputs(config, paths)
run = run_manifest.create_run(
    paths=paths, run_id="task-2_5-bigmhc-pilot-preparation", kind="pilot_data_preparation",
    seed=42, config=config_path, inputs=[item["path"] for item in inputs],
    argv=["Task 2.5 canonical pilot preparation"],
)
adapter.prepare(config_path=config_path, out=run, paths=paths)
adapter.prepare(config_path=config_path, out=run, paths=paths, verify_existing=True)
```

Existing runs are never overwritten. CLI equivalents on an existing hashed-input
run are:

```sh
PYTHONPATH=src python3 -B -m stability_label_curation pilot-prepare --config configs/bigmhc_pilot_v0.json --out <run-directory>
PYTHONPATH=src python3 -B -m stability_label_curation pilot-prepare --config configs/bigmhc_pilot_v0.json --out <run-directory> --verify-existing
```

`--input INPUT_ID=PATH` accepts explicit checksum-pinned fixture paths. The command
requires an explicit run directory and never writes by import or path resolution.
Preparation writes only to the selected project run; replay is read-only.
