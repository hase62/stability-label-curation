# Frozen local MixMHCpred/SPEARMINT scoring protocol — Task 2.39

Frozen on 2026-10-26 on Z790/WSL2. This document authorizes **no benchmark inference**. Task 2.40 requires a separate user request. Task 2.39 only authenticates artifacts, constructs outcome-free identities, audits coverage/exposure, and runs the two fixed public smoke peptides. No immunogenicity outcomes or historical prediction files were accessed.

## Artifact and input lock

The authoritative machine-readable registry is `configs/modern_models_task239.json`, with explicit tensor/column schemas in `configs/task239_input_output_contracts.json`. Dependency resolutions are `configs/task239_mixmhcpred.lock.txt` and `configs/task239_spearmint.lock.txt`; public HLA checksums/accessions are in `configs/task239_hla_reference_checksums.json`. Private manifests and execution receipts remain outside Git in the Task 2.39 run directory, resolved with `stability_label_curation.paths`.

| Predictor | Frozen revision | Native score |
|---|---|---|
| MixMHCpred v3.0 | `0a7f9b9e20d1cf02236f4a0a90d16735be879b38` | `Score_<designated allele>`; higher is better |
| SPEARMINT Stage 3 | `93e8e3e640e49e5a373f0dc432b122df19e4b969` | predicted `log1p(half-life hours)`; higher is better |

SPEARMINT metadata are fixed to **SPA (index 0), 37.0°C**. Retain native outputs without clipping, sign reversal, outcome-dependent normalization, calibration or conversion to a purported measured lifetime. Use SPEARMINT batch size 4. The full heavy chain, including signal, transmembrane and cytoplasmic regions, is used. No pseudosequence substitution or nearest-allele fallback is permitted.

Use the authenticated local SPEARMINT snapshot, its original tokenizer and model class, safetensors only, FP32/eval/inference mode, TF32 disabled, deterministic algorithms, and `CUBLAS_WORKSPACE_CONFIG=:4096:8`. Block pickle fallback and remote snapshot loading. The compatible runtime uses Transformers 4.57.1, rather than the 4.30.2 serialization-version field in the original config; the upstream explicit state-dict loader is retained unchanged. The complete installed resolution is captured, including the existing read-only CUDA PyTorch installation. Do not replace drivers or system CUDA libraries.

MixMHCpred uses its pinned official launcher, `-a` designated allele, `-m 0`, a dedicated environment and new output paths. No installation script, `setup_path`, PRIME, sequence-alignment `-s` path, or motif-output deletion path is invoked. Its distributed object-NPY files have been authenticated and statically inspected; do not admit arbitrary new pickles. The intended use is academic non-commercial research under the distributed license. Do not redistribute the release.

## Population and identity lock

The input is the already outcome-free Task 2.32 `cohorts/IMPROVE_identities.jsonl`:

- SHA256: `33fbad5f142a93d0803b39800fa3dcb71437320c4134e92594080830b6f26986`.
- Exactly **7,788** original observations, **6,576** peptides, **7,750** peptide–HLA pairs, **36** HLA alleles, **70** patients and **3** studies.
- Ordered row-key hash: `8118663ebf5c23de8f36a7a7c15aa0247a0609e04ade927657528d2986f6fee9` (compact UTF-8 JSON array; no whitespace).
- Common coverage is **all 7,788 rows**, in the original order; the common ordered-key hash is identical. No original observation was removed or deduplicated.
- Retain the original **38 patient/peptide dependence components**; A*02:01 is a prespecified secondary subgroup of **616** observations in **16** original components.

The private `common_coverage_row_keys.json`, allowlisted identity table, `coverage.jsonl`, HLA reference file and provenance receipt are the future scoring inputs. Verify their hashes and exact ordered keys before scoring. Do not recreate the hard split. Keep repeated patient-specific observations. Never inspect published prediction columns or reinterpret restricting HLAs. The Task 2.35/2.36 two-HLA gate decisions remain unchanged and are unrelated to this pan-HLA comparison.

Eligibility is determined solely by canonical peptide/length support, exact allele mapping, authenticated full-length HLA sequence and required metadata. No binding-score filter, IM outcome, earlier performance, source-training overlap, or favorable HLA selection enters eligibility. Exposures are reported separately and do not trigger additional cohort attrition. If these frozen inputs become unusable, stop for protocol review; do not substitute A*02:01 as primary.

## Score mapping

For MixMHCpred, group observations by their **designated HLA**, retain original within-group order, and map results back to the frozen global row keys. Read `Score_A0201`, for example, for A*02:01. Save the matching `%Rank_A0201` separately. Never use `Score_bestAllele`, `%Rank_bestAllele`, donor-genotype maxima, or the nearest-reference metadata as a replacement score. The v3.0 output is rounded to six decimals by upstream; preserve those ties. C*03:04 has C0303 as a tied nearest reference at distance zero, but its **direct C0304 score remains required**.

For SPEARMINT, construct chains with the original tokenizer, peptide chain ID 0 and full-HLA chain ID 1; supply SPA and 37.0 explicitly. Validate finite outputs, exact row association and batch lengths. Preserve source keys, native scores, model identity, assay and sequence hash. Do not use other assay heads, Stage 1/2 scores, or change temperature.

## Frozen rank and fusion definitions

Keep three distinct analyses: native pooled scores; within-HLA ranks; fixed rank fusion. For each predictor, on the **same complete common-coverage observation population**, define the higher-is-better within-HLA percentile as

`r = (number of strictly lower scores + 0.5 * number of equal scores) / N_HLA`.

Repeated biological observations retain their multiplicity. All ties receive the same rank; a singleton receives 0.5. No jitter, outcome-based tie break or label-derived HLA weighting is permitted. Freeze ranks once on the original common population, before uncertainty resampling; do not recompute them on each resample.

The fixed fusion is `0.5 * r_EL + 0.5 * r_stability`. The EL-only rank comparator is **the same `r_EL`**, so an effect of rank transformation is not mistaken for an effect of fusion. No fitting, learned normalization or coefficient search is authorized. These are cohort-relative rankings, not clinically calibrated probabilities. A beneficial fusion alone does not establish independent causal information from kinetic stability.

## Future endpoints and uncertainty

The primary metric is pooled **non-interpolated AP** on the original common-coverage full IMPROVE cohort. Report native EL, native stability, EL rank, stability rank and fixed fusion. Keep the native stability-minus-EL comparison and fusion-minus-EL-rank comparison distinct and prespecified; do not choose whichever is favorable. Secondary reports are AUROC, prevalence/AP relative to prevalence, and descriptive A*02:01 and other-HLA summaries where defined. Do not switch the primary endpoint or population based on results.

AP groups identical score thresholds: sum recall increments times precision at the end of each tied-score group. AUROC uses half credit for ties. If top-K precision is reported, use fractional inclusion of a tied boundary group (expected precision under random ordering within the tie), without label-based ordering. Undefined metrics, including single-class resamples, remain undefined.

Use paired cluster resampling of the **original patient/peptide components**, with replacement, preserving every row within a drawn component and using exactly the same draw for all score conditions. Use **10,000** replicates, `random.Random(24040).choices` over lexicographically sorted original component identifiers (draw the original number of components), and 2.5/97.5 percentile intervals with linear interpolation over sorted valid differences. For A*02:01, retain the original 16 components rather than reconstructing components after filtering. Keep ranks fixed as above. Report valid/invalid replicate counts, sampled component sizes and limitations. Seeds and resampling settings here are a prospective local reconstruction; no unprovided Mac settings are claimed to have been recovered. Individual rows and patients linked by shared peptides must not be treated as independent units. Do not fabricate a study-bootstrap interval for the single study/peptide connected component.

Report exploratory paired AP intervals for native stability–EL and fusion–EL-rank, with other rank comparisons descriptive. No population-level significance claim follows solely from these intervals. Do not alter models or eligibility in response to results.

The historical 267-row Neoepitope cohort is **deferred optional descriptive evidence**. It was not processed, scored or reselected in Task 2.39. Its identity/common coverage and peptide-cluster resampling must be authenticated in a separately authorized evaluation before use; it cannot replace IMPROVE if results are unfavorable.

## Interpretation boundaries

Both external benchmarks have prior evaluation exposure. Source identity audits do not establish untouched confirmatory independence. S2/S3 stability training/validation/test occurrence, sequence-neighbor exposure, underlying study overlap, and unknown MINT Stage 1 BA/PPI and MixMHCpred EL ancestry are different quantities. The stability-only fitting objective does not establish that every upstream development choice was blind to IM outcomes; upstream selection history remains incompletely verified.

No exact S2/S3 exposure does **not** mean leakage-free ancestry. Full-length input compatibility is not evidence of equivalent accuracy for every HLA. Predicted kinetic half-life is distinct from measured thermal melting temperature, EL presentation, repeat MS detection, and T-cell recognition. No claim about false-positive EL labels is warranted. Defer all IM metrics and scientific comparisons to a separately authorized Task 2.40.
