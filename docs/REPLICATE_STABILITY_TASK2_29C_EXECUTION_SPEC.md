# Task 2.29C — Execution specifications frozen before prediction

The Task 2.29 protocol and Task 2.29A amendment remain authoritative. This record
resolves implementation details before any SHERPA Teacher prediction or
stability–repeat association. Task 2.29C explicitly authorizes their execution.
No scientific endpoint, index choice, model or primary cohort changes.

Primary: the original ordered 671 HLA-A*02:01 index peptides. Use the original
Teacher once per peptide–HLA pair. Spearman uses average ranks for ties on both
deployed clipped log1p-half-life and Y = reserved detection count / 2. Correlation
with count 0/1/2 is identical because this is a positive linear scaling.

There is one biological dependence component, comprising the same three sample
units and all 671 observations. The protocol specifies no interval with fewer
than two components. Therefore the confidence interval is **undefined** and
bootstrap draws are not attempted. No peptide bootstrap or asymptotic interval
is substituted. The fixed one-sided negative control shuffles score assignments
within HLA for 10,000 draws using local `Random(228230)`. Report
`(1 + count(T_perm >= T_observed))/(1 + usable_draws)`, explicitly descriptive
and dependent on exchangeability. Integer doubled average ranks permit exact
comparison of tied permutation statistics without a numerical tolerance.

Report exact peptide–HLA and peptide-only exposure to original training and
validation rows separately. Compute exact minimum unweighted Hamming distances
to A*02:01 fitting sequences and to all-HLA fitting sequences, with witnesses.
The single prespecified exposure sensitivity excludes all exact/one-substitution
neighbors of **any** actual Teacher fitting peptide, globally across HLA. This
implements the original protocol's fitting-exposure exclusion conservatively;
it also removes every such A*02:01 neighbor. It does not additionally exclude
validation exposure. Freeze sensitivity identities before predictions. Apply
the same correlation and descriptive negative-control method to that fixed
sensitivity cohort; do not select another threshold or subgroup from results.
Peptide-only exposure to another HLA is not direct fitting exposure of the
A*02:01 coefficient model and will be distinguished explicitly in interpretation.

For the user-authorized descriptive rank strata, freeze quartiles using
`(average_rank - 0.5)/N` with upper bounds .25/.50/.75/1, assigning an entire tie
block by its average rank. Do not split ties to make equal group sizes. Report
the count distribution, both follow-up detection rates and mean Y in every
quartile. These are descriptions, without extra significance tests. Likewise
report half-life distributions by count 0/1/2 and by separate binary follow-up
patterns. No alternative outcome-specific regression or cutoff search.

The existing curation established that quantitative index precursor abundance
and individual q values are unavailable. No RAW or new source search is needed.
Fragment-ion intensity is not the protocol's intensity covariate. The specified
abundance-adjusted model is therefore unavailable; do not fit an all-missing
covariate model or introduce sequence/quality covariates after seeing results.
Preserve explicit missing values and state residual abundance confounding.

Preparation authenticates the handoff and frozen source identities, accepts
every unchanged Teacher input without scoring, records exposure and missing
covariates, and freezes ordered primary/sensitivity identities and component
membership. Inference saves the entire ordered prediction set before analysis.
Association reads only that saved prediction set and the frozen design. Original
datasets/checkpoints, earlier reports and historical benchmark predictions are
not modified. Plotting uses saved descriptive summaries; it cannot change them.

Machine-readable specification:
`configs/replicate_stability_association_task2_29c.json`. Numeric thresholds,
seeds, ties, exposures, unavailable adjustments and ordered runs are fixed there.
No model fitting, calibration, auxiliary model, new replicate condition or
unapproved cohort is part of this task.
