# Task 2.29 — Conditional within-HLA stability and repeat-detection protocol

Prepared in Task 2.28 on 2026-10-20 before any stability prediction or
stability–repeatability association on these sources. This document authorizes
neither prediction nor analysis in Task 2.28. A future Task 2.29 requires explicit
researcher authorization and all scientific gates below.

**Current readiness: blocked for an allele-specific association.** The frozen
PXD006939 curation has zero observations with established peptide-specific HLA
restriction; all samples are multi-HLA. The frozen Teacher JSON is also absent
on this WSL2 machine. A documented genotype is not an allele assignment. The
curated data support descriptive MS reproducibility, which Task 2.28 reports.
They do not by themselves support the proposed primary stability test.

## Biological question and estimand

Question: within an established human HLA-I restriction, does higher predicted
peptide–MHC kinetic stability associate with more frequent direct MS/MS detection
in comparable repeat measurements? The directional hypothesis is positive.

The endpoint is detection under the specified acquisition/search procedure.
It is not cell-surface absence, a false EL label, universal presentation,
immunogenicity or repeated T-cell recognition. Teacher outputs estimate kinetic
half-life, not thermal melting temperature. An observational association does
not establish a causal effect of pMHC dissociation on MS detection.

Task 2.28's union-based matrices remain descriptive, conditional on identification
in at least one run. The future primary estimand is more specific: **repeat-run
detection frequency conditional on direct detection in a fixed index unit**.
This avoids defining the primary index cohort using its future repeat outcomes.
Do not add undetected hypothetical peptides or synthetic negative labels.

## Mandatory pre-prediction gates

1. Authenticate the final Task 2.28 freeze and source/run/condition identities.
   Preserve its complete original matrices and exclusions. Do not reinterpret
   one-run detections as erroneous positives.
2. Require an authentic monoallelic system with adequately documented residual
   HLA expression, or independently established peptide-specific restriction.
   Genotype alone, binding predictions, deconvolution and Teacher scores cannot
   assign restriction. C1R transfectants are not automatically allele-pure;
   residual endogenous HLA must be addressed experimentally.
3. Require at least three genuinely comparable replicate units, their hierarchy
   and available acquisition/QC records. Instrument, preparation and biological
   endpoints remain separate. Treatments, doses, cell inputs, patients, organs
   and unequal fractionation are not exchangeable replicates. Reprocessing an
   existing RAW file never creates another measurement.
4. Require canonical, actually assayed 9-mers, direct-versus-transfer identities
   and chemical modification information adequate for the unmodified Teacher.
   Source peptide-table base-sequence aggregation alone does not establish an
   unmodified molecular species. Known synthetic-standard identifications and
   unresolved heavy/light counterparts cannot enter the endogenous primary
   analysis. Preserve these records outside that primary cohort.
5. Require the exact frozen Teacher from Task 2.3, SHA256
   `a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99`,
   with its original support/validation and fitting-partition metadata. No
   refitting, calibration, new allele model or nearest-allele fallback. Map HLA
   names through explicit exact-identity normalization; report unsupported or
   weakly validated models. Preserve training-exposure flags separately from
   detection outcomes.
6. Freeze actual eligible identities, index/repeat units, sample/peptide
   dependence components, known covariates and counts before prediction. Do
   not optimize source choice, thresholds or HLA subsets using stability or
   prior A/S/P results. No A/S/P inference is part of this protocol.

These gates currently yield **N=0**. Task 2.29 must report that limitation if
unchanged. Restoring original model bytes would require no retraining, but
would not resolve multi-HLA attribution. Any additional monoallelic acquisition
or newly established restriction needs separately authorized curation and a
committed cohort amendment before predictions. Do not silently promote another
dataset or an inferred HLA assignment to primary.

## Index, repeat and score definitions if the gates become satisfiable

Within each preapproved comparable group, sort original preparation/run-unit
identities deterministically by their frozen published order. The first unit is
the index; the others are reserved repeat opportunities. Choose this order
without comparing detection richness, stability or correlations. Include valid
peptides directly identified in the index unit, regardless of repeat detection.
Do not require identification in two runs as an inclusion criterion.

For peptide i in sample/group g, define Y_ig as the number of reserved units with
at least one accepted direct MS/MS identification divided by the number of
available reserved units. An MBR-only identification is not a direct MS/MS
success; preserve it as a separate state. A performed run without an identified
peptide contributes zero, while an unavailable/failed acquisition is missing,
not a nondetection. Availability exclusions must be documented using acquisition
QC before peptide outcomes are analyzed, and applied uniformly to all peptides.

Use the frozen Teacher continuously in its original deployed log1p-half-life
space; preserve clipping/ties and unsupported results. Obtain scores only once
for each distinct eligible peptide–HLA pair. Within each HLA, use average ranks
for tied scores. No low/high stability cutoff, stability-based filtering,
coefficient change or score-dependent cohort revision is allowed.

The current RA957 preparation units aggregate their two recorded instrument
injections fairly and preserve their three separate instrument diagnostic
matrices; those overlapping endpoints must not be pooled as independent samples.
They remain outside primary because restriction is unresolved. Likewise the
alternative CD165 1e8 search view is not a new replicate group for inference.

## Prespecified association summaries and dependence

Primary effect: Spearman correlation of continuous Teacher stability and Y_ig
within each established HLA × independent sample/group, with average ranks for
ties in both variables. Summarize by averaging valid group correlations within
each HLA, then averaging equally across evaluable HLAs. Report every group/HLA
coefficient, N, score/outcome diversity and undefined value. The target is an
equally weighted HLA/context summary, not a peptide-count-weighted population
effect. Constant scores/outcomes or insufficient observations make a group
correlation undefined; retain that cohort and report it rather than finding a
different split. Fewer than 30 index peptides per group is flagged as sparse,
without redefining inclusion or adapting the primary endpoint.

For uncertainty, form identity-only connected components sharing independent
biological sample/donor OR exact peptide, retaining all related preparation,
condition and instrument observations within a component. Freeze these units
before prediction. Sample the same fixed number of whole components with
replacement for 10,000 draws using local `Random(228229)`, preserving repeated
observations with multiplicity and recomputing the same predefined summary.
Use percentile 95% intervals with linear interpolation at `(n−1)q`, q=.025/.975.
Report component sizes, usable/undefined draws and all empty or constant groups.
Fewer than two components gives no interval; fewer than 20 components or 1,000
usable draws is explicitly unreliable. Do not substitute row-independent
intervals when shared peptides connect samples. Report study-level dependence;
one source study cannot support study-population generalization.

A prespecified negative control permutes score assignments between distinct
peptides within each HLA, using the same permuted peptide score across every
sample/context containing that peptide. Outcomes, run availability and peptide
dependence remain fixed. Use 10,000 draws and local `Random(228230)`. Report the
one-sided descriptive permutation tail fraction `(1 + count(T_perm >= T_obs)) /
(1 + usable_draws)` and undefined draws. This control requires exchangeability
within HLA and does not remove abundance, sequence or protein-family confounding;
it cannot establish causality. No permutation-based source/subset selection.

## Predefined secondary descriptions and confounders

- Report direct detection count/frequency distributions in the fixed full union
  and index-conditioned cohort. MBR-inclusive frequencies are separate transfer
  diagnostics and cannot replace the direct endpoint.
- Describe instrument, preparation and biological results separately, including
  group sizes, equal cell inputs, injection fractions, acquisition depth and QC.
- If quantitative index intensity is available, report a fixed abundance-adjusted
  descriptive linear regression of Y on within-HLA stability rank, index log2
  intensity and sample/group fixed effects. Missing/zero index intensity gets a
  missingness indicator and centered zero covariate value; it does not exclude
  a directly identified peptide. Use the same whole-component bootstrap for the
  stability coefficient. Report rank-deficient designs as undefined. This is a
  sensitivity analysis, not a causal adjustment or primary-model replacement.
- Use only index-run or independent protein/RNA abundance and identification
  covariates. Do not condition on repeat-detection-dependent intensity or the
  source table's best PEP pooled across index and repeat runs. Where independent
  expression is unavailable, report residual confounding rather than inventing
  expression values or imputing nondetection as low expression.
- Report source-protein ambiguity, hydrophobicity/ionization and fragmentation
  bias, DDA precursor selection, FDR/PEP definitions, processing batch and
  modification ambiguity. Hamming/protein families and repeated peptides can
  retain dependence beyond the recorded sample hierarchy.
- Flag exact and one-substitution exposure to actual Teacher fitting sequences
  if the authenticated fitting partition becomes available; report a fixed
  exposure-excluded sensitivity without promoting it to primary. BigMHC fitting
  exposure is a distinct provenance category, not Teacher leakage by definition.

No synthetic negatives, stability association, resampling, permutation or
regression was executed in Task 2.28. No result may trigger training, EL-label
flipping/removal, tuning or a follow-up experiment without separate approval.
An imprecise, absent or opposite association is reported as such; none proves
that an EL observation is false or that the frozen Teacher is experimentally
calibrated for MS reproducibility.
