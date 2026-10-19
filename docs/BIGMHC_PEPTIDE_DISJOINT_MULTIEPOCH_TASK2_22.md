# Task 2.22 — Completed peptide-disjoint multi-epoch baseline

Status: completed on Z790 WSL2 / RTX 4090. Internal IM training ran once for 60 epochs; the final fit restarted once from original A EL and completed the selected 20 epochs on all 3,428 rows. No historical 383-row development outcomes or sealed independent benchmark files were accessed.

Branch: `task/2.22-peptide-disjoint-multiepoch-baseline`. Scientific execution commit: `b912f8c1246d8c9f5825969c0c1b30b291f0b5a4`. Task 2.21 commit `4340f785bbf49a9fa31969ea0fb282617e210ed7` was present in fetched origin/main; local main matched origin/main and the fast-forward was a no-op. No merge or push followed.

The [frozen protocol](BIGMHC_PEPTIDE_DISJOINT_MULTIEPOCH_PROTOCOL.md) and [configuration](../configs/bigmhc_multiepoch_task2_22.json) define grouping, native optimizer/sampling, candidate epochs and independent benchmark rules. The later documentation clarification of future PPVn uses the publication's n=1..P convention; it changes no Task 2.22 training or selection setting.

## Validation and split evidence

The four focused unittest modules passed **55 tests**, with zero failures and zero skips, using the existing Python 3.13.5 environment on WSL2. They cover the new split, fixed candidate selection, persistent AdamW agreement with the native loop, all-negative batch skip, RNG isolation, existing runner contracts and historical compatibility gates. Actual CUDA preflight strictly reloaded all 36 original EL tensors, checked FP32 and finite 16-row inference, with deterministic algorithms enabled and both TF32 switches disabled. GPU training and checkpoint inference then completed.

| Partition | Observations | Positive | Negative | Positive prevalence | Unique peptides | HLAs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| train | 2,742 | 764 | 1,978 | 27.862873815% | 2,650 | 35 |
| validation | 686 | 191 | 495 | 27.842565598% | 665 | 33 |

Exact peptide overlap = **0**; exact peptide–HLA overlap = **0**. Both classes occur in both sets. All 3,428 original observations occur exactly once with original labels and source locators preserved. All 33 validation HLAs are represented in IM training. The manifest retains original prepared-row indices, source file/row/line/ID/SHA256, original peptide/HLA/label and resolved HLA. Native subset coordinates are separately contiguous, without replacing original coordinates.

Validation contains **10 EL-exposed IM-novel peptides / 10 observations**, and **655 fully training-unseen peptides / 676 observations**. Exposure is defined against the authenticated original EL population, across all HLA and labels; this conservatively includes population rows that native EL sampling might not have consumed. The exact overlap report records every matching EL prepared index, HLA and original label. No EL population was redesigned.

Same-length one-AA neighbors occur for **21 / 665** validation sequences. Minimum train-sequence Hamming-distance counts are: distance 1: 21, distance 2: 8, distance 3: 35, distance 4: 272, distance 5: 309, distance 6: 20. These are descriptive results and did not change the split.

## Candidate comparison and selection

Select highest non-interpolated AP among the fixed seven candidates; exact ties choose earlier. **Epoch 20 was selected.** Validation BCE and noncandidate epochs did not select the model.

| Candidate epoch | Validation AP | Validation AUROC | Train eval BCE | Validation BCE |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 0.4098563757299015 | 0.6763340208366386 | 0.592493871 | 0.628811808 |
| 2 | 0.42933062076812506 | 0.6905812047173304 | 0.545489170 | 0.584322404 |
| 5 | 0.44921705451874366 | 0.7056110846686763 | 0.500156152 | 0.545763242 |
| 10 | 0.44988699206743404 | 0.7135543920884235 | 0.471029269 | 0.533107597 |
| 20 | 0.45635376958215745 | 0.7182822994341319 | 0.432577426 | 0.533600488 |
| 40 | 0.4410190900126003 | 0.7081812893331217 | 0.357435080 | 0.563423700 |
| 60 | 0.44443257655938356 | 0.7086466761859432 | 0.290481137 | 0.593067306 |

On the **same new validation split**, epoch 1 to epoch 20 changes AP by **+0.046497393852** and AUROC by **+0.041948278597**. This is evidence for useful additional IM training under this protocol. It is not a comparison with the historical 383-row population and does not isolate an accuracy effect of changing the split.

Early epochs improve substantially, followed by a noisy plateau around epochs 8–32. By epoch 60, AP/AUROC have declined relative to epoch 20 while training BCE continues down. Validation BCE reaches its minimum at epoch 15 (0.530255104) and rises to 0.593067306 at epoch 60; training eval BCE falls from 0.592493871 to 0.290481137. This is consistent with late overfitting, not continuing generalization improvement at the 60-epoch boundary. There was no budget extension.

At the selected internal checkpoint, the fully training-unseen stratum has 676 observations (184 positive), 655 unique peptides, AP **0.4471454880709223** and AUROC **0.7128402262283492**. The 10 EL-exposed observations contain seven positives; separate performance is not reported because that stratum is too small. These are descriptive strata from the already selected internal validation predictions, not independent tests or further selection criteria.

## Full 60-epoch validation learning curve

All 60 source-row-traceable prediction files and full-precision JSON/CSV values are saved. BCE below is eval-mode observation-mean BCE computed from logits, including every row. Separate update-mean/row-weighted BCE, native source-style loss and skip logs are retained per epoch.

| Epoch | AP | AUROC | Train eval BCE | Validation BCE | Optimizer updates |
| ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 0.409856376 | 0.676334021 | 0.592493871 | 0.628811808 | 171 |
| 2 | 0.429330621 | 0.690581205 | 0.545489170 | 0.584322404 | 171 |
| 3 | 0.435566978 | 0.696504310 | 0.523229963 | 0.564679605 | 171 |
| 4 | 0.440616641 | 0.700354329 | 0.509886452 | 0.554258802 | 171 |
| 5 | 0.449217055 | 0.705611085 | 0.500156152 | 0.545763242 | 170 |
| 6 | 0.442470022 | 0.704722619 | 0.492842591 | 0.544504894 | 170 |
| 7 | 0.443882295 | 0.706890899 | 0.486632197 | 0.542093577 | 172 |
| 8 | 0.451916574 | 0.711618806 | 0.481287645 | 0.535302534 | 170 |
| 9 | 0.448808503 | 0.713078428 | 0.475807010 | 0.533584344 | 171 |
| 10 | 0.449886992 | 0.713554392 | 0.471029269 | 0.533107597 | 169 |
| 11 | 0.442450884 | 0.711978423 | 0.466572086 | 0.534647692 | 172 |
| 12 | 0.442053619 | 0.713046697 | 0.461939459 | 0.532715220 | 172 |
| 13 | 0.445096148 | 0.714189011 | 0.457803036 | 0.531487191 | 170 |
| 14 | 0.443194382 | 0.713998625 | 0.454309230 | 0.533400624 | 172 |
| 15 | 0.446063959 | 0.717340949 | 0.450167401 | 0.530255104 | 171 |
| 16 | 0.446336570 | 0.716949601 | 0.446708554 | 0.531892015 | 170 |
| 17 | 0.443411910 | 0.715616902 | 0.442482609 | 0.532920201 | 168 |
| 18 | 0.447211676 | 0.717203448 | 0.439046892 | 0.532422944 | 171 |
| 19 | 0.447160369 | 0.715595748 | 0.435153809 | 0.533841649 | 171 |
| 20 | 0.456353770 | 0.718282299 | 0.432577426 | 0.533600488 | 170 |
| 21 | 0.446892574 | 0.715828441 | 0.427588980 | 0.533860497 | 170 |
| 22 | 0.454392167 | 0.719562113 | 0.425713174 | 0.533446566 | 172 |
| 23 | 0.450981608 | 0.717626527 | 0.420485997 | 0.534269755 | 172 |
| 24 | 0.440550365 | 0.716061135 | 0.416445342 | 0.536104620 | 171 |
| 25 | 0.445478388 | 0.717584219 | 0.412742728 | 0.537731264 | 170 |
| 26 | 0.448286479 | 0.717679412 | 0.408865142 | 0.538050394 | 172 |
| 27 | 0.443188724 | 0.715352478 | 0.405247462 | 0.540345081 | 171 |
| 28 | 0.448901044 | 0.717023640 | 0.402443362 | 0.539470976 | 168 |
| 29 | 0.448705600 | 0.715352478 | 0.398152507 | 0.541712079 | 172 |
| 30 | 0.450480027 | 0.714707282 | 0.394562821 | 0.542941245 | 171 |
| 31 | 0.450201292 | 0.715585171 | 0.390498459 | 0.543930878 | 171 |
| 32 | 0.454209351 | 0.716854408 | 0.388571172 | 0.543447942 | 171 |
| 33 | 0.445805257 | 0.713046697 | 0.383053915 | 0.549333972 | 171 |
| 34 | 0.438929050 | 0.712983235 | 0.379386777 | 0.548465350 | 172 |
| 35 | 0.436521821 | 0.711174573 | 0.375795631 | 0.551425303 | 172 |
| 36 | 0.444961123 | 0.712295732 | 0.371808613 | 0.551421933 | 171 |
| 37 | 0.441245687 | 0.713036120 | 0.369717516 | 0.556196303 | 171 |
| 38 | 0.438040812 | 0.709884182 | 0.364164404 | 0.553700598 | 172 |
| 39 | 0.438201915 | 0.708022635 | 0.360445864 | 0.558352903 | 172 |
| 40 | 0.441019090 | 0.708181289 | 0.357435080 | 0.563423700 | 171 |
| 41 | 0.440947464 | 0.708868793 | 0.353008057 | 0.561367669 | 171 |
| 42 | 0.442736101 | 0.711132265 | 0.349399370 | 0.561780423 | 171 |
| 43 | 0.439948552 | 0.708519752 | 0.345811837 | 0.564651777 | 172 |
| 44 | 0.444042272 | 0.709323603 | 0.342363447 | 0.566935490 | 171 |
| 45 | 0.443642409 | 0.709154371 | 0.338268483 | 0.566775521 | 172 |
| 46 | 0.439719844 | 0.707768787 | 0.334562735 | 0.569115930 | 172 |
| 47 | 0.443781956 | 0.709461103 | 0.331197210 | 0.570288555 | 171 |
| 48 | 0.445075735 | 0.710434185 | 0.328674873 | 0.571628617 | 171 |
| 49 | 0.434285656 | 0.705209160 | 0.324705229 | 0.578207006 | 170 |
| 50 | 0.429478912 | 0.704585118 | 0.322420376 | 0.581194392 | 169 |
| 51 | 0.439277839 | 0.708128404 | 0.317626426 | 0.578397912 | 170 |
| 52 | 0.441005885 | 0.707440901 | 0.314908177 | 0.579495348 | 172 |
| 53 | 0.432972032 | 0.703294727 | 0.311272242 | 0.584173654 | 171 |
| 54 | 0.438535445 | 0.705505315 | 0.311527605 | 0.592231302 | 172 |
| 55 | 0.441154050 | 0.705991856 | 0.305480299 | 0.589186485 | 171 |
| 56 | 0.439294734 | 0.706182241 | 0.302048953 | 0.591398795 | 171 |
| 57 | 0.431750462 | 0.702723571 | 0.298729801 | 0.592597050 | 172 |
| 58 | 0.439473673 | 0.705399545 | 0.295873569 | 0.596280272 | 172 |
| 59 | 0.438297936 | 0.705113967 | 0.292456615 | 0.594714542 | 172 |
| 60 | 0.444432577 | 0.708646676 | 0.290481137 | 0.593067306 | 169 |

## Final fit and checkpoint lineage

Original-label A EL parent: resolved project runs / `task-2_17-abp-comparison/A/checkpoints/el`, from Task 2.17 commit `02313b20da218dbcacdbb2cbee5f5d435b258a18`. EL-stage receipt SHA256: `6e7250c22c728fb149c4f55522aec1ff85d2dbc5bdff5296a143cafdb61c05cc`. All 36 EL file identities match; no historical IM checkpoint was loaded.

The internal fit starts from this EL parent and retains seven native four-tensor IM overlays. Selected overlay: `checkpoints/internal_epoch_20`. Its explicit external EL parent, all file identities and complete reconstructed tensor identities are in `reports/checkpoint_lineage.json`. The final model independently restarts from the same original EL state with fresh seed42 and fresh AdamW, then trains **20 epochs on all 3,428 original rows**. Selection and settings were frozen in `reports/final_frozen_configuration.json` before that restart.

Final complete baseline: `checkpoints/final_all_IM`, 36 native tensor files, **349,848,462 bytes**. It is self-contained and requires no external parent to reload. Only the four native transfer parameters changed in each fit; all other tensor identities equal original EL. Both selected-overlay and final-complete strict tensor reloads passed; same-device probabilities were **bitwise identical, maximum absolute difference 0**. The final inference probe used fixed first16 training rows only and had no selection role. The final full-data model was not scored on the internal subset as a held-out test or on historical/independent outcomes.

Final epoch training update BCE = 0.44608367942668525; all-training-row eval BCE = 0.43409329503253014. These are training diagnostics, not generalization metrics.

## Runtime, optimizer and resource evidence

Platform: `Linux-6.18.33.2-microsoft-standard-WSL2-x86_64-with-glibc2.43`; RTX 4090, Python 3.13.5, Torch 2.13.0+cu130 / CUDA 13.0, cuDNN 92000, NumPy 2.5.4, pandas 3.0.6, psutil 7.2.2. The four library versions exactly match historical A. AdamW lr 5e-5, betas (0.9,0.999), eps 1e-8, weight decay 0.01 and native runtime defaults persisted unchanged within each fit. Every optimized parameter's AdamW step counter equals the cumulative epoch update count; it was never reset between epochs.

| Fit | Epochs | Updates | Skipped negative-only batches | Synchronized training seconds | Stage wall seconds | Peak allocated GPU bytes | Peak reserved GPU bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| final | 20 | 4,273 | 27 | 42.218911 | 60.956749 | 1,059,148,800 | 1,790,967,808 |
| internal | 60 | 10,258 | 62 | 99.181349 | 157.606814 | 1,059,666,944 | 1,390,411,776 |

Scientific workflow wall time: **224.489165 s** after input/runtime setup. Peak process host RSS: **2,341,761,024 bytes**. Stage wall times include validation/training diagnostics and artifact work; synchronized training times measure optimizer-loop wall time rather than CUDA kernel profiling. GPU numbers are Torch allocator peaks, not total system VRAM or power consumption. No EL compute was repeated.

All native sampled row/label sequences, batch hashes, negative-only skip masks, optimizer defaults, and epoch counters were checked from saved evidence. All 60 validation AP/AUROC pairs were recomputed from the saved probabilities. The RNG boundary after each epoch exactly matches the boundary before the next, verifying that evaluation/checkpoint work did not perturb scientific RNG. The completion verifier authenticated **306 scientific outputs** and all seven candidate overlays, the final checkpoint and the unchanged original EL parent, without additional training or inference.

## HLA distribution

| HLA | Train observations | Train positive | Validation observations | Validation positive |
| --- | ---: | ---: | ---: | ---: |
| HLA-A*01:01 | 126 | 13 | 25 | 5 |
| HLA-A*02:01 | 1039 | 439 | 259 | 108 |
| HLA-A*02:03 | 35 | 7 | 3 | 0 |
| HLA-A*02:10 | 5 | 1 | 1 | 0 |
| HLA-A*02:11 | 20 | 5 | 4 | 1 |
| HLA-A*03:01 | 105 | 41 | 28 | 7 |
| HLA-A*11:01 | 237 | 36 | 57 | 7 |
| HLA-A*23:01 | 58 | 5 | 6 | 0 |
| HLA-A*24:02 | 162 | 35 | 39 | 11 |
| HLA-A*25:01 | 6 | 1 | 2 | 0 |
| HLA-A*26:01 | 60 | 6 | 15 | 1 |
| HLA-A*29:02 | 7 | 6 | 2 | 2 |
| HLA-A*30:01 | 27 | 4 | 9 | 0 |
| HLA-A*30:02 | 5 | 5 | 3 | 3 |
| HLA-A*31:01 | 59 | 2 | 11 | 0 |
| HLA-A*32:01 | 35 | 0 | 17 | 0 |
| HLA-A*66:01 | 5 | 0 | 1 | 0 |
| HLA-A*68:01 | 38 | 4 | 16 | 6 |
| HLA-B*07:02 | 238 | 45 | 48 | 9 |
| HLA-B*08:01 | 87 | 17 | 27 | 5 |
| HLA-B*15:01 | 119 | 9 | 31 | 2 |
| HLA-B*15:02 | 1 | 1 | 0 | 0 |
| HLA-B*15:17 | 3 | 0 | 2 | 0 |
| HLA-B*18:01 | 12 | 3 | 6 | 2 |
| HLA-B*27:02 | 3 | 1 | 0 | 0 |
| HLA-B*27:05 | 37 | 21 | 7 | 3 |
| HLA-B*35:01 | 115 | 24 | 30 | 12 |
| HLA-B*35:03 | 1 | 1 | 1 | 0 |
| HLA-B*39:01 | 2 | 1 | 1 | 0 |
| HLA-B*40:01 | 29 | 9 | 15 | 3 |
| HLA-B*45:01 | 9 | 1 | 3 | 0 |
| HLA-B*51:01 | 8 | 2 | 3 | 1 |
| HLA-B*56:01 | 4 | 1 | 2 | 0 |
| HLA-B*57:01 | 22 | 9 | 9 | 2 |
| HLA-B*58:01 | 23 | 9 | 3 | 1 |

## Artifacts and stopping point

All derived artifacts are in resolved project runs / `task-2_22-peptide-disjoint-multiepoch-baseline/`:

- `processed/split_manifest.csv`, `processed/peptide_groups.json` and native partition CSVs.
- `reports/split_verification.json`, `reports/peptide_EL_overlap.json`, `reports/sequence_proximity.json`.
- `reports/training_configuration.json`, `reports/preflight.json`, `reports/CUDA_preflight.json`, `reports/execution_started.json`.
- `reports/learning_curve.csv` / `.json`, per-epoch training/metric receipts and `predictions/validation_epoch_01.csv` through `_60.csv`.
- `reports/candidate_checkpoint_comparison.json`, `reports/final_frozen_configuration.json`, `reports/final_learning_curve.json`.
- `checkpoints/internal_epoch_{01,02,05,10,20,40,60}` and `checkpoints/final_all_IM`.
- `reports/checkpoint_lineage.json`, stage start/completion reports, `reports/completion.json`, `reports/output_manifest.json`.
- `reports/completion_verification.json`, `logs/` and supplemental manifest binding the later verification/log receipts.

Original scientific output-manifest SHA256: `b594fda094cd7a29695ee5c4037504d5d377659465892bd7c44f4283ff0e4929`. The post-run [verification script](../scripts/verify_bigmhc_multiepoch.py) is repository managed; its executed SHA256 is bound in the verification receipt. Original scientific outputs were not overwritten.

No scientific protocol deviations, training retries, blockers, new dependencies, dataset downloads, large data copies, Dropbox backup, stability variants, EL retraining, or additional model fits occurred. The better split tests IM sequence novelty; it does not by itself prove an accuracy gain or eliminate sequence-neighbor/source correlations. This is one seed and one selection cohort, so selection AP is optimistic as a future performance estimate. The all-data final fit subsequently consumes those validation labels. Stability-specific predictive benefit cannot be inferred from this baseline.

Longer EL pretraining merits a separately authorized, preregistered development study, but these IM curves do **not** establish that EL is undertrained. The current evidence supports stopping IM at the selected candidate rather than extending its budget. Before a longer-EL study, define independent EL validation, fixed candidate budgets and a development selection rule while keeping the neoepitope benchmark sealed. The protocol already fixes future benchmark overlap/provenance checks, AP as primary, AUROC and K=10/20/50 precision as secondary, PPVn and exposure stratification. No such future experiment or independent benchmark evaluation was run here.
