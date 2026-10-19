# Task 2.23 — Multi-epoch EL pretraining

Frozen experiment: branch `task/2.23-el-multiepoch-baseline`, directly from Task 2.22 approved commit `565cf6bf40075406fe6443a16aab4aa9dc616f2a`. Status: completed on Z790 WSL2 / RTX 4090. All ten EL epochs, the matched fixed-duration IM comparison and final full-IM fit completed within the authorized budget.

The [configuration](../configs/bigmhc_el_multiepoch_task2_23.json) freezes one continuous ten-epoch original-label EL fit, six candidates (1, 2, 4, 6, 8, 10), two fresh matched 20-epoch IM development fits (one shared fit if epoch 1 wins), and one fresh 20-epoch fit on all 3,428 original IM observations. No stability weighting, auxiliary supervision, architecture/optimizer changes, downloads or independent-test access. All new artifacts resolve through `stability_label_curation.paths` to project runs / `task-2_23-el-multiepoch-baseline/`.

The original eligible EL population is 1,453,578 human HLA-I 9-mer rows, with 70,069 positives and 1,383,509 negatives. Exact normalized sequence exclusion applies to all 665 Task 2.22 IM-validation peptides, regardless of HLA, label or predictions. Remaining rows are grouped by normalized peptide across all HLAs. Reserve the lexically first peptide group and lexically first positive peptide group per HLA in training, where present. Shuffle sorted remaining groups once with `Random(42)`, then greedily add whole groups to validation only if they strictly improve squared relative errors to 10% of each original class. No swaps, alternate seeds, scores or split search. Source order, labels, prepared coordinates and source-row locators remain intact. A single compressed manifest covers train, validation and exclusions; original datasets are not copied. Report HLAs with no original positive anchors or without both validation classes.

Training starts once from pinned authentic `BigMHC()` defaults with seed 42, CUDA FP32, deterministic algorithms and TF32 disabled. Native EL `makebats(16, shuffle=True, negfrac=.99)` is positive anchored: its stochastically consumed row population differs from the complete eligible training partition. No rows are relabeled. Native mean BCE within each actual batch and source-style epoch denominator remain unchanged. AdamW lr 5e-5 and defaults persist across epochs. Training evidence includes batch source-coordinate hashes, exposures, losses, RNG boundaries and persistent optimizer step counts. EL validation uses all held-out rows in source order with no resampling; pooled tied-score non-interpolated AP is primary. AUROC, evaluable per-HLA AP, macro AP and all-row logit BCE are secondary. Evaluation and checkpoint reload constructors preserve scientific RNG. Full candidate checkpoints include strict tensor reload checks. Highest candidate AP selects, exact ties choose the earlier epoch; epoch 10 ends the budget unconditionally.

Downstream IM uses the exact saved Task 2.22 manifest: 2,742 training and 686 validation rows, with unchanged original labels. Each fit reloads its explicit new EL parent, resets all RNG streams to seed 42 and creates fresh native transfer AdamW, updating only the four native condenser parameters. All 20 ordered batch schedules, skip masks and RNG boundaries must agree between the two fits. Every IM epoch retains train update/evaluation BCE and validation BCE/AP/AUROC. IM scores cannot revise EL selection. Complete downstream checkpoints and final validation predictions are retained. No established top-ranking metric implementation exists in the reused runner; AP/AUROC/BCE are reported without adding a new metric convention.

Before IM evaluation, sequence and peptide–HLA overlap must be zero between the 686 validation observations and both new training populations; EL validation exclusion is also checked. The final model restarts from the EL-selected checkpoint and fits all 3,428 original IM rows for exactly 20 epochs. Its 36-tensor complete checkpoint is saved/reloaded with strict state checks and identical same-device predictions on a fixed 16-row training probe. The EL parent is not refitted on EL validation; the historical Task 2.22 checkpoint is never combined with it.

This is an exploratory development evaluation. IM epoch 20 was selected using this same validation cohort in Task 2.22; the combined procedure therefore has no independent final test here. Exact-sequence novelty does not rule out similar peptides, shared HLA biology, or exposure in possible external representations; this run starts from a fresh authentic constructor rather than external pretrained weights. The ten-epoch search and EL validation selection can overfit EL validation. A subsequent separately authorized independent evaluation should freeze the complete procedure first.

## Preflight evidence

Eighty focused unittest checks passed on the installed WSL2 Python 3.13.5 GPU environment. Tests cover exclusion/group integrity, HLA positive anchors, candidate restrictions/ties, novelty failure, pooled/macro AP, native BCE denominator and optimizer continuation, sampler identity delegation, and existing runner/loss-adapter contracts. A first test command named a nonexistent compatibility test module; the corrected four-module command passed all 80 tests. An initial preflight was interrupted during preparation to fix excessive temporary set construction; no training occurred. A later manifest writer duplicate-key error also occurred before training. Its failure receipt and 140-byte compressed header fragment remain preserved; the complete authoritative manifest is `processed/el_split_manifest_v1.csv.gz`. The corrected preflight passed and freezes its SHA256.

IM-validation exclusion removes **11 EL rows: 10 positive, 1 negative**, spanning ten of the 665 excluded peptide sequences. The fixed exclusion list contains all 665 sequences, including those absent from EL.

| EL partition | Rows | Positive | Negative | Unique peptides | HLAs |
| --- | ---: | ---: | ---: | ---: | ---: |
| Training | 1,308,196 | 63,053 | 1,245,143 | 1,122,528 | 49 |
| Validation | 145,371 | 7,006 | 138,365 | 124,828 | 47 |

All retained rows occur exactly once; original labels and provenance are preserved. Exact sequence/pair overlap between EL partitions is zero. All 686 IM validation rows / 665 sequences are absent from both EL partitions and from the 2,742-row IM training subset; pair overlaps are also zero. Every remaining EL HLA has training representation and at least one original positive anchor. EL validation exceptions: B*39:10 (10 remaining rows, 2 positives; no validation rows), B*44:05 (16 rows, 2 positives; validation negatives only), B*57:02 (32 rows, 5 positives; no validation rows). Their groups and labels were unchanged. Per-HLA AP excludes validation HLAs without both classes.

## Execution and all ten EL epochs

Scientific execution commit: `a02f836e9bcee212fe8764339e34433fbf80f27d`. CUDA preflight passed with authentic 36-tensor FP32 architecture, deterministic algorithms and TF32 disabled. Every candidate complete checkpoint strictly reloaded. EL optimizer state persisted for all ten epochs. All-row eval BCE uses summed logit BCE divided by observations; update BCE uses the native sampled training population and batch denominators.

Native EL sampling per epoch consumes 1,071,901 rows: 63,053 positive and 1,008,848 negative exposures. Requested batch size 16 yields native maximum actual batch size 17; the pinned positive-anchor algorithm is unchanged. Eligibility/split coverage refers to all source rows, while sampling exposes a stochastic subset of negatives. The reused runner names its no-adapter audit field `native_unweighted_IM` even in EL reports; the executed EL loss is native unweighted BCE and all 36 EL parameters are optimized. This field name does not introduce IM sampling, weighting or auxiliary supervision into EL.

| EL epoch | Candidate | Pooled AP | AUROC | Macro HLA AP | Train update BCE | Train eval BCE | Validation BCE | Updates |
| ---: | :---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | yes | 0.843953736 | 0.988740161 | 0.767042991 | 0.076768067 | 0.053331067 | 0.054443687 | 63053 |
| 2 | yes | 0.857329174 | 0.990233386 | 0.800138128 | 0.059370350 | 0.049391001 | 0.051279308 | 63053 |
| 3 |  | 0.868599488 | 0.991050677 | 0.809238048 | 0.055513446 | 0.046539968 | 0.048668764 | 63053 |
| 4 | yes | 0.872537129 | 0.991326996 | 0.820390189 | 0.053528973 | 0.044354595 | 0.047593214 | 63053 |
| 5 |  | 0.871759723 | 0.991672753 | 0.823337954 | 0.051916600 | 0.044404010 | 0.047221429 | 63053 |
| 6 | yes | 0.876875260 | 0.991742612 | 0.834217100 | 0.050997287 | 0.042999128 | 0.047267906 | 63053 |
| 7 |  | 0.876002160 | 0.991773334 | 0.828974028 | 0.050312228 | 0.042466495 | 0.046946270 | 63053 |
| 8 | yes | 0.878240105 | 0.991799690 | 0.829902587 | 0.049627475 | 0.042398108 | 0.046367457 | 63053 |
| 9 |  | 0.882767661 | 0.992163088 | 0.834884054 | 0.049189607 | 0.042443838 | 0.046462303 | 63053 |
| 10 | yes | 0.880037743 | 0.991715571 | 0.824149123 | 0.048550950 | 0.040736540 | 0.045895454 | 63053 |

**EL epoch 10 selected**, solely by highest pooled validation AP among the six predefined candidates. Exact ties prefer earlier epochs. Selection was saved before downstream IM fits. The full 46-evaluable-HLA AP curves, candidate tensor/file identities, configuration SHA256 and source-coordinate sampling evidence are preserved in run reports. No EL refit on its validation partition occurred.

## Matched 20-epoch IM development comparison

| EL parent epoch | IM epochs | IM AP | IM AUROC | Train update BCE | Train eval BCE | Validation BCE |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 1 | 20 | 0.431021806 | 0.708562060 | 0.446392522 | 0.432478742 | 0.550422915 |
| 10 | 20 | 0.489327862 | 0.730287165 | 0.401442420 | 0.386722491 | 0.537724266 |

Same 686 observations (191 positives, 495 negatives), 665 unique peptides, with training subset fixed at 2,742 rows (764 positives, 1,978 negatives). AP change selected versus epoch 1 = **+0.058306056**; AUROC change = **+0.021725104**. Every ordered sampled batch hash, native all-negative skip mask and RNG boundary matches between the two IM fits; each updates only the four native transfer parameters. Both models have complete checkpoints and original-coordinate validation predictions. All 20-epoch training/validation loss curves are saved in `reports/IM_from_EL_01_learning_curve.json` and `reports/IM_from_EL_10_learning_curve.json`; the final all-data training curve is `reports/final_all_IM_learning_curve.json`. These outcomes did not revise EL selection. No historical Task 2.17/2.22 checkpoint was used.

## Final full-data model and reload

The final fresh IM model starts from new EL epoch 10 and trains on all 3,428 original observations for 20 epochs. Complete checkpoint: project runs / `task-2_23-el-multiepoch-baseline/checkpoints/final_all_IM/`. It contains 36 files (349,848,462 bytes). SHA256 of the canonical sorted filename-to-file-SHA256 JSON map: `b92308ab3e35d02530867053ada7e29ee18076bf653df26458f5c3728a2be3a0`. Individual file and tensor identities and explicit EL parent are in `reports/final_checkpoint.json`. Strict tensor reload passed; fixed 16-training-row probe maximum prediction difference = 0.0, exactly identical = True. The EL parent was selected with held-out EL validation and has not been refitted on that partition.

Final all-IM epoch-20 training update BCE = 0.408369345996; all-training eval BCE = 0.387465079405. These are training diagnostics. The final model was not evaluated as held-out on its own fitting rows or on independent neoepitope outcomes.

## Runtime and GPU resources

Workflow elapsed time after input/split/runtime setup: **14388.046 seconds (3.997 hours)**. Peak host RSS: 3,409,592,320 bytes.

| Stage | Epochs | Stage wall seconds | Training-loop seconds | Peak allocated GPU bytes | Peak reserved GPU bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| EL | 10 | 14214.085 | 10832.277 | 1,876,995,072 | 2,149,580,800 |
| IM_from_EL_01 | 20 | 49.509 | 32.547 | 1,058,706,432 | 2,149,580,800 |
| IM_from_EL_10 | 20 | 47.592 | 31.263 | 1,058,706,432 | 2,149,580,800 |
| final_all_IM | 20 | 59.388 | 42.084 | 1,058,706,432 | 2,149,580,800 |

479 nvidia-smi snapshots every 30 seconds, beginning after startup: mean/max GPU utilization 66.6/79%; max system VRAM 3086 MiB; mean/max power 230.4/254.9 W; max temperature 59 C. System snapshots include display usage and are distinct from Torch allocator peaks. Stage wall includes evaluation/checkpoint work; synchronized training-loop times are not kernel profiles.

## Scientific interpretation and next step

EL epoch 1 AP 0.843953736 versus selected epoch 10 AP 0.880037743; selected-minus-first = +0.036084007. Epoch 9 to 10 AP change = -0.002729918. Additional EL epochs are not clearly justified by this single, flattening and noisy curve: epoch 10 AP is below noncandidate epoch 9, and later candidate gains are small. Independent assessment of the frozen procedure has priority over another epoch search. The matched IM result supports improved developmental peptide-unseen ranking for the selected EL initialization. A single seed, one EL split, one already-used IM development cohort and candidate selection noise limit causal/generalization claims. Similar peptides can bridge partitions; exact exclusion guarantees sequence novelty only. There can be shared HLA biology and possible externally pretrained representation exposure in other model lineages, although this run uses a fresh constructor and no public pretrained weights. IM epoch 20 was chosen using this cohort in Task 2.22. These results are not an independent assessment of the combined training procedure. Proposed next step: freeze this complete model-selection/transfer procedure and obtain authorization for an independent peptide-unseen evaluation with a verified exposure inventory, keeping sealed test outcomes unopened until that review. No additional search, stability variant, archive, merge or push was performed.

## Completion verification

The read-only [completion verifier](../scripts/verify_bigmhc_el_multiepoch.py) passed after execution: **505 scientific outputs** authenticated against the saved output manifest, all ten EL pooled/macro/per-HLA AP and pooled AUROC recomputed exactly from original-coordinate predictions, both final 686-row IM AP/AUROC pairs recomputed, optimizer step continuity and RNG continuity checked across every fit, and both IM batch/skip/RNG schedules matched for all 20 epochs. Final complete checkpoint file identities and exact probe reload were verified. It performed no new model scoring or independent-test access. The 80 focused tests, passed data/CUDA preflight, training stdout, GPU samples and verification log are preserved under the run's `logs/`; resource summaries and their log hashes are recorded separately in `reports/resource_summary.json` and `reports/finalization_manifest.json`.
