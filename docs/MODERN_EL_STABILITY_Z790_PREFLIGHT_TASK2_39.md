# Modern EL/stability local preflight — Task 2.39

**Technical GO for a separately authorized, explicitly exploratory Task 2.40 comparison. No benchmark inference is authorized by this preflight.** Both pinned models execute locally, all 7,788 frozen IMPROVE observations have authenticated common input coverage, and exact designated-HLA score extraction passes. Complete ancestral training independence and upstream IM-blind model development remain unverified; GO does not mean a leakage-free or untouched confirmatory benchmark.

Completed 2026-10-26 on Z790/WSL2. Branch: `task/2.39-modern-el-stability-z790-preflight`; exact base: `81c756e4039821f4f324d32951b5d99d71f2f113`. The requested separate worktree is `~/codex/repos/stability-label-curation-task239`. The historical worktree was clean before isolation and remains unchanged. No merge, push, remote configuration, BigMHC checkpoint modification or historical-result change occurred.

## Scope and cross-machine provenance

No IMPROVE/Neoepitope model predictions, IM outcomes, previous prediction values, AP/AUROC values, training or tuning were accessed or computed. The only scored peptides were the fixed public `GILGFVFTL` and `NLVPMVATV`, against A*02:01 and B*07:02. No private cohort sequences were sent to any remote service.

The Task 2.38 Mac commit `c1149bfe3f79bf7729871587347297a808361ea4` and compact handoff manifests were not locally available. No unrelated Git histories were fetched/merged. Registries and six outcome-free stability identity indexes were independently reconstructed from the required pinned public sources. The supplied prefix pins, inventory counts and A/B full-length reference lengths reproduce, but **Mac file/hash equivalence was not checked**. No independently generated hash is presented as a recovered Mac hash.

The source repositories provide the following public artifact roots:

- [MixMHCpred official v3.0 release](https://github.com/GfellerLab/MixMHCpred/releases/tag/v3.0), commit `0a7f9b9e20d1cf02236f4a0a90d16735be879b38`.
- [SPEARMINT Stage 3 pinned snapshot](https://huggingface.co/dkarthikeyan1/spearmint/tree/93e8e3e640e49e5a373f0dc432b122df19e4b969).
- [SPEARMINT data/code source](https://github.com/dhuvik/spearmint/tree/d548dee9b04dd0e3a9d7a50a593d2c030e31d2a5).
- [IPD-IMGT/HLA protein reference](https://github.com/ANHIG/IMGTHLA/blob/bdc6233a79b1d0323140c25ef6e2e6d4e7187c26/fasta/hla_prot.fasta), release 3.64.0, upstream tag `v3.64.0-alpha`, dated 2026-04-16. The suffix is the official repository's tag spelling.

## Authenticated artifacts and security

| Artifact | SHA256 |
|---|---|
| Exact MixMHCpred source/release archive | `ebd8f2b6e582909d4dc8cb2ab7da19f867b5cd3b3cf7502917ca12fecc4bc1b9` |
| SPEARMINT Stage 3 `model.safetensors` (3,259,432,552 bytes) | `5b842af0c8b41fdf7a0ab329fe2bc76b92de0bf559dcede1501493fdf68cff8f` |
| SPEARMINT `modeling_spearmint.py`, including tokenizer | `82a1175dd79706988ea9ef7fa59619883c058d984890e99f9216845fedf82413` |
| SPEARMINT `configuration_spearmint.py` | `55c8ead8061e3852d2f1433c0267b165a2afe65a725a94a308d1a1b62c4e5bb4` |
| IPD protein FASTA | `95b0e8752fb8e7411e8db40c87cd2cc369c2aa9ccf054c6e5c52c5eeef311b1e` |

Both Git tree objects were reconstructed from their entry bytes and matched to the tree hashes in the pinned commits (rather than assuming an API root `sha` is a tree hash). Every Mix release file was checked against its pinned Git tree blob and recorded with SHA256, including individual PWM, neural weight, rank-reference and source files. HF custom code/config were checked against pinned Git blobs; the entire safetensors SHA256 and byte count match the HF LFS metadata. Source CSVs and HLA consensus references were checked against their pinned Git blobs and SHA256. Registry/receipts retain original acquisition URLs. API metadata snapshots are acquisition evidence; changing server-side counters/serialization are not model version changes, and a reacquired metadata hash mismatch must not be concealed.

Mix's launcher, Python scoring code and installer were inspected. `install_packages` would invoke system package managers, so it was **not executed**. `setup_path`, sequence-alignment shell evaluation, MAFFT, motif plotting/deletion and PRIME were not invoked. Only `-a` and `-m 0` paths with new output files were used. Its nine distributed object-NPY files were inspected without unpickling; their globals are limited to NumPy ndarray/dtype/reconstruction/scalar helpers, with no dynamic-global or extension opcodes. These fixed official files are distinct from admitting arbitrary pickle checkpoints. The academic non-commercial license permits intended research execution; commercial use needs a separate license and redistribution is prohibited. External artifacts were not committed.

SPEARMINT's custom code is self-contained tensor/model/tokenizer code. Its upstream loader contains remote snapshot and pickle fallback branches. The smoke wrapper requires the verified existing local directory and safetensors, blocks both fallback functions, sets offline flags before load, and uses the original class/tokenizer without source modification. No pickle weights were loaded. Optional Apex is not installed; the upstream normal PyTorch layer-normalization path is used. HF/source licensing is MIT, with inlined MINT/ESM attribution retained. Static inspection and pinned files are an execution safeguard, not a formal security proof.

## Runtime and public-only smoke evidence

- Ubuntu **26.04.1 LTS**, WSL2 kernel **6.18.33.2-microsoft-standard-WSL2**, machine Z790; Python **3.13.5**.
- RTX **4090**, driver **610.88**; **24,564 MiB** total and **23,542 MiB** free at readiness capture.
- PyTorch **2.13.0+cu130**, CUDA **13.0**, cuDNN **92000**; CUDA available and actual inference passed.
- Separate external `env_mixmhcpred` and `env_spearmint` runtimes. Mix uses NumPy **2.2.6**, pandas **2.2.3**, SciPy **1.15.3**; SPEARMINT uses Transformers **4.57.1**, safetensors **0.6.2**, NumPy **2.5.4** and the existing read-only shared GPU Torch installation via `.pth`.
- No shared environment, GPU driver or system CUDA library was modified. Complete resolved dependency versions are committed as two lock files; runtime lock checks reject drift. The original config serializes Transformers 4.30.2; compatible 4.57.1 was fixed locally before smoke inference. The pinned upstream explicit loader supports cross-version state-dict loading; architecture, tokenizer and weight bytes were unchanged.

| Public peptide | HLA | Mix native designated-HLA score | Mix published percentile rank | SPEARMINT Stage 3 log1p(hours) |
|---|---|---:|---:|---:|
| GILGFVFTL | A*02:01 | 0.260247 | 0.034531 | 2.247546434402466 |
| NLVPMVATV | A*02:01 | 0.171245 | 0.049002 | 2.130753993988037 |
| GILGFVFTL | B*07:02 | -2.075408 | 6.307124 | 0.06617001444101334 |
| NLVPMVATV | B*07:02 | -2.481245 | 11.708995 | 0.6516284942626953 |

Mix's executable identifies itself as **MixMHCpred3.0**, with actual columns `Peptide`, best-allele convenience fields, `Score_A0201`, `%Rank_A0201`, `Score_B0702`, `%Rank_B0702`. Designated columns were selected explicitly, including multi-allele output where best allele differs. Repeated runs, per-allele versus multi-allele results, and single versus batched peptide inputs were identical. Higher native scores and lower published ranks have the documented presentation orientation. Public smoke elapsed time: **4.5962684149853885 s**.

SPEARMINT accepted the full 365/362-residue chains and original chain IDs. SPA index **0** and raw temperature **37.0** were asserted. FP32 eval-mode outputs were finite; repeated batches were exactly equal. Maximum single-versus-batch difference was **4.76837158203125e-7**, below the prospectively fixed `atol=1e-4, rtol=1e-5`. Elapsed time including load: **10.359059848007746 s**; peak allocated GPU memory **3,823,875,584 bytes**, reserved **3,969,908,736 bytes**. These are four-public-input resource observations, not a measured benchmark throughput claim. No study predictions or fusion were generated.

## Frozen identity population and coverage

The sole historical scientific input read was the already outcome-free Task 2.32 `cohorts/IMPROVE_identities.jsonl`. A strict schema allowlist projects identifiers, peptide, HLA, original row mapping, study/patient and non-outcome dependence groups. Unexpected columns cause rejection before value lookup. A runtime file-access guard denies every other historical run artifact. `scientific_file_access.json` records only that identity file; no original mixed outcome CSV, outcome sidecar or historical score file was read.

Original identity SHA256: `33fbad5f142a93d0803b39800fa3dcb71437320c4134e92594080830b6f26986`.

Ordered row keys and common-coverage ordered row keys both hash to `8118663ebf5c23de8f36a7a7c15aa0247a0609e04ade927657528d2986f6fee9` using compact UTF-8 JSON-array serialization.

| Quantity | Count |
|---|---:|
| Original and retained observations | 7,788 |
| Distinct canonical 9-mer peptides | 6,576 |
| Distinct peptide–HLA identities | 7,750 |
| Distinct HLA alleles | 36 |
| Patients / studies | 70 / 3 |
| Original patient/peptide dependence components | 38 |
| A*02:01 observations / original components | 616 / 16 |
| Mix input coverage | 7,788 / 7,788 |
| SPEARMINT full-length input coverage | 7,788 / 7,788 |
| Paired common coverage | 7,788 / 7,788 |
| Excluded / unresolved HLA / noncanonical / length-incompatible rows | 0 / 0 / 0 / 0 |
| Unknown ancestral-history flags | 7,788 / 7,788 |

All original observation multiplicities, patient associations and order are retained. Coverage by peptide length is 7,788 nine-mers. No IM class counts were generated, including by HLA. The 267-row historical Neoepitope cohort remains deferred optional descriptive evidence and was not opened or scored.

Full-length model consensus sequences match exact proteins/accessions in the fixed IPD release. The reference contains 12 A proteins of 365 residues, 17 B proteins of 362 residues and 7 C proteins of 366 residues. Signal/TM/tail residues are retained. A*02:01 sequence SHA256 is `a77c8fd26c1e0b5d0034384309cd3600fb1e3f8775e1979363d5db3a185be675`; B*07:02 is `5de81f208e7148a6c5163dc26042423d3e3fdd21b2eb3c95625b3a80f58583fb`. All 36 accessions/designations/checksums are frozen in the compact public reference registry. Model consensus plus exact IPD protein agreement, not length alone, authenticates these selected full references. Synonymous three/four-field matches are recorded; this supplies a canonical two-field model input, not unobserved donor suballele genotyping. Fragmentary references elsewhere in upstream data were not extended or substituted.

Every IMPROVE allele has direct learned-reference support in Mix v3.0's allele/PWM tables; **0 require pan-allele inference**. Original nearest-reference/distance metadata are preserved. C*03:04's upstream nearest reference is C0303 at distance 0 because of tied binding-site identity; the designated C0304 PWM/score is still used. Full-chain SPEARMINT accepts all 36 inputs, but only 25/36 and 21/36 occur in the published S2/S3 fitting inventories, respectively. Input coverage does not imply allele-specific stability fitting support or validated accuracy.

## S2/S3 exposure audit

Six independently rebuilt unlabeled identity indexes preserve original source lines, alleles, full-MHC sequence hashes, split assignment and available PMID/IEDB reference identifiers. Inventory totals reproduce **27,031 S2 rows** and **10,141 S3 rows**. S2 consists entirely of nine-mers. S3 train/validation/test include 8,183/530/876 nine-mer rows, with 282/13/257 other-length rows retained in indexes but excluded from nine-mer distance comparisons. No artificial Hamming distance was assigned to incompatible lengths; all source peptides are canonical.

Every row has **zero exact peptide–HLA and zero allele-agnostic peptide matches** to each of the six published split indexes. This is a statement about these authenticated inventories, not all ancestral training. Below, `>=3` is an aggregate; per-row files preserve the exact minimum distance and a reference witness. Counts are observations, including repeated biological measurements.

| Published split | Source rows | Exact pair / peptide | Hamming 0 | Hamming 1 | Hamming 2 | Hamming >=3 |
|---|---:|---:|---:|---:|---:|---:|
| S2 fitting | 21,626 | 0 / 0 | 0 | 0 | 8 | 7,780 |
| S2 validation | 2,705 | 0 / 0 | 0 | 0 | 0 | 7,788 |
| S2 test | 2,700 | 0 / 0 | 0 | 0 | 2 | 7,786 |
| S3 fitting | 8,465 | 0 / 0 | 0 | 0 | 6 | 7,782 |
| S3 validation | 543 | 0 / 0 | 0 | 0 | 1 | 7,787 |
| S3 test | 1,133 | 0 / 0 | 0 | 0 | 3 | 7,785 |

The union of S2/S3 fitting-neighbor observations at distance <=2 is **8/7,788 (0.1027221366204417%)**; exact fitting exposure is **0%** against the published indexes. These flags did not change eligibility. Validation and test occurrences/neighbors are separately named and are not called model-fitting exposure.

Same-HLA distances are also saved. S2 fitting/validation/test have 4/0/0 distance-2 observations and 2,714/2,778/2,778 undefined same-HLA distances because no same-HLA reference exists. S3 fitting/validation/test have 3/1/1 distance-2 observations and 3,169/3,908/3,478 undefined same-HLA distances. Undefined is not classified as >=3. Allele-agnostic distances are defined for every candidate in every split. The indexed nine-mer search uses exact identity/Hamming distance and a distant-query scan fallback, without a full all-pairs matrix; synthetic cases were checked against brute force.

S3 source PMID annotations are present on only 659/8,465 fitting, 43/543 validation and 476/1,133 test rows. A focused bibliographic-only DOI lookup maps the frozen bladder and melanoma studies to PMIDs 35410325 and 34813506; neither occurs among available S3 annotations. The Basket preprint has no resolved PMID in that lookup. This is **not** complete study-independence evidence: most S3 annotations and S2 publication/donor links are unavailable, and patient ancestry cannot be linked. Source reference IRIs and lookup receipts are preserved without fetching assay outcomes.

MINT Stage 1 BA, MINT PPI and complete MixMHCpred EL training identities are **unverified**, not assumed absent. The source release's stability-only S2/S3 fitting objective is distinct from IM-supervised fitting, exact sequence exposure, near-neighbor exposure and upstream architecture/model-selection exposure. Upstream downstream-IM files were not opened; the complete authors' IM-blind development history cannot be established from these indexes. A cryptographic checkpoint-to-full-training-run manifest was not recovered. These limits apply to all 7,788 observations and prevent any fully leakage-free ancestry claim. SPEARMINT is not promoted to an audited primary source for fitting new project models by this task.

## Frozen contracts and decision

The separately committed protocol specifies exact native scores, SPA/37°C, designated-HLA mapping, unchanged common coverage, patient/peptide paired uncertainty, and deterministic observation-weighted within-HLA percentile midranks. The fixed fusion is **50% EL rank + 50% stability rank**, compared with EL alone on the same rank scale. Native pooled, within-HLA rank and fused scores remain distinct. Fusion was tested only on synthetic records. No IM labels determine coefficients, subsets, assay, normalization or thresholds.

Technical GO rests on authenticated local artifacts/dependencies, successful public smoke tests, exact row/HLA alignment, finite deterministic output, complete shared input coverage and a frozen outcome-blind protocol. It permits only a **separately requested** Task 2.40 exploratory comparison. Unknown ancestry and upstream development choices are scientific interpretation limits, not evidence that the cohort is leakage-free. A fully independent confirmatory claim is **NO-GO** on current provenance. No required execution/sequence/score-mapping blocker remains. Do not launch inference automatically.

## Per-HLA coverage (no IM outcomes)

| HLA | Observations | Full-chain residues | Mix support | S2 / S3 fitting-source rows | Nearest reference (distance) |
|---|---:|---:|---|---:|---|
| HLA-A*01:01 | 251 | 365 | direct | 175 / 248 | A0101 (0.0) |
| HLA-A*02:01 | 616 | 365 | direct | 808 / 1758 | A0201 (0.0) |
| HLA-A*02:05 | 41 | 365 | direct | 15 / 3 | A0205 (0.0) |
| HLA-A*03:01 | 474 | 365 | direct | 686 / 1033 | A0301 (0.0) |
| HLA-A*11:01 | 153 | 365 | direct | 458 / 846 | A1101 (0.0) |
| HLA-A*24:02 | 379 | 365 | direct | 457 / 1070 | A2402 (0.0) |
| HLA-A*26:01 | 243 | 365 | direct | 215 / 256 | A2601 (0.0) |
| HLA-A*30:01 | 163 | 365 | direct | 302 / 8 | A3001 (0.0) |
| HLA-A*30:02 | 27 | 365 | direct | 302 / 57 | A3002 (0.0) |
| HLA-A*31:01 | 235 | 365 | direct | 295 / 0 | A3101 (0.0) |
| HLA-A*32:01 | 239 | 365 | direct | 26 / 4 | A3201 (0.0) |
| HLA-A*68:01 | 88 | 365 | direct | 302 / 33 | A6801 (0.0) |
| HLA-B*07:02 | 555 | 362 | direct | 524 / 770 | B0702 (0.0) |
| HLA-B*08:01 | 402 | 362 | direct | 369 / 126 | B0801 (0.0) |
| HLA-B*13:02 | 64 | 362 | direct | 7 / 1 | B1302 (0.0) |
| HLA-B*15:01 | 111 | 362 | direct | 860 / 1251 | B1501 (0.0) |
| HLA-B*18:01 | 116 | 362 | direct | 294 / 0 | B1801 (0.0) |
| HLA-B*27:05 | 119 | 362 | direct | 290 / 12 | B2705 (0.0) |
| HLA-B*35:01 | 225 | 362 | direct | 527 / 655 | B3501 (0.0) |
| HLA-B*35:03 | 91 | 362 | direct | 302 / 3 | B3503 (0.0) |
| HLA-B*37:01 | 12 | 362 | direct | 0 / 0 | B3701 (0.0) |
| HLA-B*38:01 | 390 | 362 | direct | 0 / 0 | B3801 (0.0) |
| HLA-B*40:01 | 276 | 362 | direct | 244 / 262 | B4001 (0.0) |
| HLA-B*40:02 | 80 | 362 | direct | 16 / 3 | B4002 (0.0) |
| HLA-B*44:02 | 174 | 362 | direct | 0 / 0 | B4402 (0.0) |
| HLA-B*44:03 | 85 | 362 | direct | 0 / 0 | B4403 (0.0) |
| HLA-B*44:05 | 17 | 362 | direct | 283 / 0 | B4405 (0.0) |
| HLA-B*51:01 | 87 | 362 | direct | 283 / 0 | B5101 (0.0) |
| HLA-B*57:01 | 22 | 362 | direct | 280 / 8 | B5701 (0.0) |
| HLA-C*02:02 | 310 | 366 | direct | 0 / 0 | C0202 (0.0) |
| HLA-C*03:04 | 288 | 366 | direct | 0 / 0 | C0303 (0.0) |
| HLA-C*04:01 | 389 | 366 | direct | 0 / 0 | C0401 (0.0) |
| HLA-C*05:01 | 10 | 366 | direct | 0 / 0 | C0501 (0.0) |
| HLA-C*06:02 | 225 | 366 | direct | 0 / 0 | C0602 (0.0) |
| HLA-C*07:01 | 556 | 366 | direct | 0 / 0 | C0701 (0.0) |
| HLA-C*07:02 | 275 | 366 | direct | 0 / 0 | C0702 (0.0) |

## Reproduction and focused validation

External storage roots are `data/stability-label-curation/modern_models_task2_39/` and `runs/stability-label-curation/task-2_39-modern-el-stability-z790-preflight/` beneath the configured Codex root. Downloads, full references, private row keys, indexes, exposure witnesses, smoke outputs and receipts stay outside Git. No backup archive was made.

The reproducible entry points, all with `PYTHONPATH=src`, are:

1. `scripts/task239_fetch.py --include-weights`: fixed public acquisition/checksums; no installers or IM data.
2. Create isolated runtimes from the two dependency locks; preserve the existing GPU environment. See the environment receipt and read-only Torch `.pth` arrangement.
3. `scripts/task239_preflight.py`: authenticate every source, project the frozen identity-only cohort, verify full references, build split indexes, exact distances, common coverage and file-access evidence.
4. `scripts/task239_security.py`: record inspected execution branches and verify pinned files/object-NPY restrictions.
5. `scripts/task239_mix_support.py` under the Mix environment: original nearest-reference metadata only, no peptide scoring.
6. `scripts/task239_public_smoke.py mix` / `spearmint` under their respective environments: fixed public pairs only; refuses existing smoke-result output. Do not rerun merely to reproduce results already preserved.
7. `scripts/task239_environment.py`: installed dependency/hardware receipt.

Fourteen new focused tests pass for conservative HLA normalization, checksum/reference authentication, designated-HLA extraction despite a different best allele, missing/reordered/duplicate rows, finite scores, fixed assay encoding, tied percentile ranks, deterministic fusion, identity-only schema enforcement, source-label omission, coverage, import-without-storage-writes, exact Git-tree reconstruction and brute-force Hamming agreement. All 57 focused tests pass. The existing 43 sequence-leakage tests also pass on synthetic/fixture inputs. No real IM outcome is needed by these tests.

A repeated data-only audit reproduces the identity/index/coverage hashes; the reproducibility receipt records the comparison. Runtime dependency checks and the 36-allele checksum registry are part of the executable gate. Public-only smoke results are retained, not regenerated as benchmark predictions. All task code/configuration/protocol/report files are locally committed; the final external receipt records the commit. No training, IM metrics, calibration, outcome-based eligibility, new model candidate or subsequent experiment occurred.
