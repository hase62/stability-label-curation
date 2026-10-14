# SPEARMINT Stage 2 / original DTU overlap audit (Task 1.3)

This task inventories a pinned release and compares its rows with the immutable
DTU 2016 reference. It does not create independent observations, approve training
eligibility, execute external scripts, load weights, or run a model.

## Source versions and storage

The source registry remains `configs/data_sources.toml`; SPEARMINT remains
`audit_only`. The new `configs/external_repositories.lock.json` records the
requested repository URL, exact commit, acquisition time, branch, Git blob
identities, byte sizes and local SHA256 values of ten relevant files. It pins
external files, not scientific inclusion or publisher-verified checksums.

- Requested repository: https://github.com/dhuvik/spearmint
- Pinned commit: `d548dee9b04dd0e3a9d7a50a593d2c030e31d2a5`, branch `main`.
- Checkout: `resolve_paths().repos_root / 'spearmint'`, a sibling of this project.
- Acquisition: sparse, shallow, blob-filtered HTTPS clone with LFS smudging skipped.
- Required Stage 2 CSVs and reference contain actual payloads, not LFS pointers.
  Unrelated Stage 1/3 data, predictions and model weights are not materialized.
- External checkout remains clean and read-only after acquisition.

Exact snapshots preserve repository-relative paths beneath
`resolve_paths().project_data_dir / 'spearmint_stage2'`. Existing identical bytes
are reused; different bytes or symlinks are rejected. Each new copy is streamed
into a unique partial file, fsynced, and atomically published without replacing
an existing file. Only the invocation's own failed partial is removed. Imports
and default audit inspection never acquire files or create directories.

| Original repository-relative file | Bytes | SHA256 |
| --- | ---: | --- |
| data/binding_stability/train.csv | 8,483,129 | `3ad79db3286688972b47ea96ba96129704367c1f016947a2ecc39c4872520793` |
| data/binding_stability/val.csv | 1,059,966 | `49217866a5d084ecd74150609bd5f0cfb8f6a78ac772ded6f26e1ff427a79dd8` |
| data/binding_stability/test.csv | 1,058,281 | `61d8ab1ae07e75fcf69b8175617ccf1bb43255498f0a8f37882568b2075c953f` |
| refs/2field_hla_consensus_seqs.csv | 3,876,460 | `8969927707689d83656eef7c0f1b59b295e80ee7b202d55ee9904aaa9d947eae` |

The DTU file is never downloaded or modified. Its required local SHA256 is
`5f2c6e82d198705a66974b4e42a0ed1412124c4b1e8f7033c7cd43bbdac07f67`.
The audit verifies it before scientific row analysis and again after comparison.

## Code and publication evidence

`configs/spearmint_stage2_evidence.json` captures scoped evidence and limitations.
All code references below use the pinned commit:

- [Stage 2 configuration](https://github.com/dhuvik/spearmint/blob/d548dee9b04dd0e3a9d7a50a593d2c030e31d2a5/configs/s2_stability_args.json),
  lines 8, 20-21, 28: the binding_stability directory; log_transform enabled;
  stability_score disabled; no validation/test subsampling.
- [Stage 2 loader](https://github.com/dhuvik/spearmint/blob/d548dee9b04dd0e3a9d7a50a593d2c030e31d2a5/src/mint_stability/train_stability.py),
  lines 321-323, 409-425, 438-445: reads train/val/test, applies log1p to CSV labels,
  then constructs datasets. This establishes a runtime target transform, not an
  already-transformed CSV solely from the model output convention.
- [Shared dataset/collation](https://github.com/dhuvik/spearmint/blob/d548dee9b04dd0e3a9d7a50a593d2c030e31d2a5/src/mint_stability/train_binding.py),
  lines 125-145, 155-170: returns fields without another target transform; casts
  labels to float32 and replaces J with L during tokenization. The audit performs
  neither operation on source data. CLI overrides could change training behavior.
- [Input documentation](https://github.com/dhuvik/spearmint/blob/d548dee9b04dd0e3a9d7a50a593d2c030e31d2a5/src/README.md),
  lines 25-49, 81-86: CSV inputs are described using half-life hours and full MHC
  alpha-chain sequences. Root README distinguishes Stage 1 affinity, Stage 2
  stability, and Stage 3 assay conditioning; output log1p is not input proof.

The associated [preprint v1](https://www.biorxiv.org/content/10.64898/2026.06.28.735023v1.full),
DOI `10.64898/2026.06.28.735023`, Section 2.2 / Binding stability data, attributes
stability data to NetMHCstabpan, describes allele normalization and full-sequence
mapping, and reports 27,034 measurements/72 alleles. It separately reports splits
21,626/2,705/2,700, totaling 27,031. It describes log1p modeling and an 80% identity
peptide-cluster split. Discussion acknowledges mutant exclusion. These claims
were verified from primary-page indexed full text; direct HTTP retrieval returned
403, so no byte-exact preprint snapshot exists. Data availability names
`pirl-unc/spearmint`; the explicitly requested `dhuvik/spearmint` release is pinned
here. No second repository was cloned or assumed equivalent.

No preparation, normalization, sequence-reference construction or split-generation
script was found in the pinned tracked tree. Thus the original build procedure,
upstream IPD-IMGT/HLA release, and the aggregate count discrepancy remain partly
unresolved. The preprint's 80% identity and cross-task leakage claims are not
verified by this exact row/peptide audit; Stage 1/3 files were not inspected.

## Actual released schema and label interpretation

All three released CSVs have six columns:
`peptide_sequence,mhc_sequence,label,allele,assay,temperature_C`.
Every observation retains these raw field values, CSV record number, physical
source-line span, and split membership. The snapshot identifies exact bytes;
JSONL records preserve decoded cell text without destructive normalization.

Labels are finite half-life hours. Every matched Decimal label equals the DTU
half-life numerically. Only 353 label strings also match exactly (`1.8` versus
`1.80`, for example, differs textually). `log1p` is applied once in the configured
training script after CSV loading. No released preparation code was found to
establish a prior transformation; the unchanged values are independently observed.
The comparison applies no inverse transform to this release. A supported verified
log1p input uses Decimal exp minus one at precision 50 for comparison only.
Unknown label semantics are retained but excluded from numerical agreement.

All peptides are 9-mers. Released context is SPA at textual temperature `37.0`.
No malformed, missing, non-finite, negative, or noncanonical peptide values were
observed. The inventory also reports MHC lengths/characters, value-type counts,
distinct peptide/sequence/allele strings, and every duplicate-key group.

MHC strings have lengths 181 (1,103 rows), 362 (13,346), or 365 (12,582).
The 181-residue strings belong to HLA-A*02:50 (375 rows), HLA-A*24:19 (378),
and HLA-B*08:03 (350), and match the same named entries in the pinned reference.
This conflicts with treating every released string as a complete ~365-residue
chain. Explicit identifiers plus exact named-reference agreement support the
released mapping, without guessing from partial similarity. No sequence is
completed, repaired, or removed; reference completeness remains a limitation.

| Split | Rows | Exact-zero labels | Positive labels |
| --- | ---: | ---: | ---: |
| Train | 21,626 | 3,790 | 17,836 |
| Validation (val.csv) | 2,705 | 508 | 2,197 |
| Test | 2,700 | 413 | 2,287 |
| Total | 27,031 | 4,711 | 22,320 |

## Mapping and overlap results

The pinned sequence reference has `Allele` and `Full Sequence` columns. All
27,031 released rows carry literal HLA identifiers and sequences exactly matching
that identifier's reference entry. There are 72 mapped identifiers, zero unmapped
rows, and no sequence inconsistencies. A shared sequence need not uniquely name
an allele; an explicit matching name disambiguates aliases. Sequence-only lookup
is accepted only for a unique exact reference entry. No partial similarity,
allele-name repair, or C67S-to-wild-type mapping is implemented.

Every receptor mapping retains raw identifier and sequence, mapped reference
identifier, rule, exact reference provenance, candidate aliases, status, and
limitations. Reference agreement supports the released representation, not
biological equivalence of experimental materials or an audited consensus-build
procedure.

All 27,031 Stage 2 rows match DTU by both strict literal `(HLA, peptide)` and
verified mapped keys. All half-lives are exactly equal as Decimals; maximum,
median and p95 absolute difference are zero hours. Agreement counts are reported
at tolerances 0, 1e-12, 1e-9, 1e-6 and 0.01 hours. None of these tolerances is used
to alter a measurement or certify experimental origin.

Every one of the 72 ordinary DTU identifiers has complete key inclusion: 27,031
ordinary rows are present. No Stage 2 row is absent from DTU. The only DTU rows
absent from Stage 2 are:

| Unchanged DTU identifier | Absent rows | Zeros | Positives |
| --- | ---: | ---: | ---: |
| HLA-B*14:01(C67S) | 374 | 333 | 41 |
| HLA-B*14:02(C67S) | 382 | 286 | 96 |
| HLA-B*39:06(C67S) | 379 | 349 | 30 |
| Total | 1,135 | 968 | 167 |

No C67S rows are mapped to wild-type, and no raw DTU observation is removed.
The released ordinary partition is described, not adopted as an inclusion rule.
There are no within- or cross-split duplicate raw/mapped keys and no exact
peptides shared between splits. These checks do not establish 80% similarity
separation or independence from the Stage 1 affinity corpus.

The preprint's aggregate 27,034 exceeds both its split sum and the released
27,031 by three. No three additional observations exist in the released splits.
A typo or different processing stage remains possible, but neither is established
without missing preparation evidence. The totals are never forced to agree.

The combined evidence supports a released representation of the ordinary DTU
2016 rows, rather than additional independent experimental measurements.
Every matched row is tagged `dtu_matching_released_row_not_independent` while
its measurement origin remains
`published_raw_stability_table_row_origin_unverified`. Zero never implies
synthetic, missing, physical zero, or censoring status. The original DTU assay
and replicate uncertainties from Task 1.2 remain unresolved.

## Offline commands, reports, and provenance

Python 3.11+ standard library only, from this checkout:

```sh
PYTHONPATH=src python3 -B -m stability_label_curation spearmint audit
PYTHONPATH=src python3 -B -m stability_label_curation spearmint audit --json
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
```

Default auditing is read-only and offline. It verifies the pinned external HEAD,
clean tree and relevant bytes, using Git with optional index writes and lazy
fetch disabled. It never imports external modules. Snapshots are preferred;
when absent, pinned-checkout inputs are read and that actual path is recorded.
Explicit `--checkout`, `--train`, `--val`, `--test`, `--mapping`, `--lock`,
`--evidence`, and `--dtu` support offline fixtures or relocated pinned inputs.
Overrides still require matching checksums. `--expected-dtu-sha256` requires an
explicit `--dtu` and must not be used to bypass the canonical primary identity.

Snapshot acquisition is an explicit local-copy API, separate from inspection:

```sh
PYTHONPATH=src python3 -B - <<'PY'
from stability_label_curation import spearmint_overlap_audit as audit
from stability_label_curation import netmhcstabpan_2016 as raw
print(raw.json_report(audit.snapshot_stage2()))
PY
```

Use `--reports-dir /absolute/project/run/reports` only with an existing run
whose manifest explicitly hashes DTU, all three splits and the sequence reference.
The writer rejects existing outputs and unsafe paths/symlinks. Publication is
atomic per file; the final completion/checksum record distinguishes a complete
bundle from interrupted outputs, which are retained without cleanup.

After tests and commit, one canonical run uses the existing `create_run` API,
`kind='source_overlap_audit'`, `inputs=result.inputs`, and the lockfile as config.
All inputs must be in project data/runs for canonical manifest capture; a
checkout-only fallback cannot be recorded as those explicit inputs without
snapshots. The API leaves `external_repositories` empty; the pinned external
commit is recorded in the hashed lockfile, source inventory and execution
evidence without editing the manifest schema or fabricating a record.

Reports include `spearmint_source_inventory.json`, `stage2_split_inventory.json`,
`allele_mapping_evidence.json`, `dtu_stage2_overlap_summary.json`,
`dtu_stage2_overlap_rows.jsonl`, `stage2_unmatched_rows.jsonl`,
`dtu_absent_rows.jsonl`, `stage2_provenance_evidence.json`, and
`overlap_report_checksums.json`. Canonical execution also preserves relevant
source-code evidence, snapshot acquisition receipt, and execution verification.
Per-allele inclusion/exclusion and source-line traceability remain outside Git.
All row outputs are audits, not filtered training tables.

The canonical execution verifies deterministic report/JSONL hashes, unchanged
input bytes, the main-project commit, and unchanged external Git state. Initial
clone/storage restrictions required approved escalation; direct preprint 403 is
recorded as an evidence limitation. macOS execution provides no WSL2/GPU evidence.

Training eligibility, C67S treatment, zero semantics, upstream reference version,
missing preparation history, the three-row preprint claim, and applicability of
dataset licensing remain deferred. Task 1.3 ends at ChatGPT review; no Task 1.4,
training, evaluation, additional dataset acquisition, or Git push is authorized.
