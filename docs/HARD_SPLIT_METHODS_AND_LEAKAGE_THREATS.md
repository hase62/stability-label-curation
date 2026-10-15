# Hard-split methods and leakage threats — Task 2.0

This is an evidence and feasibility audit. It produces no folds, EL correction
masks, models or performance estimates. User-adopted directions and unresolved
choices are separated in the [EL-to-IM protocol](PHASE2_EL_TO_IM_RESEARCH_PROTOCOL.md).

## Evidence status

[hard_split_literature_evidence.json](../configs/hard_split_literature_evidence.json)
captures access date, exact sections, all requested comparison dimensions and
these statuses: `directly_verified_method` (article text read),
`publication_claim_only` (reported outcomes/assertions not reproduced),
`implementation_verified` (requires inspected implementation), `unresolved`, and
`not_applicable`. Reading methods verifies what is described, not what every
released file or execution does. None of the six external split implementations
has been pinned and verified in this task. Missing documentation establishes
an evidence gap, not misconduct or demonstrated leakage.

## Focused methods comparison

### T-SCAPE, Science Advances 2025

[Article](https://pmc.ncbi.nlm.nih.gov/articles/PMC12680054/), DOI
10.1126/sciadv.adz8759. Results “A scrupulous data curation and leakage control
strategy” and Methods “Sequence identity filtering using CD-HIT” describe
benchmark-directed sliding 9-residue filtering, shorter fragments retained
whole, and CD-HIT `-c 0.8 -n 2`. Subsequent 9:1 validation separation is claimed;
task-specific text also describes frequency-ordered hard validation. Exact
label-concordance analysis and near-fragment filtering answer different questions.
The paper claims a further class-I shared-fragment alignment check and separates
class-I from class-II filtering. These claims require task-specific code checks.

For aligned ungapped nine-mers, at least 80% identity requires eight matches:
zero or one mismatch. CD-HIT's greedy, representative-based clustering is not
thereby certified equivalent to exhaustively excluding every such pair. Our
complete Hamming index tests the stated predicate, not CD-HIT historical execution.
The article's terminology for peptide oligomers does not imply nucleotide input;
our windows are nine amino-acid characters.

The actual PMC supplement hyperlink was verified. One HTTPS request, capped at
12 MiB, returned non-PDF content and was rejected before publication. No PDF was
saved. The supplied reference SHA256
`fb3baced357e8317e40fb8203d197318d9369244a42dcd00ae8c5ecf73153e26`
is **not a locally verified artifact checksum**. Page-specific supplemental
statements remain `user_reviewed_secondary_task_evidence`:

| Location | Attributed statement | What it does not establish |
| --- | --- | --- |
| Text p2, Fig. S1/S1C | Before/after filtering composition, 90/10 division and exact 9-mer overlap matrix | Near-sequence, donor and checkpoint clearance |
| Text pp3–4 | Binding-benchmark <2-mismatch fragment exclusion and temporal test cohorts | Novel sequences or complete prospective independence |
| Text p6 | TCR negative-construction change: AUROC .630→.511, PR-AUC .709→.624 | EL/IM leakage or conventional-versus-hard performance effect |
| Tables S2–S4 pp19–20 | IEDB EL/affinity pretraining and PRIME IM fine-tuning sources/class counts | All pretraining/fine-tuning exposure resolved |

### BigMHC, 2023

[Article](https://pmc.ncbi.nlm.nih.gov/articles/PMC10569228/), Methods EL/IM
training and evaluation, Extended Data Fig. 5: EL MS positives use decoys;
nonrandom PRIME data support IM transfer. Training/validation are 9:1, repeated
EL train/test pMHCs are removed from training, and evaluation intersections are
removed. This does not establish global across-HLA peptide or near-sequence
separation. The reported EL test AUROC .9733/AUPRC .8779 is not a matched hard-
versus-conventional split contrast. Donor, preprocessing chronology and checkpoint
exposure require further auditing.

[Repository README](https://github.com/KarchinLab/bigmhc) was inspected without
cloning or fetching Git objects. Its permissive HLA mapping is not used here.
[Mendeley v4 metadata](https://data.mendeley.com/datasets/dvmz6pkzvb/4) identifies
CSV roles, published hashes, and CC BY 4.0. No CSV, archive or weights were
retrieved. These metadata do not authenticate future local bytes or certify
experimental-negative definitions. Future acquisition must use an explicit
file allowlist and avoid bundled model artifacts.

### HLApollo, 2024

[Article](https://www.nature.com/articles/s41467-024-54887-7), Methods training/
benchmark construction: filtered positive tuples split per genotype 90/10;
negative sets are generated, then `{el,peptide,pseudosequence}` intersections
are removed. This label-conditioned rule needs an independent conflict audit.
A peptide-disjoint alternative is referenced in Supplementary Fig. 8, while BM3
holds out specified study genotypes. Near-sequence/donor guarantees are unresolved.
Negative-set switching occurs during training, with random proteome negatives
rather than experimentally verified nonpresentation. Reported BM1 ensemble AP
78.7% and negative-switching gains are not a verified conventional/hard delta;
the latter delta remains unavailable without inspecting the supplemental result.
Protein-model extensions require separate pretraining-exposure checks.

### USMPep, 2020

[Article](https://bmcbioinformatics.biomedcentral.com/articles/10.1186/s12859-020-03631-1),
Methods “MHC binding prediction datasets”: Kim14 removes same-length peptides
with ≥80% identity from Blind and reuses BD2009 `cv_gs`. It predicts binding
affinity, not EL-to-IM. Across-HLA, cross-length fragment and donor separation
are not established by this allele-specific description. Optional unlabeled-
peptide language pretraining has different exposure from scratch models.
Reported benchmark/allele comparisons are not a matched random/hard experiment.
The IEDB16 B*38:01 example, 172/176 test sequences in a high-similarity cluster,
illustrates dependence and composition concerns even within test sets.

### DataSAIL, 2025, and addendum, 2026

[Original](https://www.nature.com/articles/s41467-025-58606-8), workflow and
(k,R,C) optimization: clustering plus integer optimization reduces total selected
similarity leakage with balance constraints. This is a heuristic for an NP-hard
problem. Two-dimensional conflicting assignments can discard interactions.
Metric, retention and residual-edge audits are essential; checkpoint, donor and
EL/IM label provenance are not automatically controlled.

[Addendum](https://www.nature.com/articles/s41467-025-67495-w), published
13 February 2026, LP-PDBBind/PINDER sections: maximum cross-split similarity
bounds differ from minimizing total leakage. The reported PINDER split has
less leakage than DataSAIL in that comparison. Reported comparisons use v1.2.1
and appropriate ratios; no EL/IM numerical performance delta is established.
This supports comparing objectives and composition rather than calling every
similarity-aware split uniformly “harder” or leakage-free.

## Controls that must remain separate

| Control | What it can test | What remains outside its scope |
| --- | --- | --- |
| Exact peptide–HLA | Identical pairs, with explicit evidence for mappings | Same peptide on other HLA; homologs |
| Full exact peptide | Identical sequences across HLA | Close variants, studies, donors |
| Shared sliding 9-mer | Exact contiguous fragments in longer peptides | Short sequences, noncontiguous motifs |
| Aligned 9-mer Hamming | Declared substitution neighborhood | Indels, structure, anchor weighting |
| Benchmark-to-training filter | Specified benchmark exposure | Independent training/validation separation |
| Pretraining/fine-tuning audit | Checkpoint/source exposure across stages | Unknown histories cannot be cleared |
| Negative-source audit | Experimental versus constructed labels | No sequence-separation guarantee |
| Study/donor grouping | Available biological metadata reuse | Homologs and external pretrained data |

## Implemented diagnostic contract

`sequence_leakage_audit.py` accepts immutable sequence records with supplied group
labels. It never assigns groups. Exact sequence and strict pair reports include
duplicate counts and raw label disagreements; disagreements are flags, not proof
that one label is incorrect. Optional normalized joins require explicit verified
mapping evidence. Ambiguous, cross-locus and annotated-mutant mappings fail.
No fuzzy mapping, sequence repair or automatic wild-type conversion occurs.

Sliding windows preserve full source strings. Shorter peptides remain in exact
identity/pair checks and are separately counted; near-short similarity is not
silently certified. Noncanonical uppercase characters are flagged. Generic
provenance includes explicit source/measurement aliases, study/donor IDs, mutant
relationships and negative/checkpoint categories. Missing metadata is unknown.
Shared source identity alone does not prove reuse of a physical measurement.

Masked-position signatures enumerate every aligned distinct-window pair within
0, 1 or 2 mismatches, with an exhaustive small-fixture oracle test. Default one
mismatch is diagnostic only. Exact duplicate occurrences are counted separately
from edges between unique sequences. Graph traversal reports deterministic
components, direct degree counts and allele representation. Transitive members
can be more distant than the edge threshold. A long peptide can touch multiple
window components; a future peptide-level split would need to consolidate its
memberships, then re-audit. No such split or grouping assignment is made here.

Bounds: 100,000 input records; 50,000 unique windows; 2,000,000 signatures/window
occurrences and direct edges. Mask counts grow combinatorially; dense buckets
and output edges can still be quadratic. Exceeding a bound fails rather than
truncates. The index is not a scalable guarantee for unrestricted EL corpora.

## Existing-registry feasibility observation

Only ordinary DTU HLA-A/B nine-mers contribute to this analysis:
27,031 records / 72 identifiers / 4,711 reported zeros, 5,633 unique peptides.
3,930 peptides recur across alleles, accounting for 25,328 records. Under the
candidate aligned distance ≤1 rule, there are 146 distinct one-mismatch edges,
5,494 components, with sizes 1:5,376; 2:103; 3:10; 4:4; 5:1.
The maximum direct degree is four. There are 96,262 same-peptide record pairs
(zero distance), which do not imply independent measurements. The largest
component by record weight touches 33 records. Zero-distance duplicate
occurrences are separate from unique-node edges. HLA-B*13:02 has seven records
across seven components, and HLA-A*69:01 has 15 across 15; sparse per-allele
support can constrain validation even without large components.

This does not exhibit a giant component under this particular rule. It does
not establish feasible stratified folds: cross-allele reuse, per-allele support,
future EL/IM overlap, prevalence and different similarity definitions remain
constraints. Component reports show each allele's support and number of touched
components. No folds or threshold choices are approved.

## Cross-task exposure matrix

Generated `cross_task_exposure_matrix.json` covers all 36 unordered pairs among
Teacher training, Teacher validation, EL baseline training, corrected EL
training, IM transfer, final assayed IM candidates, affinity comparator,
public checkpoints, and source artificial negatives/decoys.
Each pair identifies proposed peptide/pair/near-sequence, study/donor,
label-derived, shared-observation and pretraining guards. Baseline/corrected EL
share inputs intentionally; the intended intervention is the pseudolabel rule.
Other exposure counts remain unknown. No actual BigMHC or IM overlap is measured.

The Teacher's training/validation and future correction thresholds must also be
checked against final IM test exposures. Freezing a test only after development
has used its sequences or labels may not remove model-selection contamination.
SPEARMINT aliases do not provide independent DTU validation. Mutant peptide
relationships need explicit evidence rather than inferred biological lineage.

## Performance is a diagnostic

A large drop under harder separation can reveal optimistic conventional
estimates or genuine out-of-distribution difficulty. No performance drop does
not prove data leakage. A drop does not prove that all leakage has been removed.
Negative construction, prevalence, allele coverage, size and label quality can
also change performance. Future results must report composition and exposure
statistics with metrics, paired seeds and uncertainty. No predictive evaluation
was run for this task.

## Offline reproduction and provenance

Storage uses `stability_label_curation.paths`; no home directory is hardcoded.
`configs/phase2_el_im_protocol.json` pins the Task 1.8 registry, parent manifest
and evidence manifest. Actual input hashes are gated before parsing and checked
after inspection. The run records these **derived files**, not fictional new
raw-source relationships. The T-SCAPE PDF is not a run input because no PDF was
acquired. The historical source registry and run-manifest schema remain unchanged.

```sh
PYTHONPATH=src python3 -B -m stability_label_curation leakage inspect --json
PYTHONPATH=src python3 -B -m stability_label_curation runs create --help
```

Canonical run ID: `task-2_0-el-im-hard-split-preflight`. To create it once, use
`runs create --kind scientific_preflight --run-id <ID> --config
configs/phase2_el_im_protocol.json`, with repeatable `--input` for the configured
parent observation, manifest and evidence files resolved through `paths`.
Then use `leakage inspect --json --reports-dir <run>/reports`, followed by
`runs validate <ID>`. Existing run IDs and reports are never overwritten.
To reproduce, run read-only `leakage inspect --json`, compare each report's
canonical `json_report` bytes with the saved files and rehash all three inputs.
`execution_verification.json` records report hashes and the committed code SHA.

Remaining decisions are algorithm/threshold, external IM selection, correction
threshold/confidence, multi-allelic assignment, matched controls and checkpoint
history. They must be reviewed before data construction or training.
