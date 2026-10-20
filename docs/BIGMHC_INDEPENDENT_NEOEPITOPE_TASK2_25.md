# Task 2.25 — Independent neoepitope evaluation: stopped at provenance gate

Status: **stopped before outcome access or model inference**, 2026-10-20,
on Z790 WSL2 / RTX 4090. The authorized independent evaluation was **not run**.
No scientific conclusion about A/S/P performance is available.

Published `origin/main` and local `main` both matched approved commit
`87ca050e272021ec291f78be1e9e19b0c40961bf` after `git fetch origin`.
No main update was necessary. Work is on
`task/2.25-independent-neoepitope-evaluation`; no merge or push was performed.

## Missing dependency and required stop

The [locked protocol](BIGMHC_INDEPENDENT_ASP_EVALUATION_PROTOCOL.md) defines
one observation as one documented experimental peptide–HLA assay. It requires
identifying repeated copies of the same assay, retaining distinct assays, and
checking shared training observation, assay and material source provenance.
It explicitly states:

> Unresolvable assay identity or provenance is quarantined before scoring.

> Unknown material provenance is quarantined pending label-blind resolution.

The authentic release's `im_test.csv` header contains `mhc`, `pep`, `tgt` and
predictor output columns. There are **no original assay identifiers, study or
source-dataset identifiers, patient/specimen identifiers, or a row-to-assay
crosswalk** in that schema. The archive inventory contains eight CSV members:
`el_test`, `el_train`, `el_val`, `im_test`, `im_train`, `im_val`, `iedb`, and
`summary`; it contains no provenance sidecar. The available publication and
release metadata establish collection-level origin, but do not authenticate
an original experimental assay for each released row.

The missing dependency is an **authenticated, outcome-blind crosswalk from
the exact released benchmark rows to original experimental assays and their
study/material provenance**, sufficient to resolve duplicate assays and shared
training-source observations/material. Patient identifiers may remain unavailable
under the protocol's peptide-only bootstrap fallback; that fallback does not
resolve an unknown original assay or material origin. A released CSV line number
alone cannot establish whether two rows are copies of one assay or distinct
assays. Exact peptide novelty alone cannot certify the required provenance.

No mapping was invented from peptide/HLA, no reconstructed benchmark was used,
and no source or exclusion rule was relaxed. Scientific execution stopped at
this dependency. The blocker is not an observed small cohort or an unfavorable
result. No further source acquisition or evaluation was attempted after it.

## Exact source acquisition and isolation

The source is [BigMHC Training and Evaluation Data, Version 4](https://data.mendeley.com/datasets/dvmz6pkzvb/4),
DOI `10.17632/dvmz6pkzvb.4`, published 14 April 2023, CC BY 4.0.
The [publication's neoepitope methods](https://pmc.ncbi.nlm.nih.gov/articles/PMC10569228/)
describe curation from NEPdb, Neopepsee, TESLA and MANAFEST. The release member
for the combined neoepitope benchmark is `im_test.csv`; the infectious-disease
member was not substituted or opened. A MANAFEST-only subset was not substituted.

The archive was absent from configured project storage. The existing
`bigmhc_v4_audit.fetch` acquisition procedure retrieved only `datasets.zip` from
the exact documented Mendeley Version 4 URL. HTTP 200, server length and local
SHA256 matched the pinned release:

- Archive bytes: **144,274,974**.
- SHA256: `0d152a452756cf2e0014ffced6afc25118e7c11cf1f626b26e49f50f79edffaa`.
- Retrieval completion: `2026-10-20T00:33:19.548567Z`.
- Member: `im_test.csv`, **279,819 uncompressed bytes**, ZIP CRC32 `9b37e4c2`.

`reports/source_acquisition.json` retains the original/resolved URLs, timestamp,
HTTP metadata, size and checksum. Archive bytes are under resolved project data /
`bigmhc_v4/datasets.zip`. Nothing was extracted. The inspection read only the
neoepitope CSV header and ZIP directory metadata. **Zero benchmark data records,
outcome values or published prediction values were inspected.** ZIP inventory
role strings in `source_schema.json` come from the older training-source inventory
helper; they do not indicate that those member payloads were opened in this task.

## Focused preflight and frozen model identities

The [identity gates](../src/stability_label_curation/bigmhc_independent_preflight.py)
authenticate the unchanged protocol SHA256
`cb386443d768fb168366299ae7125aeec7115dda4e81da2dce62d90b4b99d250`,
the Task 2.24 freeze receipt, its scientific code/configuration hashes, all
three final IM file maps, and the shared pinned BigMHC source/HLA mapping.
The Task 2.24 receipt states no prior independent benchmark access or internal
developmental model evaluation; this task obtained no independent results.

| Arm | Final IM checkpoint under project runs | Canonical file-map SHA256 |
| --- | --- | --- |
| A | `task-2_23-el-multiepoch-baseline/checkpoints/final_all_IM` | `b92308ab3e35d02530867053ada7e29ee18076bf653df26458f5c3728a2be3a0` |
| S | `task-2_24-fully-trained-stability-auxiliary/checkpoints/S_IM_epoch_20` | `9d5a5012d38b0f7f7203c35769a5a29e35572ced3b8f708a525c03a99996862a` |
| P | `task-2_24-fully-trained-stability-auxiliary/checkpoints/P_IM_epoch_20` | `01014a37c3a4101f90d7765e48420a463a7094169a8c0163fc5994dc4a0c903b` |

All three are the frozen EL-10 / full-IM-20 models fitted on all 3,428 original
IM observations. **All 36 tensors per arm reloaded on CUDA with exactly the
frozen tensor hashes**, in FP32 and eval mode, without auxiliary heads or hooks.
The same pinned transformation source and exact HLA reference authenticate for
every arm. There were **zero forward passes** and no optimizer construction.

Six focused standard-library tests passed, with zero failures/errors/skips:

```text
PYTHONPATH=src python3 -B -m unittest discover -s tests -p test_bigmhc_independent_preflight.py -v
Ran 6 tests in 0.001s — OK
```

These check header-only inspection despite malformed sealed data, non-target
member rejection, missing members, ambiguous headers, bounded header reads,
and canonical model file-map hashing. Actual CUDA reload and authenticated
release inspection are additional executed integration evidence.

Preflight is **partial**, not passed for evaluation: cohort identity/order,
disjointness, metric tie examples, prediction finiteness/record association and
outcome quality cannot be completed past the provenance stop. No metric or
bootstrap execution occurred.

## Counts, metrics and scientific interpretation

| Requested quantity | Status |
| --- | --- |
| Locally enumerated source observations / valid 9-mers | Not determined; data rows remain sealed |
| Sequential and overlapping exclusion counts | Not determined; provenance eligibility unresolved |
| Peptide/pair overlaps with full EL train, full IM train, EL validation, Teacher or development | Not computed |
| HLA coverage, duplicates, assays, patients, clusters and sequence similarity | Not computed |
| Frozen ordered primary/secondary eligible identities | Not established |
| Primary and secondary N, positives, negatives and prevalence | Not determined |
| EL/IM exact peptide-disjointness | Not established; no eligible cohort is claimed |
| Primary AP, AUROC, Precision@10, Precision@20 for A/S/P | Not evaluated |
| IM-novel / EL-exposed subgroup AP and AUROC for A/S/P | Not evaluated |
| S−A, S−P, P−A for every endpoint; bootstrap intervals | Not evaluated |
| Prevalence-derived random-ranking AP baseline | Not determined |

Unknown cohort counts are not zero eligible observations. Uncomputed metrics are
not numerical zeroes or metrics rendered undefined by an observed class balance.
No outcomes were opened to establish class balance. No prediction, comparison,
or favorable-subset file exists. Machine-readable unavailability reasons are
in `reports/evaluation_not_run.json`.

There is no evidence here that S improves AP over either A or P, on globally
unseen peptides or any other independent cohort. Consistency with prior
developmental findings and performance relative to random ranking cannot be
assessed. Stability-specific and generic auxiliary-learning effects remain
unresolved. Prior one-epoch findings and Task 2.23 developmental improvements
remain historical development evidence. Their original results are unchanged.
Teacher-derived kinetic-stability predictions are not measured label errors,
EL repeat-detection probabilities, or thermal melting measurements. No broad
generalization, practical improvement or significance claim is supported.

## Runtime, artifacts and stop boundary

Actual environment: Python **3.13.5**, PyTorch **2.13.0+cu130**, NumPy **2.5.4**,
CUDA **13.0**, cuDNN **92000**, Linux **6.18.33.2-microsoft-standard-WSL2**,
NVIDIA **GeForce RTX 4090**, four CPU threads. Deterministic algorithms enabled,
CUDA FP32, AMP and TF32 disabled. No dependencies were installed.

| Executed engineering stage | Wall seconds | Peak host RSS bytes | Peak Torch GPU allocated / reserved bytes |
| --- | ---: | ---: | --- |
| Model authentication and exact CUDA reload | 7.427895986998919 | 1,554,731,008 | 406,828,032 / 450,887,680 |
| Archive authentication and header-only receipt | 0.9675753259798512 | 653,254,656 | No GPU work |

These times are preflight execution, excluding acquisition/approval/implementation
time; no evaluation runtime exists. GPU figures are Torch allocator peaks, not
system utilization or power measurements. Host RSS is each process's high-water
mark. No GPU utilization/power trace was collected for this stopped preflight.

Artifacts resolve through `stability_label_curation.paths` to project runs /
`task-2_25-independent-neoepitope-evaluation/`. They include original source
acquisition provenance, `models.json`, `source_schema.json`, focused-test evidence,
the stop receipt and a finalization manifest. Code, tests and this documentation
are committed; data/checkpoints and derived run receipts remain outside Git.

**No training, tuning, calibration, model/checkpoint selection, additional seed,
benchmark prediction, metric computation, or outcome-based eligibility change
occurred.** No 383-row development or 686-row fitting data substituted for an
independent benchmark. No existing result was modified. Work stops at the
missing provenance dependency; the single frozen comparison has not been used.
