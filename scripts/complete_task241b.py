"""Durable continuation of the already frozen Task 2.41-B experiment.

Wait for the six authorized fits, run frozen inference/evaluation/reproduction,
then record results locally. No fitting, selection or scientific settings here.
"""
from __future__ import annotations
import hashlib,json,subprocess,sys,time
from pathlib import Path
from stability_label_curation.low_stability_hard_filter import ARMS,ALL,BRANCH,setup,read_json,write_json,git,digest,require

def run(action):
    subprocess.run([sys.executable,'-m','stability_label_curation.low_stability_hard_filter',action],check=True)

def number(v):return 'undefined' if v is None else repr(v)

def report(p,d):
    a=read_json(d/'evaluation/aggregate.json');im=a['IMPROVE'];ci=read_json(d/'evaluation/paired_intervals.json')
    proof=read_json(d/'reports/preflight.json');summary=proof['summary'];frozen=read_json(d/'reports/predictions_frozen.json')
    fits={arm:read_json(d/f'reports/{arm}_training_completed.json') for arm in ARMS}
    supervisor=read_json(d/'reports/supervisor_completed.json')
    betterA=im['contrasts']['H-A']['AP']>0;betterR=im['contrasts']['H-mean_R']['AP']>0
    if betterA and betterR:
        answer='点推定ではHはAおよびランダム除外平均を上回った。選択的除外の利点の可能性があるが、区間と探索的性質を踏まえ独立集団の確認が必要。'
    elif betterA:
        answer='HはAを上回ったがランダム除外平均を上回らず、安定性に固有の利点は確認できない。'
    elif betterR:
        answer='Hはランダム除外平均を上回ったがAを上回らず、元の学習データを保持するより有利とは言えない。'
    else:
        answer='HはAおよびランダム除外平均を上回らず、この固定条件でlow-Stab hard filteringの追加的利点は確認できない。'
    lines=['# Task 2.41-B — Low-stability hard filtering versus matched random filtering','',
        answer,'',
        '## 固定した設計とpreflight','',
        f'- Branch: `{BRANCH}`。Base: `7ccf81de8ccb6bd1340c34f17b320ce4e0dbee06`。',
        '- Protocol/implementation commit: `a44adef`。Preflight-ready commit: `e541999`。',
        '- 実行環境: Z790 WSL2 / RTX 4090、既存bigmhc-gpu環境。新規13件と既存native EL関連14件、計27 focused tests PASS。',
        '- A: Task 2.23 EL epoch 10（IMモデルではない）。File-map SHA256: `d8e3d7d3ac5d08d7f420e00b8032fa875b8b6fec1cd9da6b36d35bca0bec04d1`。再学習なし。',
        '- 保存済みAのEL validationおよびIMPROVE予測を、元のsource bindingと固定先頭16行のGPU forward一致で認証して再利用。IMではlogitとFP32 sigmoidがbitwise一致。',
        '- 元EL学習: 1,308,196行、陽性63,053、陰性1,245,143。固定validation: 145,371行、陽性7,006、陰性138,365。学習/validationのpeptide重複なし。',
        f"- Teacherスコアcoverage {summary['Teacher_score_coverage']}/63,053。原Teacher per-HLA Ridge、予測kinetic half-life（hours）。チェックポイントSHA256: `{summary['Teacher_checkpoint_sha256']}`。",
        '- Task 2.31の除外前・学習陽性のみのexact percentile ledgerを固定利用。新たなTeacher推論や除外後rank再計算なし。',
        f"- 各群は陽性{summary['excluded']:,}行（全陽性の{100*summary['excluded_fraction_of_all_positives']!r}%）を物理的に除外。残存{summary['retained_total']:,}行＝陽性{summary['retained_positive']:,}＋陰性{summary['retained_negative']:,}。",
        '- H: HLA別floor(n/10)、rank同点はsource-row IDの辞書順。R1–R5: seed 20264101–20264105、同じ対象母集団からHLA×長さの除外数を完全一致させたランダム選択。',
        f"- {len(summary['by_stratum'])} HLA×長さ層、最小残存陽性数{min(v['remaining_positive'] for v in summary['by_stratum'].values())}。ラベル変更0、陰性除外0、score欠損/対象外陽性{summary['missing_or_outside_positive']}。各群の全行readback、元データ照合、ordered陰性fingerprint一致を確認。",'',
        '## 学習とモデル同一性','',
        '- H/R1–R5は全てAの元epoch-0初期化・元RNGから学習。A epoch 10からのfine-tuningではない。',
        '- seed42、CUDA FP32、AdamW lr5e-5、元のdefaults、native 1陽性＋16陰性sampler、batch-mean BCE。補助loss・sample weighting・label correctionなし。',
        '- 10 epoch全て完了、最終epoch10固定。各群のoptimizer連続性、36 trainable tensors、checkpoint保存/reload同一性を確認。',
        '- H/Rの陰性pool・sampling実装・seedは同一。物理削除によりdataframe permutationが変わるため、実際の負例抽出順まで同一とは主張しない。Aよりanchor/更新数が少ない点も介入の一部。',
        '- 6独立process、各4 CPU threadsで実行。GPU/RNG contextはprocess別。ランダム除外の5反復はtraining seedの5反復ではない。','',
        '| Arm | epochs | optimizer updates | checkpoint file-map SHA256 | seconds | peak allocated GPU bytes | peak RSS bytes |',
        '|---|---:|---:|---|---:|---:|---:|']
    for arm,r in fits.items():
        canonical=hashlib.sha256(json.dumps(r['files'],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        lines.append(f"| {arm} | {r['epochs']} | {r['optimizer_steps']} | `{canonical}` | {r['seconds']!r} | {r['peak_GPU_allocated_bytes']} | {r['peak_RSS_bytes']} |")
    lines+=['',f"学習wall time（6群全体）: {supervisor['seconds']!r} seconds。全epochのnative step loss、BCE、batch identity hash、RNG、validation値はrun下`reports/{{arm}}_EL_epoch_{{epoch}}.json`と`{{arm}}_EL_metrics_{{epoch}}.json`に保存。",'',
        '## IMPROVE zero-shot IM結果','',
        f"固定{im['n']}観測、陽性{im['positive']}、陰性{im['negative']}、prevalence/random-ranking AP reference={im['prevalence']!r}。元の38 patient/peptide dependence componentsを保持。",
        '全群ともEL分類logitのnative FP32 sigmoid（高いほどpositive）を使用。HLA正規化、IM transfer、fusion、calibrationなし。全7予測vectorを凍結した後に元IMラベルを結合。','',
        '| Arm | AP | AUROC | Precision@10 | Precision@20 |','|---|---:|---:|---:|---:|']
    for arm in ALL:
        m=im['arms'][arm];lines.append('| '+arm+' | '+' | '.join(number(m[k]) for k in ['AP','AUROC','precision_at_10','precision_at_20'])+' |')
    lines+=['',f"R1–R5の個別APの平均: {im['mean_random_AP']!r}。予測scoreを平均したensembleではない。",'',
        '| Contrast | AP difference | 95% paired component interval | AUROC difference | 95% paired component interval |',
        '|---|---:|---|---:|---|']
    for name,m in im['contrasts'].items():
        def interval(metric):
            x=ci['intervals'][name][metric];return f"[{number(x['lower_95'])}, {number(x['upper_95'])}]"
        lines.append(f"| {name} | {number(m['AP'])} | {interval('AP')} | {number(m['AUROC'])} | {interval('AUROC')} |")
    lines+=['',f"Bootstrap: {ci['attempts']} attempts、seed {ci['seed']}、38 components、paired整数multiplicity、元の固定score。invalid reasons={ci['invalid_reasons']}。各対比のusable/invalid数は`evaluation/paired_intervals.json`。逆向きのdrawも保持し、再抽選なし。",'',
        '## 固定EL validation結果','',
        '| Arm | EL AP | EL AUROC | BCE | macro HLA AP |','|---|---:|---:|---:|---:|']
    for arm,m in a['EL_validation'].items():lines.append('| '+arm+' | '+' | '.join(number(m[k]) for k in ['validation_AP','validation_AUROC','validation_BCE','macro_HLA_AP'])+' |')
    lines+=['','| Arm | ΔEL AP versus A | ΔEL AUROC versus A |','|---|---:|---:|']
    for arm in ARMS:
        m=a['EL_validation'][arm];b=a['EL_validation']['A'];lines.append(f"| {arm} | {m['validation_AP']-b['validation_AP']!r} | {m['validation_AUROC']-b['validation_AUROC']!r} |")
    lines+=['','陽性/陰性別mean probability、Brier、固定0.5におけるrecall/specificityは`aggregate.json`の`EL_validation.*.classes`。これはEL指標でありIM改善とは区別する。Aのepoch数はこのvalidationで既に選択されており、独立testではない。','',
        '## HLA別記述と削除数診断','',
        '| HLA | n | IM positive | A AP | H AP | mean R AP | H−A | H−mean R |','|---|---:|---:|---:|---:|---:|---:|---:|']
    for h,m in a['IMPROVE_per_HLA'].items():
        lines.append(f"| {h} | {m['n']} | {m['positive']} | {number(m['arms']['A']['AP'])} | {number(m['arms']['H']['AP'])} | {number(m['mean_random_AP'])} | {number(m['contrasts']['H-A']['AP'])} | {number(m['contrasts']['H-mean_R']['AP'])} |")
    lines+=['','単一classのAP/AUROCはundefined。小さいHLA群も記述のみで、好都合なHLAをprimaryに昇格していない。全HLA×長さの除外数、EL陽性score変化、IM score変化は`aggregate.json/exclusion_prediction_diagnostics`。','',
        '## 研究上の結論・限界','',answer,'',
        'H−Aは選択的削除、サンプル数減少、anchor/更新数減少を合わせた効果である。H−R平均は同じHLA×長さ・削除数・更新数との比較で、安定性に基づく選択の追加効果を見る。ランダム除外の結果幅も示したが、training seed間の分散は評価していない。',
        'IMPROVEは過去に繰り返し評価済みの探索的コホート。38成分によるbootstrapも独立外部確認や因果的根拠を与えない。Teacherのkinetic stabilityは実測Tm、surface persistence、EL-label正誤、T-cell recognitionと同一ではない。低安定性の陽性が誤ラベルであるとの主張はしない。',
        'EL陰性は主に構成decoyであり、EL validation改善を自然提示やIMへの一般化と読み替えない。独立集団・別seed・別削除率の有効性は未確認。本実験の結果から自動で閾値探索や追加モデルを開始しない。','',
        '## 保存物と再現性','',
        f'Run root（paths resolver）: `~/codex/runs/stability-label-curation/{d.name}/`。個別学習行、患者情報、予測、checkpointはGit外。',
        '- `inputs/{arm}_train.csv.gz` / `{arm}_excluded.csv.gz`: 物理的subsetと除外行manifest。SHA256は`reports/preflight.json`。',
        '- `reports/row_integrity.json`, `stability_distribution.json`, `runtime.json`: source/label/negativepool/Teacher coverage検証。',
        '- `reports/{arm}_training_completed.json`: 最終checkpoint file hashes、native tensor hashes、optimizer回数、reload、全10epoch。',
        '- `reports/predictions_frozen.json`: 全7群のscore hashes、source-order hash、IM unblinding前receipt。',
        '- `evaluation/aggregate.json`, `paired_intervals.json`, `paired_component_draws.jsonl.gz`: 最終表とpaired不確実性。',
        '- `reports/reproduction.json`: 保存済み予測と認証ラベルからaggregateの完全一致を確認。model再実行なし。',
        '- 本実験の新規IM training、Teacher再学習/再推論、label flipping、weighting、calibration、結果による選択/調整、merge/pushはいずれも実施なし。','']
    return '\n'.join(lines)

def main():
    p,c,d,proof=require()
    completion=d/'reports/durable_completion_started.json'
    if completion.exists():raise FileExistsError('Completion runner already started; no automatic retries')
    write_json(completion,{'commit':git(p.repository_root,'rev-parse','HEAD'),'scientific_protocol_changed':False})
    while not (d/'reports/supervisor_completed.json').exists():time.sleep(30)
    if read_json(d/'reports/supervisor_completed.json')['status']!='PASS':raise RuntimeError('Training failed; preserve evidence and stop')
    run('infer')
    # Score-only receipt commit precedes the first IM outcome association.
    freeze=d/'reports/predictions_frozen.json'
    compact=p.repository_root/'configs/low_stability_hard_filter_task241b.predictions_frozen.json'
    write_json(compact,{'prediction_receipt_sha256':digest(freeze),'training_protocol_commit':'e541999','rows_per_arm':7788,'model_arms':list(ALL),'IM_labels_opened':False})
    subprocess.run(['git','add',str(compact.relative_to(p.repository_root))],cwd=p.repository_root,check=True)
    commit=['git','-c','user.name=Takanori Hasegawa','-c','user.email=5525506+hase62@users.noreply.github.com','commit']
    subprocess.run(commit+['-m','Seal all Task 2.41-B predictions before IM outcome evaluation'],cwd=p.repository_root,check=True)
    run('evaluate');run('reproduce')
    dest=p.repository_root/'docs/LOW_STABILITY_HARD_FILTER_TASK2_41B.md'
    dest.write_text(report(p,d))
    write_json(d/'reports/final_outputs.json',{'status':'COMPLETE','report_sha256':digest(dest),'aggregate_sha256':digest(d/'evaluation/aggregate.json'),
        'pre_evaluation_commit':read_json(d/'reports/evaluation_started.json')['pre_evaluation_commit'],'checkpoint_files_git_committed':False})
    subprocess.run(['git','add',str(dest.relative_to(p.repository_root))],cwd=p.repository_root,check=True)
    subprocess.run(commit+['-m','Report frozen hard-filter versus random-filter EL and zero-shot IM results'],cwd=p.repository_root,check=True)
    if git(p.repository_root,'status','--porcelain'):raise RuntimeError('Unexpected dirty task worktree')
    write_json(d/'reports/final_commit.json',{'commit':git(p.repository_root,'rev-parse','HEAD'),'branch':git(p.repository_root,'branch','--show-current'),'clean':True,'merged':False,'pushed':False})
    print('TASK241B_COMPLETE',git(p.repository_root,'rev-parse','HEAD'),flush=True)

if __name__=='__main__':main()
