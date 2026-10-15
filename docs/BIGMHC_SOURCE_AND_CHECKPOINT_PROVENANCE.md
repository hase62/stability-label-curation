# BigMHC source and checkpoint provenance — Task 2.1

This static audit establishes behavior of acquired source files, not historical
training execution or checkpoint cleanliness. No BigMHC code was imported or
executed; no scientific CSV/archive, receptor-reference payload, or weights were
acquired. Source snapshots remain outside Git. Task 2.0's EL-to-IM protocol is
unchanged, and no sampling or correction policy is selected here.

## Pinned source and acquisition boundary

Official repository: https://github.com/KarchinLab/bigmhc

`git ls-remote --symref` advertised `refs/heads/master` at
`199e890fa69a63646730bcecea0a520e08ca4f02` on 2026-10-15. No clone, checkout,
Git packfile, or model blob was fetched. One bounded official GitHub tree API
response captured filenames and Git content identities at that commit. All ten
user-allowlisted files exist; no additional source path was needed.

Raw source requests used exact commit-qualified `raw.githubusercontent.com`
HTTPS URLs, verified TLS, finite 30-second connection/read timeouts, 256 KiB per
file and 2 MiB combined limits. Acquisition totaled **56,572 source bytes**.
Atomic nonreplacing storage uses the existing no-follow path infrastructure.
Redirects must preserve the exact pinned allowlisted URL. Existing artifacts
are identified/reused without replacement. CRC/ZIP handling is irrelevant to
these plain source files. No source archive or Git object was downloaded.

Storage, resolved through `stability_label_curation.paths`:

```text
~/codex/data/stability-label-curation/bigmhc_source/
  199e890fa69a63646730bcecea0a520e08ca4f02/
    README.md
    LICENSE
    src/{train,predict,cli,bigmhc,dataset,mhcenc,mhcuid,encseq}.py
    repository_tree.json
    source_acquisition_receipt.json
```

The receipt records exact URLs, acquisition times, HTTP status, server length,
ETag, content type, sizes and local SHA256. All source files returned HTTP 200
at their original commit-qualified URLs. Local SHA256 is not a publisher release
checksum. Independently computed Git blob SHA1 values also match the pinned
GitHub tree metadata; this is Git content identity, not independent experimental
or publisher-release authentication.

| Inspected file | Bytes | Local SHA256 |
| --- | ---: | --- |
| README.md | 6794 | `bb97813fbe86ec211a435dec9b950783cf9338b81d6012325b142b2057c79818` |
| LICENSE | 8706 | `0de14b419ace8d300daa04b9e2faa09712b0206fc3c55e00f6ac4226e6bb78ac` |
| src/train.py | 2332 | `ca190e855237b7b72d544b71642aba9b9a653bd16d0fbe669162e98360c84412` |
| src/predict.py | 2217 | `609172ed3c34bca585d9877ee35a37cf83a21c124aebb5c4ed1b1b5267acdcb7` |
| src/cli.py | 11393 | `73be4bcfdc1d6a5e8e063e9e26e10f55206942eb265146268ac34e1d370eceac` |
| src/bigmhc.py | 8525 | `d3db4ac31abc478c7427295826ac2788d9cafc06e8e301fd2feb53fedb85fc8f` |
| src/dataset.py | 8584 | `64de083639fc85700e6d459e81205553d29b6d45fea459367a2cc740ad702a22` |
| src/mhcenc.py | 5863 | `6928c214981cac3cd1235da00fc26d38f7bd87ca3d76b04c89630be2077a97b2` |
| src/mhcuid.py | 581 | `a108eb5b4ebd4b52fa8f2bfbfd64d5fe2a396a07eeea24e0cb76f1dd8a37da11` |
| src/encseq.py | 1577 | `ad39102ee0b08f46bf55e94cb30e631aa3e55e6413908ab8b972d2e451aa507d` |

The 87,929-byte repository-tree metadata SHA256 is
`32648a0a1c82e045786c6f8a4431794880b3e0fdb140dc976ff86a202fbadc56`.
The exact receipt identity is pinned in
[bigmhc_source_evidence.json](../configs/bigmhc_source_evidence.json).
No external source text is reproduced in this repository.

## Evidence method and limits

The source-audit utility parses Python with `ast`, records function/call
locations and AST hashes, and extracts loss/optimizer calls, transfer-layer
literals and the skip predicate. Reviewed findings require both file SHA256 and
function AST identities to match. A repinned but changed function yields
`unresolved_changed_or_missing_source`; a byte mismatch against the pinned
inventory fails before parsing. Missing expected functions are reported.

The analysis combines syntax facts with explicit manual call-path review.
It is not a general program verifier or a proof of runtime behavior. Captured
publisher metadata remains separate. Current source is not proven identical
to the implementation/configuration used in the 2023 publication.

## Static training path

| Concern | Source location and finding |
| --- | --- |
| Entrypoint | `train.py:82–90` calls `cli.parseArgs(train=True)` and trains one model only |
| Creation/loading | `cli.py:45–87,184–204`: no model argument creates default BigMHC; any supplied model activates transfer mode; short `el`/`im` expand to seven models, which training rejects |
| CSV input | `dataset.py:242–295`: positional columns, header skipping, uppercased peptides, float32 targets, int8 lengths; no explicit finite/binary/length-range validation |
| Row identity | UID uses sanitized allele plus peptide, then batching resets/discards the index; future adapter must preserve immutable source row IDs separately |
| Encoding | `encseq.py:19–57`: canonical amino acids one-hot; unknown letters become zero blocks, not rejected |
| Batching | `dataset.py:103–147`: peptide-length groups; label-dependent EL selection described below |
| Randomness | `cli.py:236–244`: hardcoded seed 1 for Python/NumPy/Torch/CUDA, cuDNN flags; dataframe sampling and DataLoader shuffling are separate |
| Loss/optimizer | `train.py:29–70`: BCEWithLogitsLoss and AdamW, learning rate from args; CLI default 5e-5, 50 epochs, maxbat 32; other optimizer/loss defaults are dependency behavior |
| Saving | `train.py:75–79`: saves every epoch to `out/epN`; no built-in validation-set selection/early-stopping loop in this entrypoint |

The stock CLI has no explicit “load weights but train all EL parameters” switch:
providing a warm-start model automatically chooses partial-parameter transfer.
A future full-EL warm-start design therefore needs an independently reviewed
mode, rather than an assumption about `--models`. The README's longer
`bigmhc_el`/`bigmhc_im` aliases are not expanded by `_parseModel` in this commit;
only the short forms are recognized, otherwise a custom path is assumed.

## EL class selection and label-flipping consequences

For one nonempty length group with P binary positives, N binary negatives,
requested maximum batch size B, and r=0.99, the source constructs counts:

- q = ceil((P+N)/B)
- p = ceil(P/q)
- n = int(min(ceil(N/q), p/(1−r)−p)) using Python floating arithmetic
- emit slices while positives remain, advancing positive and negative indices.

For P>0 there are M=ceil(P/p) emitted batches; all P positive row references
appear once, and min(N,Mn) negative references appear at most once. Negatives
are not sampled with replacement and positives are not duplicated. With
shuffling, negatives are selected from the shuffled order. This is a desired
negative-fraction cap, not a guarantee of 99% negatives or complete row coverage.
Invalid/nonbinary targets can fall outside both selectors even though they
contribute to group size; a future adapter must reject them explicitly.

| Hypothetical counts, not real dataset observations | Main-process consequence |
| --- | --- |
| P=0, N=100, B=32 | No batch for this length group; all negatives omitted |
| P=5, N=0, B=32 | One positive-only batch; no division by negative count |
| P=1, N=9,999, B=32 | One batch with 1 positive and 32 negatives; 9,967 negatives omitted; size 33 exceeds requested 32 |
| P=1, N=9,999, B=32,768 | Float truncation gives n=98 rather than idealized 99; 9,901 negatives omitted |

If no length group emits any batch, later first-batch indexing raises
`IndexError`. If some other group has positives, an all-negative group can
silently disappear instead. Class-wise ceilings can exceed the nominal
`maxbat`; it is not a strict maximum in this branch.

A 1→0 correction can reduce the number of positive anchors and alter negative
coverage, batch count, gradient steps, class proportions and RNG consumption.
A 0→1 correction makes that row a positive reference rather than a potentially
omitted negative and may change those same quantities discontinuously.
Equal epochs do not establish equal sample exposure or computation.

Future review should compare the source-native label-dependent sampler with an
explicit exposure-controlled alternative before choosing a policy. Neither is
adopted here. Preserve original labels and future pseudolabel provenance. Log
per-length class counts, planned and actually consumed immutable row IDs,
omissions/multiplicities, batch sizes, positive/negative contributions, update
counts and RNG/worker states. Matched random perturbation and affinity-only
controls need comparable accounting as well as matched architecture/loss/seeds.

## Worker-state uncertainty

`cli.py:222–232` creates a DataLoader with persistent workers and shuffled batch
indices. `train.py:52–55` rebuilds the main-process Dataset batches each epoch.
No explicit mechanism synchronizes these new DataFrame/batch objects into
already-running worker Dataset replicas.

The [current PyTorch DataLoader documentation](https://docs.pytorch.org/docs/2.14/data.html)
describes worker dataset replicas and persistent instances. This supports a
**runtime-verification-pending inference** that later worker-visible batches
may retain earlier state. It does not verify the historical PyTorch 1.13 run.
Consequently analytical plans are not certified counts of rows actually used
across epochs; worker-consumed IDs must be observed in a future authorized test.
No dependency or external runtime was installed or executed here.

## IM transfer semantics

`BigMHC.tllayers()` (`bigmhc.py:210–216`) names exactly four tensors:
`condenser.att.weight`, `condenser.att.bias`, `condenser.out.weight`, and
`condenser.out.bias`. These belong to two Linear modules in the same architecture.
The transfer AdamW optimizer receives only these parameters. The remaining
weights are excluded from optimizer updates, but are not explicitly changed to
`requires_grad=False`. The complete model is put in training mode, so encoder
and other Dense-block dropout remain active. “Frozen” must therefore distinguish
unchanged weights from evaluation-mode features or disabled autograd. Unoptimized
gradients can also accumulate because optimizer zeroing covers its parameter set.

Per-epoch IM batches use unbalanced length-group slicing (`negfrac=None` and
default `evendist=False`). The initial loader's `evendist=True` is superseded by
the main-process rebuild; worker visibility remains the caveat above.
`train.py:59–61` skips a transfer batch when its target sum is zero, before
forward/loss/optimizer step. With valid binary labels this skips all-negative
batches; mixed batches retain their negative members. Thus not every IM row is
guaranteed a loss contribution. The printed epoch error divides by `len(data)`,
including skipped batches, and is not automatically a row-weighted mean.

These are code findings, not proof of the exact skips or configurations used for
the paper. They do not justify altering any experimental IM label.

## Checkpoint inheritance and ensemble inference

Filename-only metadata lists seven base directories:
`models/bat512`, `bat1024`, `bat2048`, `bat4096`, `bat8192`, `bat16384`, and
`bat32768`; each has 36 `.lyr` entries and an `im` child with four. No additional
model-directory metadata files were listed. Their names correspond to the
publisher-described batch-size ensemble design, but do not prove actual training
settings or exact cohorts. Weight bytes were neither retrieved nor inspected.

`BigMHC.save` writes all state tensors for EL and only the four selected tensors
for transfer. `load` detects a four-file overlay by count, reads base layer
filenames from its immediate parent directory, substitutes matching overlay
filenames, and constructs default BigMHC. This establishes **code-level
inheritance**, not verified checkpoint ancestry. An IM subdirectory alone is
incomplete. With custom `out/epN` paths, the immediate parent must actually hold
the intended EL base; directory names do not authenticate it.

The save path stores no explicit parent/data/label hashes, optimizer state or
RNG state. Final reproducibility requires a ledger including:

- EL initialization and full parent-chain identities, code and environment.
- EL dataset, source rows, splits, original/pseudolabel version and configuration.
- Complete EL trained parameter identities.
- IM input/split identities, unchanged experimental labels, optimizer settings
  and exact updated-parameter list.
- Seeds, RNG/worker/optimizer state where continuation matters, actual update/
  exposure/skip counts, and selection history.
- EL parent and IM overlay hashes, reconstructable final model identity, and
  ensemble member identities.

`predict.py:30–61` sets evaluation mode and no-grad, averages **sigmoid
probabilities**, not logits, and averages attention. Output retains original MHC
strings, not the resolved encoder allele. Public checkpoint ancestry, source
hashes and evaluation exposure cannot be certified from source and filenames.

## Allele handling and future adapter

`mhcuid.py:24–25` uppercases and strips punctuation. This is syntactic
canonicalization, not HLA biological validation. `MHCEncoder.nearestMHC`
(`mhcenc.py:123–170`) uses exact sanitized key, cache, optional HLA prefix,
progressively shortened prefixes, and then Levenshtein nearest key. Ties depend
on encountered key order. Arbitrary unsupported strings can map to a known key;
an empty sanitized string can fail by indexing. Multiple names can collapse to
one UID or encoding. `__contains__` uses exact sanitized membership, whereas
`__getitem__` invokes fuzzy fallback. No resolved identity is added to prediction
output.

Future adapter requirements: preserve raw names and row references; use an
explicit validated human HLA-I mapping and authenticated receptor reference;
record resolved IDs and reference hashes; reject/flag unsupported, ambiguous or
colliding identifiers; preserve mutant constructs separately. Do not use nearest
fallback as scientific validation. Coverage of all 72 ordinary DTU identifiers
requires the actual receptor CSV in a later task and is **not established here**.

## Published dataset metadata, kept separate from local files

[Publication](https://doi.org/10.1038/s42256-023-00694-6), abstract and Data/Code
availability, describes seven EL networks, IM transfer, public upstream sources,
Mendeley data and GitHub software/models. No historical execution was reproduced.

[Mendeley Version 4](https://data.mendeley.com/datasets/dvmz6pkzvb/4), DOI
`10.17632/dvmz6pkzvb.4`, published 14 April 2023, lists these archive members:

| Member | Publisher-described role |
| --- | --- |
| el_train.csv / el_val.csv | EL training / validation |
| el_test.csv | EL test and predictor outputs |
| im_train.csv / im_val.csv | IM transfer training / validation |
| im_test.csv | IM test and predictor outputs |
| iedb.csv | Infectious-disease IM evaluation and predictions |
| summary.csv | Counts by allele/dataset, not extra observations |
| manafest.csv | Assay-described neoepitope evaluation with wild-type/gene metadata |
| pseudoseqs.csv | Allele one-hot reference, not stability or IM measurements |

Described columns: `mhc`, `pep`, binary `tgt`; MANAFEST additionally `wtp` and
`gene`; receptor reference uses aligned-position/amino-acid columns. Additional
prediction columns are not experimental labels. EL and IM target meanings differ.
Metadata does not independently verify each assay/negative label or source row.

The **publisher-listed, locally unverified** `datasets.zip` SHA256 is
`0d152a452756cf2e0014ffced6afc25118e7c11cf1f626b26e49f50f79edffaa`.
Other published hashes are captured in the evidence configuration with
`local_sha256=null` and `downloaded=false`. `el.csv.zip` contains predictions
on all EL train/validation/test, and `eltrainval_models.zip` holds EL-test models
rather than necessarily the GitHub production models; neither is an independent
experimental source or an authorized payload for this task.

Version comparisons use landing pages only: v1 (30 August 2022) lists separately
packaged EL/IM/IFN-gamma/MANAFEST and large constructed-negative files; v2
(19 January 2023) has a different published datasets.zip hash
`33a51710aa55ff1af99944ee617fc9f5e2a5224f4dfd2df85dd36d6fe7f44c5d`;
v3 (20 January 2023) and v4 list the same dataset archive hash. Version 4 adds
an all-EL predictions archive description. No local row-level version comparison
was performed. Published equal hashes are claims, not new file verification.

Future ingestion needs a separately approved exact artifact/version allowlist,
bounded verified download, archive member/path/size controls, raw preservation,
column and negative-provenance audits, explicit HLA coverage, and benchmark
outcome isolation before model selection. Do not acquire weight archives or
all-EL prediction archives as experimental observations.

## License and remaining decisions

The acquired `LICENSE` is the **BigMHC Academic License**: section 1 describes
noncommercial research use and commercial licensing; sections 3–5 specify
copy/distribution/modification conditions. Mendeley separately lists **CC BY 4.0**
for its dataset release. Do not substitute dataset terms for software/weight
terms. This audit makes no legal determination and redistributes no BigMHC code,
data, or weights.

Pending: source-native versus exposure-controlled batching, actual worker
consumption, full-EL initialization mode, checkpoint training-history evidence,
EL decoy definitions, IM negative evidence, receptor coverage, final cohorts,
hard splits, correction thresholds/confidence and multi-allelic assignments.
No published checkpoint is certified clean for independent IM evaluation.

## Offline reproduction and run provenance

```sh
PYTHONPATH=src python3 -B -m unittest discover -s tests -v
PYTHONPATH=src python3 -B -m stability_label_curation bigmhc source-audit --json
```

Default audit reads only the pinned snapshot and committed evidence. It performs
no acquisition. `--snapshot DIR --evidence FILE` supports explicit synthetic
fixtures, still checksum-gated. `--reports-dir` writes only into an existing
project run whose manifest records every actual snapshot input.

Canonical run ID: `task-2_1-bigmhc-code-provenance`. Its manifest uses the Task 2.1
implementation commit, the ten original source files and two metadata files as
hashed inputs. Publisher-only dataset hashes are not input-artifact records.
Reports cover source inventory, training, transfer lineage, HLA risks, published
metadata and unresolved exposure. Offline recomputation compares canonical JSON
bytes and rehashes inputs; manifest validation and byte verification are separate
checks. Existing historical dataset hashes are checked for preservation only,
not used as BigMHC scientific inputs. No run-manifest schema was changed.

Recommended Task 2.2: a separately reviewed, bounded BigMHC dataset-ingestion
specification and acquisition, including member allowlist, receptor coverage and
negative/source provenance, with benchmark outcomes protected. This document
does not authorize that acquisition or any split, correction or model execution.
