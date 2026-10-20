# Task 2.26 — Frozen third-party IMPROVE sequence-hard benchmark

**Built and frozen on Z790 WSL2, 2026-10-20.** The primary benchmark contains
**7,788 experimentally supported 9-mer/HLA/recognition observations**, with
**227 positive and 7,561 negative** labels, from **70 patients, three studies,
and 36 exactly supported HLAs**. It is ready for separately authorized Task 2.27.
No model was loaded, no A/S/P inference or performance calculation occurred,
and no prior prediction or metric file was opened.

Branch: `task/2.26-third-party-hard-split`, created from exactly
`a4a068c079ebe6e32bfde0c5314e96877e1a3fe9`, irrespective of main.
The curation rules, exact distance implementation, tests and
[Task 2.27 protocol](BIGMHC_THIRD_PARTY_EVALUATION_TASK2_27_PROTOCOL.md)
were committed as **`fc9cc8d` before reference/distance execution and cohort freeze**.
No previous document, result or checkpoint was modified.

## Source acquisition and scientific identity

Selected source: Borch et al., [IMPROVE, Frontiers in Immunology (2024)](https://www.frontiersin.org/journals/immunology/articles/10.3389/fimmu.2024.1360281/full),
DOI **`10.3389/fimmu.2024.1360281`**, original screened in-house cohort.
The [author repository](https://github.com/SRHgroup/IMPROVE_paper) was pinned at
commit **`c67094276b52358b5202ad9e5597acd87888ea1d`** using GitHub commit/tree
metadata; no repository clone or model-weight download was performed.

| Acquired source identity | Value |
| --- | --- |
| Archive URL | `https://raw.githubusercontent.com/SRHgroup/IMPROVE_paper/c67094276b52358b5202ad9e5597acd87888ea1d/data.zip` |
| Archive size | 103,626,234 bytes |
| Archive Git blob SHA1 | `a1b2375a8dcfcc24b8931d7cb5cb34e2953bb207` |
| Archive SHA256 | `adf02eb5054a8aa4b6eccd3b6e0ff1200889d41ae05655fd6e55c5c347f720d9` |
| Original screened member | `data/01_data/01_Validated_neoepitopes.txt` |
| Member size | 4,574,862 bytes |
| Member SHA256 | `b27854c98a34b6bb83af248979cc3ea121534fa2e8d9e97415654dc0c0a95c95` |

Archive bytes were checked against the pinned Git blob, size and local SHA256.
Only the screened member was opened from the archive; RNA tables, untested extra
candidates, CEDAR benchmark tables and predictor outputs were not parsed. The
archive is the published container needed for patient-annotated observations;
no `results.zip`, tool repository, model package or secondary-source data were
downloaded. Small README/provenance R scripts and the separate 410,649-byte
`neoepitope_tabels/In_house_neoepitope_for_CV.tsv` were obtained at the same commit
with Git-blob authentication. The latter **matches all 17,520 original peptide,
HLA and binary response triples in source order**. External R code was inspected
as provenance and never executed. Original publication HTML was preserved with
URL/hash metadata for the assay interpretation.

Data are under resolved project data / `improve_paper/`; URL, retrieval time,
HTTP metadata, source commit/tree, file sizes and hashes are retained in run
reports `initial_source_metadata.json`, `selected_source_files.json`,
`archive_acquisition.json`, `archive_inventory.json` and
`publication_assay_evidence.json`.

## Experimental compatibility and observation policy

The paper describes synthesized candidate peptides folded with their associated
HLA into DNA-barcoded pMHC multimers and screened against patient-derived T cells.
The released `Mut_peptide`/`HLA_allele` fields therefore identify the tested
complex; HLA was not inferred here from genotype or predicted binding alone.
Prediction-based candidate selection upstream is distinct from experimental
recognition of the resulting folded pMHC. `Mut_peptide` is used unchanged except
strip/uppercase. The predicted 9-mer binding cores in feature analyses are not
the assayed sequence field used here, and longer peptides were not converted.

The endpoint is **multimer T-cell recognition**, summarized by the authors across
available patient materials, rather than direct cytokine function or confirmed
endogenous presentation. `response` values `yes`/`1` map to positive and
`no`/`0` to negative, retaining the raw value. Negative means screened but not
recognized in that patient context, not universally non-immunogenic. Source
materials include PBMCs/TILs and, for the melanoma study, infusion-product
screening. Raw per-timepoint barcode measurements and complete assay thresholds
are not provided by this table; the author summary is the observation endpoint.

All 17,520 source rows carry `validation=Sufficient`. The inspected export script
uses this as released-analysis-population membership; it is **not independently
audited per-assay barcode quality**. The experimental interpretation follows the
paper's screen description and exact agreement with its in-house response table.
No untested or synthetic negative was added.

Original coordinates are pinned source commit + archive member + one-based data
row and original line number, with raw-row SHA256 and original `identity`.
`Patient`, `Sample`, original `cohort`, source study DOI, raw peptide/HLA/response,
wild-type sequence and available mutation annotations are retained. The **81
source Sample identifiers** are preserved separately from **70 patients**; they
are not assumed to be unique T-cell assay timepoints.

Every released original observation is retained unless its original ID has
contradictory peptide/HLA/patient/study/response definitions, in which case all
copies would be quarantined. **No such conflicting ID exists.** Repeated peptides,
pairs and different-patient responses are not silently deduplicated or resolved
by voting. Distinct patients with differing responses remain distinct experiments.

## Original and compatible candidate counts

| Population | Observations | Positive | Negative | Unique peptides | HLAs | Patients |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Complete original screened study | 17,520 | 467 | 17,053 | 15,293 | 36 | 70 |
| Compatible assayed canonical 9-mers | 10,561 | 308 | 10,253 | 8,877 | 36 | 70 |
| Fixed primary hard split | 7,788 | 227 | 7,561 | 6,576 | 36 | 70 |

The original peptide-length counts are 8: **515**, 9: **10,561**, 10: **4,716**,
11: **1,728**. Exclusion before similarity is therefore **6,959 non-9-mers**.
There are zero malformed canonical 9-mers, unsupported/ambiguous exact HLAs,
ambiguous binary responses, missing source-study IDs or conflicting original IDs
in the candidate set. All 36 HLAs are uniquely represented in the pinned native
414-feature mapping; no nearest-allele substitution occurs. Experimental
9-mer/HLA/outcome compatibility is supported for all **10,561 candidates**.

## Frozen fitting, selection and prior-test references

The EL split was joined row-for-row to the authenticated complete original EL
view, preserving all eligible negatives including those never sampled. Actual
EL partitions are 1,308,196 fitting / 145,371 validation / 11 excluded rows.
The excluded rows are not restored into either EL fitting or EL selection.
All 3,428 final IM fitting rows were used. No approximate or reconstructed
training population was substituted.

| Reference set | Exposure role | Source observations | Unique canonical 9-mers |
| --- | --- | ---: | ---: |
| EL_fit | actual_model_fitting | 1,308,196 | 1,122,528 |
| IM_fit | actual_model_fitting | 3,428 | 3,315 |
| EL_selection | EL_epoch_selection | 145,371 | 124,828 |
| IM_epoch_selection | IM_epoch_selection_also_in_final_IM_fit | 686 | 665 |
| IM_historical_development | historical_development_and_selection | 383 | 380 |
| prior_Mendeley_published | previously_used_external_source_not_training | 937 | 273 |
| prior_Mendeley_evaluated | actually_scored_external_subset_not_training | 275 | 272 |

The 686-row IM epoch-selection population is a subset of final IM fitting; it
is preserved as a separate exposure category without double-counting sequences
in the union. Fitting-only union: **1,125,785**
unique sequences. Fitting plus selection/development union:
**1,250,989** unique sequences.

The original Mendeley source has 937 observations, including 281 valid 9-mer
observations / 273 sequences. Its actually scored 275-row subset / 272 sequences
is retained separately. **Prior benchmark exposure is not fitting exposure.**
Only Task 2.25 identity manifests were opened, authenticated against their
pre-outcome eligibility hashes; no Task 2.25 prediction or metric was reanalyzed.
Source input paths/hashes, row counts and sorted unique sequence snapshots are
in `reports/reference_freeze.json` and `references/*.txt.gz`.

## Exact distance rule and difficulty strata

Primary requires **minimum unweighted same-length Hamming distance ≥3** from
the complete union of fitting and selection/development 9-mers. This excludes
exact sequences and every one-/two-substitution neighbor globally across HLAs.
All thresholds also exclude exact sequences from the full original Mendeley
benchmark. Source response labels do not determine these rules; no model score
was generated or consulted.

The index uses four disjoint blocks (2/2/2/3 residues) and exact packed amino-acid
mismatch counts. Any neighbor within three substitutions must share a block.
After bucket search, a nearest witness at distance ≤4 proves an exact answer;
more distant cases use a one-query full scan. Distances are **exact, not capped**.
No full all-pairs matrix was constructed. Seven reference categories were
searched for 8,877 unique candidate sequences, yielding **62,139 nearest-reference
witnesses**, all checked for reference membership and exact mismatch count.

Candidate distance to the fitting/selection union, before prior-test exclusion:

| Exact minimum distance | Observations | Positive | Negative | Unique peptides |
| --- | ---: | ---: | ---: | ---: |
| 0 | 92 | 4 | 88 | 69 |
| 1 | 1,165 | 38 | 1,127 | 979 |
| 2 | 1,516 | 39 | 1,477 | 1,253 |
| 3 | 6,896 | 198 | 6,698 | 5,819 |
| 4 | 892 | 29 | 863 | 757 |

Primary removes **2,773 candidate observations** at distance <3 (81 positive,
2,692 negative). Two candidate sequences overlap the prior benchmark exactly;
both already fail primary distance eligibility, so the prior-test rule removes
**zero additional primary rows**. At diagnostic ≥2 it removes one additional
row. The primary remains ≥3 regardless of diagnostic counts or prevalence.

| Minimum distance | N | Positive | Negative | Prevalence | Unique peptides | HLAs | Patients | Studies |
| --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | ---: |
| ≥2 | 9,303 | 266 | 9,037 | 0.028592927012791574 | 7,828 | 36 | 70 | 3 |
| ≥3 — PRIMARY | 7,788 | 227 | 7,561 | 0.029147406266050335 | 6,576 | 36 | 70 | 3 |
| ≥4 | 892 | 29 | 863 | 0.032511210762331835 | 757 | 35 | 70 | 3 |

Final primary distance distribution: **6,896 at distance 3; 892 at distance 4**.
There are zero primary peptides within two substitutions of the fitting/selection
union and zero exact overlaps with either prior-benchmark reference.

Primary identity-manifest SHA256:
`bd555e21e3ce16ea0aafe9b4dbc8f5ed88548cc366d07c8160ba222ba9fb74ed`.

## Contamination, duplicate and family assessment

Counts below refer to the 10,561 compatible candidates, before hard filtering.
Exposure categories overlap, so their counts must not be added as exclusions.

| Reference | Exact-sequence observations | Exact unique peptides | Exact peptide–HLA observations | Identical peptide also occurs under other reference HLA |
| --- | ---: | ---: | ---: | ---: |
| EL_fit | 46 | 34 | 2 | 46 |
| IM_fit | 41 | 30 | 22 | 19 |
| EL_selection | 1 | 1 | 0 | 1 |
| IM_epoch_selection | 8 | 7 | 5 | 3 |
| IM_historical_development | 4 | 4 | 4 | 0 |
| prior_Mendeley_published | 2 | 2 | 0 | 2 |
| prior_Mendeley_evaluated | 2 | 2 | 0 | 2 |

Global peptide exclusion is essential: a different HLA does not erase sequence
exposure. The exact same-pair column is not used as a narrower substitute.
All fitting and selection exact/near matches are excluded from primary.

Near-neighbor distance to the prior published benchmark is reported separately,
not added as another adjustable exclusion. In primary it is distance
**2: 4; 3: 11; 4: 409; 5: 3,046; 6: 4,140; 7: 178** observations.
Full candidate distributions and nearest witnesses for each reference are
retained. Exact primary prior-benchmark sequence and pair counts are zero.

The full source has 158 repeated pMHC groups / 167 excess rows and three pMHC
groups with differing responses across patients. Among compatible 9-mers,
there are 87 repeated pMHC groups / 91 excess rows and one mixed-outcome pMHC
group across patients. There are **zero duplicate original IDs and zero repeated
same-patient/same-pMHC records** in both populations. Differing patients' outcomes
are retained as context-dependent measurements, not relabeled as contradictions.

Primary retains **38 repeated pMHC groups / 38 excess rows**, all across distinct
patients, and **950 repeated-peptide groups / 1,212 excess rows**. Its 52 mixed-
outcome peptide groups can involve different HLA/patient contexts; there are
no conflicting original IDs or mixed-outcome same-pMHC groups in primary.

Possible mutation-family grouping uses the raw gene ID, genomic position and
amino-acid change, without chromosome/genome-build harmonization. Primary has
**4,160 such groups**, including **1,304 with multiple peptide sequences** and
**37 spanning multiple patients**. These are descriptive candidate families,
not a certified normalized-variant identity or an additional exclusion rule.
Reference training inputs lack comparable variant/patient annotations, so
mutation-family identity overlap with training cannot be independently resolved.

Hamming exclusion does not eliminate shifted shared cores. Primary contains
**109** observations sharing a contiguous 8-mer with an EL fitting sequence,
**one** with an IM fitting sequence and **18** with EL selection sequences.
These overlapping counts are reported per reference and do not change the fixed
rule. The split is rigorous for the specified ungapped 9-mer Hamming criterion,
not a guarantee of independence under every sequence alignment or protein family.

The original studies are identified below, but BigMHC prepared training views
and the Mendeley benchmark do not expose complete comparable upstream study
and patient identifiers. Therefore **study/publication or patient overlap is
unresolved, not asserted zero**. A third-party 2024 release may reuse earlier
clinical studies; publication date alone is not assay independence. The exact
and Hamming exclusions are verified even with this residual provenance limit.

## Primary patient/study composition and dependence

| Original cohort | Source study DOI | Patients | N | Positive | Negative |
| --- | --- | ---: | ---: | ---: | ---: |
| Basket | `10.1101/2024.03.17.585416` | 20 | 2,034 | 51 | 1,983 |
| bladder | `10.1038/s41467-022-29342-0` | 24 | 3,255 | 84 | 3,171 |
| melanoma | `10.1172/JCI150535` | 26 | 2,499 | 92 | 2,407 |

All three diagnostic strata retain all 70 patients. Primary spans 81 source
Sample identifiers. Per-patient and exact HLA counts are frozen in population
reports; primary HLA-A/B/C counts are **2,909 / 2,826 / 2,053**. Exact encoding
support is distinct from fitting-population representation: these HLA-C
observations extend beyond the project's A/B-restricted fitting views.

Identity-only connected components join observations sharing patient OR peptide.
Counts are **28 (≥2), 38 (primary ≥3), 65 (≥4)**. Primary's largest component
contains **2,475 observations from 21 patients**; treating all 7,788 rows as
independent would overstate precision. Shared peptides across studies reduce
study/peptide components to **one (≥2), one (primary), two (≥4)**. These memberships
are already frozen, before any future model prediction.

The locked protocol predefines paired patient/peptide-component bootstrap
uncertainty and a separate study-component sensitivity analysis. Primary study-
bootstrap intervals will be unavailable because only one independent study
component remains; ≥4's two components are also too few for reliable study
generalization. This limitation does not promote another threshold to primary.
Low prevalence, uneven patient influence, candidate preselection, multimer
endpoint differences and sparse allele-specific positive counts remain material
limits, despite 227 primary positives. No bootstrap was run in Task 2.26.

## Frozen A/S/P and future Task 2.27 specification

The original complete final IM file maps were authenticated without deserializing
or loading a model:

| Arm | Frozen canonical file-map SHA256 |
| --- | --- |
| A | `b92308ab3e35d02530867053ada7e29ee18076bf653df26458f5c3728a2be3a0` |
| S | `9d5a5012d38b0f7f7203c35769a5a29e35572ced3b8f708a525c03a99996862a` |
| P | `01014a37c3a4101f90d7765e48420a463a7094169a8c0163fc5994dc4a0c903b` |

The separate [locked protocol](BIGMHC_THIRD_PARTY_EVALUATION_TASK2_27_PROTOCOL.md)
has SHA256 **`6139b8a850224781d71768949f6a138ebdfdc111547222cd4ba1c935649df0c9`**. It fixes primary non-interpolated AP on ≥3,
secondary AUROC/P@10/P@20, prevalence, AP−prevalence and AP/prevalence, and
prespecified ≥2/≥4 diagnostics. It requires A/S/P and S−A/S−P/P−A on identical
rows, exact tied-score conventions, preserved final IM weights, deterministic
native inference, all predictions frozen before outcome association and paired
patient/study dependence handling. It prohibits adapting eligibility or choosing
the most favorable diagnostic result. Insufficient classes/units yield explicit
uncertainty limitations rather than a changed population.

No future evaluation is authorized by this curation task. **The benchmark and
evaluation specification are fully frozen and ready for one separately authorized
A/S/P evaluation**, with the stated assay/provenance/dependence limitations.

## Focused validation, execution evidence and artifacts

**13 focused tests passed**, zero failures/errors/skips. Tests cover exact packed
Hamming and indexed search versus small brute-force examples, distances 0–9,
the distant-query fallback, original assayed sequence retention, binary outcome
mapping, duplicate/context handling, nested thresholds independent of labels,
and patient/study/peptide connected components. No broad historical audit ran.

The [completion verifier](../scripts/verify_third_party_hard_split.py) passed:
**35 frozen artifacts**, **seven reference sets**, **62,139 valid nearest-reference
witnesses**, ordered threshold/outcome manifests, dependence clusters, census
and unchanged final IM file maps. It performs no model inference/performance
calculation and opens no Task 2.25 prediction or metric file.

Actual curation execution: **44.66958926501684 seconds**, excluding source
acquisition and code/report preparation. Peak host RSS **326,971,392
bytes**, Python **3.13.5**, platform
`Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.43`. CPU-only curation; Torch was not imported and
no GPU/model validation is claimed for this task. No dependency was added.

All derived outputs are under resolved project runs /
`task-2_26-third-party-hard-split/`:

- Original source acquisition, publication-assay evidence and compatibility reports.
- `cohorts/source_observations.jsonl`, `candidate_9mers.jsonl`, compatibility exclusions.
- `references/*.txt.gz` plus source identity/census hashes in `reference_freeze.json`.
- `similarity/unique_peptide_distances.jsonl`, observation-level distances,
  primary exclusions, exact-pair/HLA/core flags and per-reference search evidence.
- `cohorts/hamming_ge_{2,3,4}.jsonl`, identity-only files, original-outcome files,
  and both patient/study dependence component memberships.
- `threshold_populations.json`, `minimum_distance_distribution.json`,
  `overlap_assessment.json`, `benchmark_freeze.json`, tests and verification evidence.
- A copy of this interpretation, closed curation log and finalization manifest.

Frozen cohort metadata, identities, original outcomes, references, config and
future protocol hashes are persisted before Task 2.27. Source data and derived
outputs remain outside Git; code, small configuration and documents are committed.
**No training, model modification, A/S/P inference, model-performance calculation,
Task 2.25 prediction reanalysis, tuning, extra benchmark acquisition, merge or
push occurred. Work stops after this benchmark freeze.**
