# NetMHCstabpan 2016 source evidence (Task 1.2)

Task 1.2 is an offline, non-destructive audit of the Task 1.1 artifact. It does
not approve training eligibility, label individual measurements, or alter raw
values. Complete generated summaries and row flags belong in project runs.

## Provenance chain and captured evidence

The source registry remains `configs/data_sources.toml`, ID
`netmhcstabpan_2016`. [DTU's official supplementary page](https://services.healthtech.dtu.dk/suppl/immunology/NetMHCstabpan-1.0/)
links its stability table to [Rasmussen et al. (2016), DOI 10.4049/jimmunol.1600582](https://pmc.ncbi.nlm.nih.gov/articles/PMC4976001/).
The Task 1.1 receipt records the acquisition; the Task 1.2 checksum gate pins
those locally observed bytes, independently of publisher checksum verification.
No publisher-provided checksum is available.

The PMC HTML article and DTU landing page were captured through standard-library
HTTPS. Their exact byte sizes and SHA256 values are recorded in
`configs/netmhcstabpan_2016_evidence.json`. This small, version-controlled evidence
configuration contains concise claims, source locations, scope, limitations,
and all 75 Table II entries; it is not a second source registry. Full publication
HTML stays outside Git and is retained with the canonical run reports.
The web browser returned a PMC challenge; direct HTTPS succeeded. DTU manuscript
text corroborated the relevant sections, but direct PDF retrieval returned 403.
No local user-uploaded PDF was assumed or used.

## Verified publication statements and boundaries

The evidence register records precise Methods/Table locations, including author
manuscript pages 3, 5-6, and 17-18. Each item separates a confirmed statement from
what it cannot establish. The following paraphrases summarize the main article:

- Assay: scintillation proximity-based pMHC-I dissociation; reported half-life is
  a geometric mean from two independent experiments.
- Construction: combining earlier in-house data yielded 28,939 measurements and
  80 HLA-A/B allotypes.
- Selection: an allotype needed one stable and two non-stable observations at a
  2-hour threshold at 37 C; the selected set contained 28,166 observations/75 allotypes.
- Training augmentation: 1,000 random natural 9-mers/allotype, predicted affinity
  weaker than 20,000 nM using NetMHCpan-2.8, were assigned artificial zero hours.
- Table II treats the three C67S molecules as distinct entries.

These are dataset, assay, preprocessing, and model-training statements. They do
not expose replicate records, identify artificial augmentation in raw rows, or
explain individual numerical zeros. Historical author preprocessing is described
here but is not re-applied. Kinetic half-life remains separate from thermal Tm.

The earlier [Jørgensen et al. study, DOI 10.1111/imm.12160](https://onlinelibrary.wiley.com/doi/10.1111/imm.12160)
is in the 2014 Immunology issue; publisher indexed metadata dates its accepted
manuscript online to August 8, 2013. The 2016 paper cites it and incorporates
prior in-house data. Independence cannot be assumed; the previously published
5,509 observations must not be added as independent data. Exact historical row
overlap is outside Task 1.2, and the earlier stability file was not downloaded.

## Local zero-value and allele context findings

The immutable artifact has 799,880 bytes and SHA256:

```text
5f2c6e82d198705a66974b4e42a0ed1412124c4b1e8f7033c7cd43bbdac07f67
```

Local counts confirm 28,166 observations, 75 original identifiers, all 9-mers,
5,679 exact zeros (20.1626%), and 22,487 positives. Every zero is written `0.00`.
There are no malformed values or duplicate HLA-peptide keys. Numerical equality
to zero is established with Decimal, without interpreting biological origin.

| Descriptive group | Identifiers | Rows | Zeros | Positives | Zero fraction |
| --- | ---: | ---: | ---: | ---: | ---: |
| Ordinary HLA-A | 36 | 13,335 | 1,744 | 11,591 | 13.0784% |
| Ordinary HLA-B | 36 | 13,696 | 2,967 | 10,729 | 21.6633% |
| C67S-annotated HLA-B | 3 | 1,135 | 968 | 167 | 85.2863% |
| Unexpected identifiers in this audit | 0 | 0 | 0 | 0 | — |

The ordinary partition contains 72 identifiers and 27,031 rows. It is a
descriptive grouping, not an approved training filter. Task 1.1's strict allele
syntax inventory reports the annotated strings as unexpected; this audit
recognizes the annotation as a separate category without changing that inventory
or any source identifier.

| Original identifier | Rows | Zeros | Positives | Zero fraction |
| --- | ---: | ---: | ---: | ---: |
| HLA-B*14:01(C67S) | 374 | 333 | 41 | 89.0374% |
| HLA-B*14:02(C67S) | 382 | 286 | 96 | 74.8691% |
| HLA-B*39:06(C67S) | 379 | 349 | 30 | 92.0844% |

The main article contains these annotations in Table II, but no explanation of
the modification or its experimental role was located in the reviewed main text.
Underlying protocols remain unreviewed. Do not assert equivalence to unmodified
HLA, silently map identifiers, or exclude these observations.

All positive source values have two reported decimal places. The smallest
positive is `0.05` hours (one row); `0.10` occurs 443 times, `0.11` once, `0.14`
once, `0.15` thirteen times, and `0.20` 1,297 times. These text distributions do
not establish assay resolution or a detection limit. Positive-only summaries
are minimum 0.05, median 2.00, p95 29.20, p99 57.914, and maximum 256.70 hours.
Per-allele positive-only summaries and the ten smallest distinct positive values
are retained in `zero_value_audit.json`.

A descriptive flag uses zero fraction >=50%, with no statistical or eligibility
claim. It flags all three C67S entries and ordinary HLA-B*45:01 (247/368),
HLA-B*41:01 (220/368), HLA-B*55:01 (210/378), and HLA-B*51:01 (179/353).
Every original allele's zero fraction and positive count is reported, including
alleles without zeros; every zero row retains its original source line number.

## Table II reconciliation

The captured PMC HTML has one `T2` section with two five-column blocks. The
standard-library extractor rejects ambiguous cells or duplicate identifiers.
All 75 per-allotype counts match the raw file, totaling 28,166. Representative
matches include HLA-A*01:01 220, HLA-A*02:01 1,023, HLA-A*03:01 861,
HLA-B*07:02 647, HLA-B*15:01 1,070, and HLA-B*35:01 650. All three C67S counts
also match exactly.

For comparison only, the publication's space before `(C67S)` is bridged
explicitly; both published and original raw identifiers remain recorded. No
wild-type mapping occurs. The machine-readable reconciliation contains every
count, missing/extra/mismatched entries, and exploratory p05/p95 comparisons.

Quantiles use type 7, `h=(n-1)*p`, linear interpolation with Decimal arithmetic.
Positive-only distributions exclude zeros only from descriptive statistics;
Table II comparisons use all original values. Printed quantiles can differ
because the author's interpolation and rounding rules are not specified.
Numerical differences are not declared measurement errors and never modify raw
rows. The captured article can be replayed offline with
`verify_publication_snapshot(path, evidence)`; its checksum, size, and extracted
Table II must agree with the evidence register.

## Known and unresolved measurement semantics

Dataset-level experimental provenance is documented. Each row nevertheless
retains `published_raw_stability_table_row_origin_unverified`. A table-wide count
match does not verify each observation's origin or the two underlying replicates.

No explicit row-specific zero rule, detection/quantification threshold, rounding
rule, or censoring convention was located in the reviewed 2016 main article.
This is a scoped literature-review limit, not proof that the original assay had
no limits. Reference 24's assay protocol, supplementary material, original fitting
outputs, and unpublished records remain unreviewed.

Physical zero, synthetic augmentation, missingness, rounding, and left-censoring
remain hypotheses for individual raw zeros. No epsilon, imputation, label,
transformation, or exclusion is applied. Training eligibility, mutant handling,
assay/censoring interpretation, license scope, and historical overlap require
later scientific decisions.

## Reproduction and explicit output

Python 3.11+, standard library only, from the source checkout:

```sh
PYTHONPATH=src python3 -B -m stability_label_curation dtu2016 audit
PYTHONPATH=src python3 -B -m stability_label_curation dtu2016 audit --json
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
```

Default inspection creates no files, never downloads, and fails before scientific
analysis when the raw hash differs. `--json` prints complete audit JSON reports;
the default prints a concise summary. `--input` permits offline explicit input;
`--expected-sha256` requires `--input` and is intended for independently pinned
local fixtures, not for bypassing the canonical Task 1.1 identity.

After committing and verifying a clean tree, create exactly one run using the
supported CLI, with the actual raw artifact as explicit input and evidence
configuration as `--config`. Resolve paths through the project API if using
environment overrides:

```sh
PYTHONPATH=src python3 -B -m stability_label_curation runs create \
  --kind data_source_audit --config configs/netmhcstabpan_2016_evidence.json \
  --input "$HOME/codex/data/stability-label-curation/netmhcstabpan_2016/Stability.txt" \
  --description 'Task 1.2: zero semantics, C67S context, and publication reconciliation'
```

Use the printed run path as `--reports-dir /absolute/project/run/reports` on
`dtu2016 audit`. Only this explicit option writes audit outputs; the destination
must be an existing valid project run whose manifest records the same raw input
and checksum. Existing reports and symlinks are rejected. Publication is atomic
per file, not transactional for the whole bundle; `audit_report_checksums.json`
is published last to mark completion. An interrupted bundle is retained, never
automatically deleted or overwritten.

Outputs are `zero_value_audit.json`, `allele_context_audit.json`,
`publication_reconciliation.json`, `row_flags.jsonl`, `evidence_register.json`,
and `audit_report_checksums.json`. The canonical execution additionally preserves
`publication_article.html`, `dtu_landing.html`, and an evidence-capture checksum
record. Every observation's JSONL flag includes original line number and raw
line text, original HLA/peptide/half-life text, Decimal hours serialized as text,
exact-zero flag, descriptive category, and the conservative provenance status.
Ordering is the source order. No row is labeled training-ready.

To reproduce offline against captured evidence, supply
`--evidence /absolute/run/reports/evidence_register.json`. Snapshot replay is
also offline; no article retrieval is part of the audit implementation. Report
checksums, raw checksum preservation, code commit, and complete JSONL row counts
are verified during canonical execution. macOS checks provide no WSL2/GPU proof.

Stop after Task 1.2; ChatGPT review and later authorization are required before
Task 1.3 or any scientific filtering, transformations, training, or evaluation.
