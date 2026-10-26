#!/usr/bin/env python3
"""Render already frozen Task 2.40 result tables/figures; no scoring or metrics."""
from __future__ import annotations
from collections import Counter
import json
from pathlib import Path

from stability_label_curation.paths import resolve_paths


def main() -> None:
    paths=resolve_paths();run=paths.project_runs_dir/'task-2_40-frozen-el-stability-im-evaluation'
    points=json.loads((run/'aggregate_metrics.json').read_text());uncertainty=json.loads((run/'paired_uncertainty.json').read_text())
    freeze=json.loads((run/'prediction_freeze.json').read_text());execution=json.loads((run/'evaluation_complete.json').read_text())
    rel=json.loads((run/'label_free_score_relationships.json').read_text())
    columns=[('Mix native','mix_el_native'),('SPEARMINT native','spearmint_spa37_log1p_half_life'),('Mix EL rank','mix_el_rank'),('Stability rank','stability_rank'),('Fixed 50:50 fusion','fusion_rank_50_50')]
    def number(x):return 'undefined' if x is None else repr(x)
    lines=['# Frozen modern EL/stability IM evaluation — Task 2.40','',
      '**The fixed fusion did not improve the prespecified primary AP endpoint.** Its observed AP was lower than the same-scale Mix EL rank comparator; the paired component-bootstrap interval includes both negative and positive effects. No claim of a useful incremental kinetic-stability ranking benefit is supported by this exploratory run. This does not establish biological irrelevance of kinetic stability.','',
      '## Isolation, frozen design and execution order','',
      '- Branch: `task/2.40-frozen-el-stability-im-evaluation`; separate worktree `~/codex/repos/stability-label-curation-task240`. Exact base: `eb681b8504dc3ce73c1471e8cb14c411618a6bf2`.',
      '- Scientific implementation/protocol commit: `'+freeze['score_code_commit']+'`.',
      '- **Pre-evaluation prediction-seal commit: `'+execution['pre_evaluation_commit']+'`.** Final documentation commit is identified by Git HEAD and the external final receipt.',
      '- No Task 2.39 transformation discrepancy: unchanged observation-weighted within-HLA midrank `(less + 0.5 * equal) / N`; fixed fusion is the arithmetic mean of EL/stability ranks. Native pooled comparisons remain separate. Ranks and fusion are cohort-relative scores, not calibrated immunogenicity/presentation probabilities or clinical thresholds.',
      '- Bootstrap uses the already frozen `random.Random(24040).choices` stream, not fallback seed 202640 or the older BigMHC `randrange` stream. Original sorted patient/peptide units are retained.',
      '- No new public-model discovery/download, model fitting, IM calibration, checkpoint/head/temperature selection, thresholds, alternate fusion weights or cohort optimization. Neoepitope was not evaluated. Other branches, historical BigMHC results and checkpoints were preserved; no merge or push.','']
    lines+=['| Event | UTC |','|---|---|']
    for name in ['input_receipt.json','mix_started.json','spearmint_started.json','prediction_freeze.json','pre_evaluation_receipt.json','evaluation_started.json','evaluation_complete.json']:
        value=json.loads((run/name).read_text());lines.append(f"| {name} | {value['utc']} |")
    lines+=['','The Stage A module imports no outcome/evaluation loader. Its file-access guard denies other historical run and biological-data files; verified Mix child processes receive only local per-HLA peptide/input-output paths. Both complete native vectors, all ranks, fusion, the sensitivity mask and scientific code hashes were sealed before the pre-evaluation Git commit. Only the subsequent Stage B gate opened the original outcome sidecar. The scored identity population had not changed after outcome inspection.','',
      '## Model authentication and prediction integrity','',
      '| Model | Revision | Artifact SHA256 |','|---|---|---|',
      '| MixMHCpred v3.0 | `0a7f9b9e20d1cf02236f4a0a90d16735be879b38` | archive `ebd8f2b6e582909d4dc8cb2ab7da19f867b5cd3b3cf7502917ca12fecc4bc1b9` |',
      '| SPEARMINT Stage 3 | `93e8e3e640e49e5a373f0dc432b122df19e4b969` | safetensors `5b842af0c8b41fdf7a0ab329fe2bc76b92de0bf559dcede1501493fdf68cff8f` |','',
      'All runtime-source hashes and dependency versions were checked against authenticated Task 2.39 receipts/locks before inference. Full-length HLA sequences and their hashes were reused for all 36 alleles; no pseudosequence/nearest-allele substitution. Mix selected `Score_<designated HLA>`, including C0304 despite its tied C0303 nearest-reference metadata, and retained native six-decimal ties. No best-allele or PRIME score was substituted.',
      '', 'SPEARMINT used original full-chain tokenization and explicit chain-ID/CLS/EOS checks, Stage 3, SPA index 0, raw 37.0°C, batch size 4, FP32, eval/inference mode, no gradients, deterministic algorithms and disabled TF32. Remote snapshot and pickle fallbacks were blocked; only local safetensors were loaded. Parameter version counters were unchanged, and the on-disk checkpoint hash remained unchanged. Outputs are unconstrained native predicted log1p(hours), not measured lifetimes; finite negative outputs were retained without clipping.','']
    for model in ['mix','spearmint']:
        e=json.loads((run/(model+'_execution.json')).read_text())
        lines.append(f"- {model}: **{e['rows']} successful predictions; {e['failed']} failed**. No missing/duplicate/misaligned or nonfinite rows. Elapsed scoring/load time {e['seconds']} s; recorded self peak RSS {e['peak_RSS_KiB']} KiB.")
        if model=='spearmint':
            d=e['details'];lines.append(f"  Fixed first-four-row repeated batch was exactly equal; single/batch maximum absolute difference {d['single_batch_max_difference_first_four']}, inside fixed atol=1e-4/rtol=1e-5. Peak GPU allocation/reservation {d['peak_GPU_allocated_bytes']} / {d['peak_GPU_reserved_bytes']} bytes.")
    lines+=['','Z790/WSL2 Ubuntu 26.04.1 LTS; RTX 4090, driver 610.88; Python 3.13.5. SPEARMINT uses the existing PyTorch 2.13.0+cu130/CUDA 13.0 build with Transformers 4.57.1 and safetensors 0.6.2. Mix/evaluation use the isolated NumPy 2.2.6 environment. No shared environment, driver or CUDA libraries were changed. `runtime_environment.json` and execution receipts retain complete dependency versions and resource evidence. Aggregate evaluation plus all three 10,000-attempt resamplings took '+str(execution['seconds'])+' s.','',
      '## Sealed score identities','',
      'Original Task 2.32 identity SHA256: `33fbad5f142a93d0803b39800fa3dcb71437320c4134e92594080830b6f26986`. Task 2.39 allowlisted identity SHA256: `'+freeze['identity_manifest_sha256']+'`. Common-coverage manifest SHA256: `'+freeze['common_manifest_sha256']+'`. Ordered row-key hash: `'+freeze['ordered_keys_sha256']+'`.','',
      '| Frozen score artifact | SHA256 |','|---|---|']
    for name in ['mix_native.jsonl','spearmint_native.jsonl','rank_scores.jsonl','fusion_scores.jsonl','frozen_scores.jsonl']:
        lines.append(f"| {name} | `{freeze['artifact_sha256'][name]}` |")
    lines+=['','Prediction-freeze receipt SHA256 is `'+__import__('hashlib').sha256((run/'prediction_freeze.json').read_bytes()).hexdigest()+'`. Private row keys, peptides, patient-level data, scores and weights stay outside Git. No score table was overwritten or rerun after unblinding.','',
      '## Primary full-cohort result','',
      'All **7,788** frozen observations were retained: **227 positive, 7,561 negative**, prevalence/random-ranking reference **0.029147406266050335**, 6,576 unique peptides, 7,750 peptide–HLA pairs, 36 HLAs, 70 patients, three studies and 38 original patient/peptide dependence components. Repeated original biological observations were not deduplicated. The labels matched the authenticated original Task 2.26 sidecar SHA256 `64ed767d65e4e5f9895b1062f9ff160054d1d29b9b460d7bd3e8037279e31709` and its original curation receipt; every ordered source key matched.','',
      '| Score | Non-interpolated AP | AUROC | Precision@10 | Precision@20 | AP / prevalence |','|---|---:|---:|---:|---:|---:|']
    for label,c in columns:
        v=points['populations']['full_IMPROVE']['arms'][c];lines.append('| '+label+' | '+' | '.join(number(v[m]) for m in ['AP','AUROC','precision_at_10','precision_at_20','AP_over_prevalence'])+' |')
    main=points['populations']['full_IMPROVE'];ci=uncertainty['full_IMPROVE']['intervals']['fusion_minus_EL_rank']
    lines+=['',f"**Primary fusion minus EL-rank AP: {main['contrasts']['fusion_minus_EL_rank']['AP']}**, paired 95% percentile interval **[{ci['AP']['lower_95']}, {ci['AP']['upper_95']}]**. Secondary relative AP change: **{main['primary_relative_AP_change_percent']}%**. The interval spans zero; these results neither demonstrate benefit nor establish a precise harmful effect.",
      '',f"Fusion minus EL-rank AUROC: {main['contrasts']['fusion_minus_EL_rank']['AUROC']}, paired interval [{ci['AUROC']['lower_95']}, {ci['AUROC']['upper_95']}]. Precision@20 improved descriptively from 0.05 to 0.1 while Precision@10 stayed 0.1; neither replaces the failed primary AP comparison. Native Mix achieved AP 0.04240844678691356 and Precision@10/20 0.2/0.15. Do not attribute differences from native Mix to stability alone, because HLA rank normalization changes that comparator.",'',
      '## Paired uncertainty and prespecified secondary/sensitivity analyses','',
      '| Population | N / positive / negative | Units | EL-rank AP | Fusion AP | Fusion minus EL-rank AP | 95% paired interval | Valid / attempts |','|---|---|---:|---:|---:|---:|---|---|']
    for name in ['full_IMPROVE','A0201','training_neighbor_excluded']:
        p=points['populations'][name];u=uncertainty[name];v=u['intervals']['fusion_minus_EL_rank']['AP']
        lines.append(f"| {name} | {p['n']} / {p['positive']} / {p['negative']} | {u['number_of_units']} | {p['arms']['mix_el_rank']['AP']} | {p['arms']['fusion_rank_50_50']['AP']} | {p['contrasts']['fusion_minus_EL_rank']['AP']} | [{v['lower_95']}, {v['upper_95']}] | {u['valid']} / {u['attempted']} |")
    lines+=['','Exactly 10,000 attempts were made per planned population. Full and sensitivity analyses had no invalid attempts; A*02:01 had one no-positive draw (9,999 valid), retained in the audit log and not replaced. All score conditions used identical component multiplicities. Original full-cohort ranks were fixed throughout. Sensitivity reused the original 38-unit universe; A*02:01 retained its original 16 component keys. No row bootstrap or study-bootstrap interval was substituted.','',
      'Full-cohort component sizes ranged from 19 to 2,475 observations; A*02:01 ranged from 3 to 262. Large components and only 38/16 units limit precision. Shared study/acquisition effects and incomplete donor ancestry need not be captured fully by patient/peptide components; all studies connect in one study/peptide component, so a study-bootstrap interval is not identifiable. These are conditional exploratory uncertainty summaries, not 7,788 independent biological experiments or population-level clinical guarantees.','',
      '| Secondary paired contrast (full cohort) | AP difference | 95% paired AP interval | AUROC difference | 95% paired AUROC interval |','|---|---:|---|---:|---|']
    for name in ['native_stability_minus_native_EL','stability_rank_minus_EL_rank']:
        d=main['contrasts'][name];v=uncertainty['full_IMPROVE']['intervals'][name]
        lines.append(f"| {name} | {d['AP']} | [{v['AP']['lower_95']}, {v['AP']['upper_95']}] | {d['AUROC']} | [{v['AUROC']['lower_95']}, {v['AUROC']['upper_95']}] |")
    lines+=['','A*02:01 is secondary: 616 observations, 21 positives, 595 negatives, prevalence '+str(points['populations']['A0201']['prevalence'])+'.','',
      '| A*02:01 score | AP | AUROC | Precision@10 | Precision@20 |','|---|---:|---:|---:|---:|']
    for label,c in columns:
        v=points['populations']['A0201']['arms'][c];lines.append('| '+label+' | '+' | '.join(number(v[m]) for m in ['AP','AUROC','precision_at_10','precision_at_20'])+' |')
    d=points['populations']['A0201']['contrasts']['fusion_minus_EL_rank'];v=uncertainty['A0201']['intervals']['fusion_minus_EL_rank']
    lines +=['',f"A*02:01 AUROC difference is {d['AUROC']} with interval [{v['AUROC']['lower_95']}, {v['AUROC']['upper_95']}]. Its positive AUROC direction does not override its negative AP direction, lower top-K precision or its secondary status. There are only 21 positives and 16 dependence units.",
      '', 'The label-blind eight-observation sensitivity mask was hashed before predictions and sealed before labels. All eight excluded observations were subsequently found to be negative; the retained set is 7,780/227/7,553. No transformation was recomputed. The AP contrast remained negative and its interval still crossed zero. This exclusion does not resolve unverified Mix EL or MINT Stage 1/PPI ancestry.','',
      '## All-HLA descriptions','',
      'All alleles are listed alphabetically, without a favorable-subset gate. For a single HLA, native and within-HLA rank AP coincide because ordering/ties are preserved; the table uses the same-scale rank comparator. Full native/rank AP/AUROC and top-K values are retained in `aggregate_metrics.json`. Missing-class AP/AUROC are explicitly undefined, not replaced by another cohort.','',
      '| HLA | N | Positive | Negative | Mix EL AP | Stability AP | Fusion AP | Fusion minus EL-rank AP |','|---|---:|---:|---:|---:|---:|---:|---:|']
    heterogeneity=Counter()
    for a,p in points['per_HLA'].items():
        d=p['contrasts']['fusion_minus_EL_rank']['AP'];heterogeneity['undefined' if d is None else 'improved' if d>0 else 'deteriorated' if d<0 else 'equal']+=1
        lines.append(f"| {a} | {p['n']} | {p['positive']} | {p['negative']} | {number(p['arms']['mix_el_rank']['AP'])} | {number(p['arms']['stability_rank']['AP'])} | {number(p['arms']['fusion_rank_50_50']['AP'])} | {number(d)} |")
    lines+=['',f"Among 30 alleles with both classes, 13 improved and 17 deteriorated descriptively; six alleles have no positives and undefined AP/AUROC. Many class counts are very small. This heterogeneity does not support a general stability-fusion advantage, and no allele is promoted as a new primary target.",'',
      '## Label-free score relationships','',
      f"Overall native-score Spearman correlation: **{rel['overall_native_score_Spearman']}**. Pooled correlation of the two within-HLA percentile ranks: **{rel['pooled_within_HLA_rank_correlation']}**. Full per-HLA correlations are saved. These show partially shared rankings, not causally independent biology.",
      '', 'Fusion-induced within-HLA percentile displacement diagnostics: `'+json.dumps(rel['fusion_induced_within_HLA_percentile_changes'],sort_keys=True)+'`. This re-ranking is diagnostic only; the evaluated fusion remains the original arithmetic mean. Native SPEARMINT score range was '+str(rel['native_score_distributions']['spearmint_spa37_log1p_half_life']['minimum'])+' to '+str(rel['native_score_distributions']['spearmint_spa37_log1p_half_life']['maximum'])+'; values were not clipped or converted into supposed measured hours.','',
      '## Scientific interpretation and limits','',
      '1. Adding the fixed 50:50 stability rank did **not** improve primary AP beyond the same-scale modern EL rank. The primary difference is negative and exploratory uncertainty spans zero. No strong directional benefit is supported.',
      '2. A*02:01 AP and the fixed eight-neighbor sensitivity analysis also have negative observed AP differences. Mixed AUROC/top-K and HLA-specific effects do not rescue the primary hypothesis.',
      '3. No exact peptide or peptide–HLA match to published S2/S3 split indexes was found in Task 2.39, but eight training-neighbor observations were known. These facts do not establish complete novelty or zero leakage.',
      '4. Complete MINT Stage 1 BA, MINT PPI and MixMHCpred EL training identities remain unknown. Full source-publication/donor overlap and upstream IM-blind architecture/model-selection history remain unverified. Stability-only fitting objectives and this task\'s lack of IM fitting are distinct from complete development-history independence. SPEARMINT also inherits BA/PPI representations, so even a fusion benefit could not isolate causal kinetic-stability information.',
      '5. IMPROVE has prior exploratory use in the project; this is not untouched confirmation or prospective clinical validation. Patient-context assay negatives are not universal biological non-immunogenicity. Assigned HLA identities were preserved rather than reinterpreted as new experimental restriction evidence.',
      '6. Predicted kinetic half-life differs from Jappe measured thermal melting temperature, natural surface pMHC persistence and patient-derived T-cell recognition. This result says nothing definitive about stability\'s biological relevance or correctness of low-stability EL-positive labels.',
      '7. **NO-GO for advancing this fixed fusion as an improved predictor on the present evidence.** Independent confirmation would be required before any improvement claim, but this result provides no positive efficacy signal that warrants prioritizing adoption/confirmation of this exact fusion over EL alone. A future independently specified replication could still be scientifically informative; no further optimization or experiment is initiated here.','',
      '## Tests, reproduction and artifact boundaries','',
      'Twenty-six focused tests passed before predictions: 12 new Task 2.40 cases and 14 reused Task 2.39 cases. They cover identity/hash/alignment, designated HLA, full chains, fixed assay/offline contract, finite/sign-preserving scores, midranks/fusion, tie-aware AP/AUROC against brute-force weighted oracles, fractional top-K ties, paired fixed-rank component resampling, no-positive invalid draws/no rerolls, exact eight-row masks, scoring-file access restrictions and deterministic/no-overwrite serialization.',
      '', 'Saved-score aggregate tables were reproduced exactly against original authenticated labels, without running a model or recomputing ranks. All saved bootstrap multiplicities were reproduced with the frozen RNG, and percentile intervals were regenerated from the saved paired contrasts. `reproduction_verification.json` is PASS. No scientific scoring, metric, resampling, population or configuration code changed after unblinding. Reporting/plot rendering only reads completed result artifacts.',
      '', 'Run root: `~/codex/runs/stability-label-curation/task-2_40-frozen-el-stability-im-evaluation/`. Key outputs: `prediction_freeze.json`, `pre_evaluation_receipt.json`, `frozen_scores.jsonl`, `aggregate_metrics.json`, `paired_uncertainty.json`, three full bootstrap logs, `label_free_score_relationships.json`, model execution/environment logs, `reproduction_verification.json`, and `final_execution_receipt.json`. Large/private data and external weights are not in Git. Standalone figures are `figures/AP_comparison.png/.svg` and `figures/paired_AP_contrasts.png/.svg`.','',
      'No BigMHC/IM training, model fitting, calibration, coefficient or head search, threshold optimization, model selection, favorable cohort/HLA selection, historical-results revision, merge or push occurred. Stop after this single frozen evaluation; Task 2.41 has not started.','']
    (paths.repository_root/'docs/MODERN_EL_STABILITY_FROZEN_IM_EVALUATION_TASK2_40.md').write_text('\n'.join(lines))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figdir=run/'figures';figdir.mkdir(exist_ok=True)
    fig,axes=plt.subplots(1,2,figsize=(11,4),layout='constrained')
    for ax,name,title in zip(axes,['full_IMPROVE','A0201'],['Full IMPROVE — primary','A*02:01 — secondary']):
        p=points['populations'][name];ax.bar(range(5),[p['arms'][c]['AP'] for _,c in columns],color=['#3c6478','#b07848','#377ba8','#9b7350','#7865a7'])
        ax.axhline(p['prevalence'],color='gray',linestyle='--',label='Positive prevalence')
        ax.set_xticks(range(5),['EL native','Stability\nnative','EL rank','Stability\nrank','50:50\nfusion']);ax.set_ylabel('Non-interpolated AP');ax.set_title(title);ax.legend(fontsize=8)
    for suffix in ['png','svg']:fig.savefig(figdir/('AP_comparison.'+suffix),dpi=160)
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,3.8),layout='constrained')
    names=['full_IMPROVE','A0201','training_neighbor_excluded'];labels=['Full IMPROVE (primary)','A*02:01 (secondary)','Eight neighbors excluded']
    for i,name in enumerate(names):
        delta=points['populations'][name]['contrasts']['fusion_minus_EL_rank']['AP'];ci=uncertainty[name]['intervals']['fusion_minus_EL_rank']['AP']
        ax.errorbar(delta,i,xerr=[[delta-ci['lower_95']],[ci['upper_95']-delta]],fmt='o',capsize=5,color='#5f518f')
    ax.axvline(0,color='gray',linestyle='--');ax.set_yticks(range(3),labels);ax.invert_yaxis();ax.set_xlabel('AP(fixed fusion) − AP(EL rank), paired component-bootstrap 95% interval');ax.set_title('No demonstrated AP advantage from fixed stability fusion')
    for suffix in ['png','svg']:fig.savefig(figdir/('paired_AP_contrasts.'+suffix),dpi=160)
    plt.close(fig)
    print('Report and four figure artifacts rendered from frozen results')


if __name__=='__main__':main()
