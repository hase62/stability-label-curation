# Task 2.35 — Prospective data-only eligibility rules

Frozen on 2026-10-23 JST before this task loads IM outcome manifests or tabulates
candidate HLA-specific class counts. Earlier cohort counts/results are already
public within this project, so this is computational label separation, not a
claim that the sources or their outcomes were previously unseen.

No training, inference, model loading, GPU access, score-file access, IM
performance calculation, CapsNet access or historical artifact transfer.
Use Jappe 2020 DOI10.1038/s41467-020-20166-4 original Supplementary Data3/4,
Task2.23's actual authoritative EL fitting/validation manifest, and Task2.32's
exact ordered external identity/outcome manifests. Stop on inconsistent source
counts: finite distinct peptides1094/1354; canonical nine-mers711/782.
Preserve original Celsius Tm, source row/cell/file, every quality flag, the five
expected unresolved repeated-minimum flags, and all genuine observations.
No clipping/imputation, censoring reinterpretation or outcome-based deletion.
Target y=0.5+(Tm_C-37)/72 must be finite and within[0,1] for every nine-mer.
Measured thermal melting temperature is not measured kinetic half-life.

Peptide normalization: strip outer whitespace, uppercase, no internal edits,
canonical amino acids ACDEFGHIKLMNPQRSTVWY, exact length9. HLA identities are
exact canonical source/manifests, no prediction or approximate mapping.
Measure exact peptide-HLA and peptide-only overlaps separately. Hamming only
compares equal-length canonical peptides; no artificial mismatch for other
lengths. Report full exact minimum distances and 0/1/2/>=3 bins, including
same-HLA and allele-agnostic references, with authentic witnesses.

**Preferred fixed leakage policy: protect both complete frozen external IM
cohorts.** Exclude prospective measured-Tm fitting sequences at Hamming<=2 from
ANY compatible-length peptide in either cohort, regardless of HLA or IM label.
All original IM observations remain unchanged. Apply the same protection to any
prospective adaptation decoys. Exact HLA-pair overlaps remain descriptive and
cannot relax the allele-agnostic protection. Freeze source and retained identities
before any outcome loading. Compare, but never select using class balances, the
alternative: retain full Tm panel, exclude IM rows within Hamming<=2 of any Tm
peptide, with identical sequence-only rules. Alternative masks are diagnostic
copies, never modifications of original frozen cohort manifests. Report both
training and evaluation attrition and per-HLA retention. Do not switch policies
if one has more favorable class balance. Exact/near historical baseline exposures
are descriptive and cannot be undone by a new adaptation exclusion. Do not use
EL validation for selection or claim it remains independent if adapted Tm peptides
expose it.

**Minimum exploratory support, fixed before current outcome tabulation:** each
HLA must have >=10 positive IM observations, >=30 negative IM observations and
>=5 frozen independently resampleable dependence components. Existing per-HLA
AP-reporting rules (N>=20,>=5 per class) are weaker and do not supersede this gate.
Both A*02:01 AND B*07:02 must pass for the intended two-HLA primary comparison.
Reuse global frozen patient/peptide components for IMPROVE, even within HLA
subsets; do not split components to inflate support. Neoepitope uses canonical
peptide clusters; unknown patient/assay dependence remains unresolved. Report
components carrying positives, patients/studies and dominant-component sizes.
Insufficient support => NO-GO for the intended two-HLA primary; single-HLA
feasibility is descriptive, never an automatic replacement primary.

Provisional future primary: equal-weight macro of non-interpolated within-HLA
IM AP over A*02:01 and B*07:02 in the unchanged IMPROVE>=3 cohort. Secondary
HLA AP/AUROC, AP relative to prevalence, Precision@K, neoepitope if supported,
and unchanged full IMPROVE for unsupported-HLA negative transfer. No metric or
model score is calculated now. Sources were previously evaluated: exploratory,
not untouched confirmatory. Future paired resampling must retain global known
dependence components across both HLA contributions; a low component count or
sparse positives limits inference even if minimum gates pass.

Prospective decoys: only Task2.23 TRAIN-partition binary-negative canonical
nine-mers at either supported HLA, never EL validation/excluded rows. Preserve
original observation multiplicities, but select one identity per peptide-HLA,
with deterministic earliest prepared-row representative. Remove exact peptide
conflicts with any published measured-Tm ligand (all source lengths where equal)
or any authenticated EL-positive peptide across fitting AND validation,
regardless of HLA. Remove Hamming<=2 neighbors of all frozen external IM peptides.
Do not treat a decoy as a measured low-Tm or unstable pMHC observation.

Fixed proposed selection: per HLA choose16 unique eligible negative identities
per retained measured ligand, ordered by SHA256 of UTF-8
`Task2.35-decoy-v1|HLA|PEPTIDE`, then HLA/peptide as collision tie-breakers.
Require enough candidates; do not relax exclusions or silently change the ratio.
No full training batch materialization is needed now. D/P/T share precisely the
same negative identities and exposure order. Freeze label-independent selection
manifests and use no IM score, prevalence or outcome to select identities.

Future arms, conditional on all GO gates and separate training authorization:
A is unchanged Task2.23 EL10; D adapts measured ligands1/decoys0; P adapts within-HLA
permuted continuous-Tm targets/decoys0; T adapts genuine targets/decoys0. Targets
are permuted once with a dedicated Random(235002), sorted HLA and source identity,
preserving complete HLA target multisets including flagged records. Main contrast
T-P, practical T-A, descriptive T-D. All D/P/T start from the identical A checkpoint.
Only existing final output linear weight/bias may receive gradients; frozen
backbone and stochastic modules stay in eval mode. AdamW lr0.001, native defaults,
ordinary batch-mean BCE denominator, batch64,20 complete passes, no early stopping
or epoch/parameter search. Data order: sorted fixed source identities, local
Random(235001), shuffle one index array each pass, same sequence in all arms,
keep partial final batch. This proposed adaptation batching is distinct from the
historical EL positive-anchor sampler; no purported historical schedule match.
No setting is changed using prior IM performance. Structural feasibility is
checked by source text/AST only, without model loading or feature computation.
No transfer/training is authorized by this document.
