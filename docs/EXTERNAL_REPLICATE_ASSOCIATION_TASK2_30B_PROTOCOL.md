# Task 2.30B — Locked external biological replication protocol

Frozen in Task 2.30A on 2026-10-21, before any Teacher predictions or stability
associations in this dataset. This is an external replication planned **after**
the exploratory SHERPA result was known, not a preregistration predating that
discovery. No execution is authorized by this document alone.

## Source, experimental population and fixed order

Use only authenticated MSV000099922 edited JY ΔBC W6/32 data from Cobos-Figueroa
et al., DOI `10.1016/j.mcpro.2026.101578`, as curated in
[Task 2.30A](EXTERNAL_REPLICATE_FEASIBILITY_TASK2_30A.md). HLA restriction is
source-defined classical HLA-A*02:01 after B/C editing, not computational
`Affinity_HLA` assignment. Preserve residual/nonclassical-HLA limitations.

The four original RAW basenames and roles are fixed:

1. ΔBC1 index technical Exp1: `Seq84886_HF`.
2. ΔBC1 index technical Exp2: `Seq84886_3-4_HF`.
3. ΔBC2 follow-up technical Exp1: `Seq84887_HF`.
4. ΔBC2 follow-up technical Exp2: `Seq84887_3-4_HF`.

The **biological index unit is ΔBC1**, selected by the first numbered clone in
the original experimental mapping. Both its technical measurements contribute
one direct-detection union. ΔBC2 is the single biological follow-up. Do not
choose one injection, reverse the clones, add other genotypes/antibodies, use
unmapped runs, or pool technical measurements as biological replicates.
The primary cohort is the fixed **496 unmodified canonical 9-mers** directly
identified in either index-clone measurement. The 1,472-peptide four-run union
and other lengths/chemical species remain descriptive and are not scored as
an alternate primary cohort.

Require these pinned Task 2.30A artifacts, under resolved project runs /
`task-2_30a-external-biological-replicate-curation/`:

- Primary `manifests/future_primary_index_cohort.jsonl`, SHA256
  `37d5247b7533243d4083142b9ec3dd4645eb8bcc344293908763cfb94bac5cd2`.
- `manifests/run_identities.jsonl`, SHA256
  `700c26f02842d7d6b49e28667f39082af8fe87927f88939401317d73f26f116b`.
- `matrices/unmodified_9mer_four_run_matrix.jsonl`, SHA256
  `be7ca2512342ffda5cbdf6362ad8c2ce008df7b08315dbdb49bc8fc212805e67`.
- Sensitivity IDs, SHA256
  `a7e6dbc0e53432fdd655556114318f3293142c014e9b0c742c8772b50aa61edd`.
- The final Task 2.30A dataset-freeze inventory, original processed inputs and
  source/evidence links. No dataset reconstruction or RAW reprocessing.

## Endpoint, model and one-time scoring

For each fixed index peptide define **Y=1 if directly identified in either
ΔBC2 measurement, otherwise Y=0**. Current source counts are 366/130. Keep the
two follow-up technical indicators and count 0/1/2 separately (130/182/184),
but do not mistake that count for two independent biological follow-ups.
This source-specific binary endpoint differs from SHERPA's count across two
reserved biological runs. Replication concerns direction in a new context;
coefficient magnitudes cannot be equated mechanically across outcome scales.

Use the recovered original Teacher, checkpoint SHA256
`a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99`.
Authenticate original source code, HLA-A*02:01 status, configuration and fitting
partition. No refitting, recalibration, architecture, model selection or external
predictor. Use original canonical 9-mer encoding and clipped log1p kinetic
half-life in hours. Score each of the 496 distinct index peptide–HLA pairs once,
save all finite outputs and source associations before computing associations.
Keep zero-floor ties and unsupported values explicit; do not change membership
or substitute scores on failure. No full-union scoring is needed.

Primary statistic: Spearman correlation of continuous deployed log1p stability
with binary Y, using average ranks for ties in both variables. The scientific
direction is positive. With one HLA/context, no across-context averaging is
estimable. N≥2 and nonconstant variables are necessary; flag N<30 or minority
outcome count<10 as sparse. Undefined values stay undefined; no alternative
index, confidence cutoff or subset is selected to rescue a result.

Preserve biological/peptide dependence by components sharing a biological
sample/clone or exact peptide. All current index observations share the same
two clones: **one component**. The whole-component bootstrap interval is
therefore **undefined**. Do not substitute row/peptide-independent confidence
intervals or nominal regression standard errors. Record conditional bootstrap
settings of 10,000 draws and `Random(228229)` but execute zero draws with fewer
than two components. This is a limited external-context replication, not
population inference across HLAs, cell lines, studies or independent clone pairs.

Use the same prespecified descriptive negative control as discovery: permute
score assignments across distinct peptides within HLA for 10,000 draws with
local `Random(228230)`, preserving original paired observations and run states.
Report the one-sided tail `(1+count(T_perm >= T_obs))/(1+usable_draws)` and
undefined draws. It requires peptide exchangeability, is confounded by sequence
families/detectability, and is not a biological-population significance test.
No asymptotic substitute, alternative seeds or favorably selected test.

## Prespecified secondary adjustment and sensitivity

The quantitative index covariate is frozen in the manifest: sum positive finite
MS1 intensities once per unique unmodified direct evidence feature within each
index run, then average the available positive run sums across the two index
technical measurements. No follow-up values enter it. This is relative MS1
feature abundance, not fragment intensity or absolute surface concentration.
There are 473 available and 23 missing values; keep all 496 observations.

Secondary descriptive adjusted model: ordinary least squares of binary Y on
an intercept, within-HLA stability percentile rank `(average rank-.5)/N`,
centered log2 index intensity and a missing-intensity indicator. Center log2
intensity using available index values; use centered zero plus the indicator
for missing values. If an indicator is constant, omit only that redundant
column by this predetermined rule. Report a rank-deficient design as undefined,
not an opportunity to change covariates. Report the rank coefficient as a
descriptive partial association with the same unavailable biological interval;
no nominal row-independent p-value or new model-performance endpoint. Do not
introduce PEP, hydrophobicity, protein or batch covariates after seeing results.
Residual measurement error and run normalization limitations remain explicit.

Fixed sequence-exposure sensitivity: retain only index peptides at minimum
Hamming distance ≥2 from **any actual Teacher fitting peptide across HLA**.
The frozen subset has **483 identities**, removing ten exact and three
one-substitution fitting neighbors. Reuse the saved 496 predictions, rerank
within this subset and report its same coefficient/negative control. Do not
introduce ≥3/≥4, alternate HLA-only filters or validation exclusion. Training
and validation exposure are separate: the primary has ten exact fitting
peptide–HLA overlaps and one exact validation overlap. Kinetic labels are not
MS-replication outcomes; report exposure without claiming automatic label leakage.

Describe all four frozen technical run states, clone-level union/counts, missing
intensity, stability distributions by binary outcome and fixed stability-rank
quartiles. Quartiles use `(average rank-.5)/N` upper bounds .25/.50/.75/1, without
splitting ties. Nested follow-up technical 0/1/2 summaries are diagnostics,
without additional hypothesis tests or promotion to the biological endpoint.

## Interpretation, quality caveats and stopping rule

Preserve source PSM FDR .05, source direct MS/MS evidence and original
reverse/contaminant exclusions. No new PEP threshold. State that processed
Protein FDR is literally `1`, differing from article .01; variable modifications
include acetylation omitted from the article's methods list; MBR is False.
These are reported quality/provenance limitations, not reasons to silently
reprocess spectra, strengthen confidence labels or tune inclusion.

Account for clonal editing/expression effects, unequal run depth, joint-search
context, MS intensity scaling, preparation/technical ambiguity, DDA stochasticity,
ionization/fragmentation, source confidence, index-selection conditioning,
residual HLA background and Teacher-sequence exposure. Do not pool this dataset
with SHERPA to manufacture biological replication or reanalyze SHERPA outcomes.
A positive descriptive direction is compatible with replication but does not
prove a causal kinetic-stability effect or generalization across biological
systems. An opposite/null result must be reported equally. No result proves
that low-stability EL positives are false or missing MS calls mean surface absence.

Save the fixed source/model references, once-only predictions, paired outcomes,
primary/secondary results, undefined intervals, tests, execution evidence and
scientific interpretation under a separately authorized Task 2.30B run. No
model or cohort changes, additional benchmarks or follow-up experiments may
be triggered by results. **Task 2.30A stops at this protocol and dataset freeze.**
