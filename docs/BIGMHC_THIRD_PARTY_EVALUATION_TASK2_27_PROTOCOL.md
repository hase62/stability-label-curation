# Locked Task 2.27 — Third-party sequence-hard A/S/P evaluation

Version 1, fixed in Task 2.26 before any A/S/P inference on this source.
Task 2.26 authorizes curation, distance filtering and freezing only. Task 2.27
requires separate explicit evaluation authorization. No A/S/P inference or model
performance calculation is part of Task 2.26.

## Models and source

Reuse exactly the three final EL-10 / full-IM-20 checkpoints from Tasks 2.23/2.24:

| Arm | Checkpoint under resolved project runs | Canonical file-map SHA256 |
| --- | --- | --- |
| A | `task-2_23-el-multiepoch-baseline/checkpoints/final_all_IM` | `b92308ab3e35d02530867053ada7e29ee18076bf653df26458f5c3728a2be3a0` |
| S | `task-2_24-fully-trained-stability-auxiliary/checkpoints/S_IM_epoch_20` | `9d5a5012d38b0f7f7203c35769a5a29e35572ced3b8f708a525c03a99996862a` |
| P | `task-2_24-fully-trained-stability-auxiliary/checkpoints/P_IM_epoch_20` | `01014a37c3a4101f90d7765e48420a463a7094169a8c0163fc5994dc4a0c903b` |

Authenticate these files and frozen tensor identities before inference; do not
substitute EL-only models. No auxiliary head, new training, calibration, model
selection, architecture change, additional seed, coefficient tuning, threshold
optimization or ensembling. All arms use the same pinned authentic BigMHC source,
exact HLA pseudosequence mapping, eval mode, batch16, deterministic CUDA FP32,
AMP/TF32 off and original sigmoid IM probability. No nearest-HLA imputation.

Use Borch et al., IMPROVE, DOI `10.3389/fimmu.2024.1360281`, repository
`SRHgroup/IMPROVE_paper` at `c67094276b52358b5202ad9e5597acd87888ea1d`,
`data.zip` member `data/01_data/01_Validated_neoepitopes.txt`. Archive SHA256
`adf02eb5054a8aa4b6eccd3b6e0ff1200889d41ae05655fd6e55c5c347f720d9`;
member SHA256 `b27854c98a34b6bb83af248979cc3ea121534fa2e8d9e97415654dc0c0a95c95`.
The observed endpoint is the authors' screened pMHC multimer T-cell recognition
summary, not a direct functional cytokine response or endogenous presentation
measurement. Positive means recognized in at least one sampled patient material;
negative means not recognized in that screen, not universally non-immunogenic.
Candidate-selection binding predictions do not replace experimental response.
No long peptide's response may be assigned to a predicted 9-mer core.

## Immutable observations and hard split

Use the source member's original row as the observation, retaining raw `identity`,
`Patient`, `Sample`, `cohort`, peptide, HLA and response fields. Preserve repeated
peptide/pair and patient-level observations. The Task 2.26 configuration defines
outcome-independent row handling; contradictory copies of the same original ID
are quarantined as a whole. Different patients' differing responses remain
distinct. No source reconstruction, genotype-based HLA inference or synthetic
negative creation is allowed. Normalize peptide only by strip/uppercase and use
the exact existing HLA resolver and reference membership. Keep valid canonical
9-mers with original experimental pMHC and unambiguous binary response.

Freeze reference identities separately for actual fitting (1,308,196 EL rows;
all 3,428 IM rows), EL epoch selection (145,371 EL validation rows), historical
IM development and earlier 686-row IM epoch selection (now also fitting data),
and the original published Mendeley test plus the actually evaluated subset.
Prior test exposure is not neural-network fitting exposure.

The primary rule is **minimum unweighted Hamming distance >=3 from the union
of fitting and model/epoch-selection canonical 9-mer sequences**. Exclude exact
peptide overlaps with all valid 9-mers in the original 937-row Mendeley benchmark,
regardless of HLA. Diagnostic strata use the same safeguards and distance >=2
and >=4. These thresholds are fixed; labels and model scores cannot select or
alter them. Similarity to the prior benchmark beyond exact matches is reported
separately and does not add a new exclusion. Hamming is same-length, ungapped
exact amino-acid identity; shared shifted cores and mutation families are
descriptive, not additional exclusions.

Task 2.26 freezes ordered identities, outcomes, distance witnesses, references,
patient/study composition, and clustering in the run's `reports/benchmark_freeze.json`
and its hashed `cohorts/` files. Task 2.27 must authenticate that receipt and its
protocol/configuration hashes. If it is not ready or a cohort lacks adequate
class diversity, report that limitation without substituting a threshold/source.
Do not adapt cohort eligibility after any performance is observed.

## One future evaluation and endpoints

After separate authorization, score each arm once on the ordered union of the
three fixed strata (the >=2 stratum), then obtain >=3 and >=4 results by immutable
membership. Retain source coordinates and all full FP32 probabilities. Before
joining outcomes, freeze all three prediction files and verify complete identical
row coverage, finite scores, native emitted order and unchanged model tensors.
Missing/nonfinite rows stop comparisons; never drop rows from one arm alone.

Primary endpoint: non-interpolated average precision on the >=3 primary cohort.
Group exactly tied scores at one threshold and sum recall increments times
precision, with no interpolated precision envelope.

Secondary: primary AUROC (half credit to positive/negative ties), Precision@10,
Precision@20, positive prevalence, AP minus prevalence and AP divided by
prevalence. Report the latter ratio unavailable when prevalence is zero. K>N
is undefined and is never replaced. Top-K ties are ordered by canonical peptide,
canonical HLA, study DOI, patient ID, then immutable source-row locator. Report
tie groups and boundary ties. Diagnostic >=2 and >=4 strata report AP/AUROC,
class counts, prevalence and the same prevalence-relative AP quantities; they
cannot replace the primary result. No new HLA/patient subset endpoints or model
selection on diagnostic difficulty is allowed.

For each defined endpoint, report A/S/P and exactly S−A, S−P, P−A on identical
observations. Accompany every population with N, positives/negatives, unique
peptides/pairs/HLAs, patients, studies and prevalence. With either outcome class
absent, report counts and no discriminative comparison. Flag N<20 or fewer than
five in either class as very limited. Small counts never relax eligibility.

## Paired uncertainty and dependence

Use 10,000 paired bootstrap draws and local `Random(262742)`, fixed cohort order
>=3, >=2, >=4. Primary clustering is connected components of observations that
share a canonical peptide OR share a patient (namespaced by source study).
Preserve every observation in a selected component with multiplicity; sample
each cohort's fixed number of components with replacement. Use the identical
resampled rows for all arms/endpoints and paired contrasts within that cohort.
Do not assume multiple rows from the same patient are independent peptides.

Also report the prespecified study-dependence sensitivity analysis: connected
components sharing study DOI OR canonical peptide, using a separate local
`Random(262743)` stream and the same 10,000 paired-draw procedure. Three source
studies provide very few independent study units; those intervals are descriptive
and explicitly unreliable, and may be unavailable if fewer than two components
remain. This sensitivity analysis cannot replace the primary patient/peptide
analysis or support broad study-generalization claims.

For both analyses use sorted percentile 95% intervals with linear interpolation
at index `(n−1)q`, q=.025/.975. Report undefined draws and use only jointly
defined paired draws. Fewer than 1,000 usable draws or 20 independent components
are unreliable; fewer than two components yields no interval. Freeze both sets
of component memberships in Task 2.26 using identities alone. Low prevalence
may make top-K and AP highly discrete and bootstrap intervals unstable; report
that uncertainty without optimizing a split, seed or threshold.

## Interpretation and stop

Assess whether S improves over both A and P on the >=3 primary AP. An S−P
advantage without S>A is insufficient for useful stability-specific improvement.
All comparisons are frozen single-seed descriptive evidence; no formal
multiplicity-adjusted superiority claim is planned. Clearly distinguish
multimer recognition from other immunogenicity assays and distinguish model-
fitting/selection exposure from previously evaluated benchmark exposure.
Incomplete upstream assay/patient source linkage, repeated measurements,
candidate selection, HLA coverage and three-study dependence remain limitations.
No result measures EL-label errors or repeated EL detection. Stop after the
single future comparison; it authorizes no triggered follow-up experiments.
