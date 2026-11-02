"""Read-only audit enrichment and non-overwriting delivery of the new run."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time
import zipfile

from stability_label_curation import hla_extended_epochs as m


def csv_text(rows):
    out=io.StringIO(newline='')
    w=csv.DictWriter(out,fieldnames=list(rows[0]),lineterminator='\n')
    w.writeheader();w.writerows(rows)
    return out.getvalue()


def collect_details():
    p,c,d=m.paths_config();inventory=m.read(d/'audit/source_inventory.json');details=[]
    for pilot in m.read(d/'audit/pilot_evidence.json'):
        root=p.project_runs_dir/pilot['run']/pilot['arm']
        for stage,item in pilot['stages'].items():
            path=root/'checkpoints/el'
            if stage=='IM':path=path/'im'
            receipt=item['checkpoint_receipt'];expected=receipt['files']
            actual={name:m.sha(path/name) for name in expected}
            if actual!=expected:raise ValueError('Historical pilot checkpoint changed')
            details.append({'run':pilot['run'],'arm':pilot['arm'],'stage':stage,
                'checkpoint':str(path),'file_count':len(expected),'file_map_sha256':m.scoring.digest(actual),
                'files_match_stored_receipt':True,'EL_parent_needed':stage=='IM'})
    # Provenance of the original implemented loss/head, not just report prose.
    code=[]
    imports=__import__('ast')
    name='src/stability_label_curation/bigmhc_stability_auxiliary.py'
    commits={'Task2.21':'ca1bd9629079f7f0ad286731f3ed4773c3d14d8d',
             'Task2.24':'78acffaeec105489a00f22780c374624ef5dc61f'}
    for label,commit in commits.items():
        source=subprocess.check_output(['git','-C',str(p.repository_root),'show',commit+':'+name],text=True)
        tree=imports.parse(source)
        funcs={node.name:hashlib.sha256(imports.dump(node,include_attributes=False).encode()).hexdigest()
               for node in tree.body if isinstance(node,(imports.ClassDef,imports.FunctionDef)) and node.name in ['AuxiliaryHead','losses','Targets','train_el']}
        code.append({'task':label,'commit':commit,'file':name,'source_sha256':hashlib.sha256(source.encode()).hexdigest(),'AST_hashes':funcs})
    # Extra small settings/provenance sources omitted from generic curve capture.
    extra={
        'task-2_37-a02-measured-tm-direct-transfer':['scientific_configuration','prepared','preflight','baseline_identity','train_started','train_resumed_started'],
        'task-2_24-fully-trained-stability-auxiliary':['initialization','preflight','baseline_compatibility'],
        'task-2_41b-low-stability-hard-filtering':['preflight','runtime'],
    }
    summaries={}
    for run,names in extra.items():
        for name in names:
            f=p.project_runs_dir/run/'reports'/f'{name}.json'
            if not f.exists():
                inventory.append({'source_path':str(f),'purpose':'extra original configuration','status':'NOT_FOUND'});continue
            inventory.append({'source_path':str(f),'purpose':'extra original configuration','status':'VERIFIED_LOCAL','size':f.stat().st_size,'sha256':m.sha(f)})
            value=m.read(f)
            # Preserve compact full execution/settings receipts; no predictions/outcomes.
            summaries[run+'/'+name]=value
    m.put(d/'audit/pilot_checkpoint_file_verification.json',details)
    m.put(d/'audit/auxiliary_original_code_comparison.json',code)
    m.put(d/'audit/additional_configuration_evidence.json',summaries)
    m.put(d/'audit/extended_source_inventory.json',inventory)
    print('CHECKPOINTS',len(details),'SOURCES',len(inventory))


def windows_folder():
    exe=shutil.which('powershell.exe')
    if not exe:raise RuntimeError('Windows PowerShell unavailable; cannot verify known folders')
    script="[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); $s=New-Object -ComObject Shell.Application; @{Downloads=$s.NameSpace('shell:Downloads').Self.Path;Desktop=[Environment]::GetFolderPath('Desktop')}|ConvertTo-Json -Compress"
    result=subprocess.check_output([exe,'-NoProfile','-NonInteractive','-Command',script],text=True,encoding='utf-8-sig').strip()
    folders=json.loads(result)
    for name in ['Downloads','Desktop']:
        if not folders.get(name):continue
        local=Path(subprocess.check_output(['wslpath','-u',folders[name]],text=True).strip())
        if local.is_dir():return local,folders[name],name
    raise RuntimeError('Neither Windows default Downloads nor Desktop available')


def write_report(status,rows,comparison):
    p,c,d=m.paths_config()
    base=p.project_runs_dir/'task-2_23-el-multiepoch-baseline'
    el=m.read(base/'reports/EL_learning_curve.json')['epochs']
    im=m.read(base/'reports/IM_from_EL_10_learning_curve.json')['epochs']
    lines=['# HLA epoch監査・拡張学習報告', '',f'状態: **{status}**。取得時刻: {datetime.now(timezone.utc).isoformat()}。',
      '', '既存の1 epoch結果・コード・checkpointを変更せず、新しいworktree/runだけを使用。新しい外部IM AP/AUROC/CI、bootstrapは計算していない。',
      '', '## Phase A：認証済みの履歴', '',
      'Task2.17 A/B/P、Task2.19 L/P、Task2.21 S/Pは、設定・stage完了receipt・全step数・checkpoint実ファイルを照合し、いずれもEL1→IM1、seed42を確認。Bが本拡張のWに対応する。',
      'pilotのEL全適格集団は1,453,578行（70,069陽性・1,383,509陰性）。各EL1 epochは70,069更新、1,191,173 sampled exposures。IMは3,428行（955陽性・2,473陰性）を入力し、all-negative batch1個をskipして214更新・3,412実最適化exposures。行数と反復使用したexposure数を区別する。',
      'pilotには独立EL validationがない。保存されたEL_proxyはIM dev383（120陽性・263陰性）上の指標であり、EL検証lossとは呼べない。1回のstageとbatch loss traceから収束や最適epochを証明できない。',
      '', '| pilot arm | EL更新BCE | IM更新BCE | 完了epoch |', '|---|---:|---:|---|']
    for item in m.read(d/'audit/pilot_evidence.json'):
        lines.append(f"| {item['run'].split('-')[1]} {item['arm']} | {item['stages']['EL']['loss']['row_weighted_BCE_loss']} | {item['stages']['IM']['loss']['row_weighted_BCE_loss']} | EL1 / IM1 |")
    lines+=['', '### データ数が変わる理由と補助学習の比較', '',
      'Task2.23は、既に固定されたIM validation 665配列とexact一致するEL11行（陽性10・陰性1）を除外後、残りを配列group単位でEL学習/検証に分割。学習1,308,196行（陽性63,053・陰性1,245,143）、検証145,371行（陽性7,006・陰性138,365）。train/validationの配列・peptide–HLA overlapは0。今回も同じmanifestを再利用し、分割を作り直していない。',
      'Task2.21/2.24は同じ原Teacher、414→1 linear補助head（415 scalar、head seed22042）、positive anchorのwithin-HLA rank target、batch平均BCE + 0.1×anchor MSE、IMではheadを外す設計。`audit/auxiliary_original_code_comparison.json`に元commitのクラス・関数AST fingerprintを記録。原headとlossの一致を確認し、epoch持続optimizer対応等の差は別扱い。Task2.21のrank参照は70,069陽性全体、2.24は学習陽性63,053のみ。学習予算はEL1/IM1対EL10/IM20であり、同一人口・予算の再現ではない。',
      '', '### 長時間学習と収束の限界', '',
      'A(Task2.23)はEL候補epoch1,2,4,6,8,10のうち検証AP最大で10を選択、10で予算終了。非候補epoch9のAPは10より高い。IM20は過去Task2.22の同一内部検証集団で選んだ固定期間であり、外部IM評価で選択していない。Early stoppingによる停止ではない。',
      f"A EL1→10: train update BCE {el[0]['train_update_BCE']} → {el[-1]['train_update_BCE']}; validation BCE {el[0]['validation_BCE']} → {el[-1]['validation_BCE']}; AP {el[0]['validation_AP']} → {el[-1]['validation_AP']}. 後半もAPは変動し、完全収束は未証明。",
      f"A EL10からの内部IM開発fit: epoch1→20のtrain eval BCE {im[0]['train_eval_BCE']} → {im[-1]['train_eval_BCE']}; validation BCE {im[0]['validation_BCE']} → {im[-1]['validation_BCE']}. 最小validation BCEはepoch{min(im,key=lambda r:r['validation_BCE'])['epoch']}で{min(x['validation_BCE'] for x in im)}、epoch20では悪化。validation APは{im[0]['validation_AP']} → {im[-1]['validation_AP']}。損失の最適化とランキング改善は同一ではなく、20 epochを一意に収束済みとは呼べない。",
      'Aのfinal full-IM20は全3,428行で再fitし、held-out IM validation lossは存在しない。学習eval BCEだけを収束の独立証拠にはしない。',
      'Task2.24 S/P: fixed EL10/IM20、早期停止・外部IMによる選択なし。EL training BCEはS 0.0772223830925593→0.04799678922560008、P 0.07767441991162882→0.04892452827373744。SのMSEは0.0766449973715527→0.04714387580562254、Pは0.09782460800490728→0.09297911447232078。独立EL検証AP/AUROC/BCEはこの実行経路に保存されていない。改善するtrain lossだけでgeneralizationの収束を主張しない。',
      'Task2.31 W/P: fixed EL10、IMなし。これは上位陽性upweightで、本実験の両方向Wとは違う。検証BCEはW 0.05467126038425421→0.04612716631058239、P 0.05418433348925672→0.045394203876895634。全epochとAP/AUROCは保存済みcurveを同梱。AはTask2.23を再利用。',
      'Task2.37: Jappe実測Tm（kinetic half-lifeではない）710 ligand＋11,360 decoy、A EL10から最終出力415 scalarのみ更新、20 passes、seeds123/456/789、D/P/T。dropout/BNをeval固定し、class-balanced BCEをsample-weight sumで割る。checkpointは最終20 pass、IM fitなし。新しいW/Lのnative BCE分母とは異なる別目的の転移実験。held-out adaptation-validation curveがなく、soft-target Tとbinary Dのloss値は直接比較しない。旧技術reload修復とD123の正確elapsed不明も原記録どおり保持。',
      'Task2.41b H/R1–R5: fixed EL10、seed42、IMなし。各群の陽性6,279を物理削除し、EL学習1,301,917行（56,774陽性・1,245,143陰性）。Aは元1,308,196行のEL10。最終epoch固定、early stoppingなし。全6群の保存検証curveを同梱し、削除後集団を今回のA/W/Lに流用しない。',
      '', '## Phase B：固定条件と実施状況', '',
      'preflight PASS、56 scientific focused tests PASS（失敗0・skip0、CUDA loss/gradient checksを含む）＋process分離2 tests PASS。事前固定commit: `72eb757df7836450956c37adbf0f0a256b500cc5`。',
      '追加点検で、同一Python内の学習後推論でinterop thread設定を二度呼ぶと失敗することを確認。科学実装・設定を一切変えず、実行管理のみcommit `a8ec298`で別プロセス推論へ分離した。元supervisorだけを置換し、4つの稼働中fitは停止・再学習せず維持。元workerの予測前setup失敗receiptも残し、完成checkpointから初回の実モデル推論を新プロセスで行う。その他の失敗を自動retryしない。',
      'paired seeds42/123/456。A42は元EL10とfinal full-IM20をSHA256・runtime・source・初期値で確認して再利用。A123/A456とW/L全6 fitは同じseedごとに新規初期化。全群固定EL10→IM20、lr5e-5、native AdamW、1陽性+16陰性、persistent optimizer、native batch-row BCE分母、元ラベル、同一HLA encoding。評価値で期間・checkpoint・seedを選ばない。',
      '学習陽性のみで事前計算したrankに基づき、W=1+0.5(r−0.5)、L=min(1,W)。このrank参照範囲は後期protocolと一致するがpilot全陽性rankと異なるため明記する。Wの平均重み1、Lの平均重み0.9375002668439971、31,512陽性downweight、Wでは31,512陽性upweight、陰性weight1。元Teacher全63,053陽性binding PASS、除外0、ラベル変更0。',
      '各seedのW/Lは、同seed Aの実際の全ordered batch hash・skip mask・optimizer設定・RNG境界に一致することを学習中に検証。IMでは重み付けせずnative4パラメータのみ更新。', '',
      '| arm | seed | 状態 | 実完了EL epoch | 実完了IM epoch | predictionファイル数 |', '|---|---:|---|---:|---:|---:|']
    for row in rows:
        lines.append('| '+' | '.join(str(row[k]) for k in ['arm','seed','status','EL_epochs_completed','IM_epochs_completed','prediction_files'])+' |')
    lines+=['', '予測はEL-onlyとIM-adaptedを別ファイルにし、各stageでIMPROVE7,788行・Neo267行。実際に保存済みの行数/SHA256は`prediction_files.csv`とcheckpoint manifestを参照。未生成の予測や未完了epochを完了と数えていない。',
      '新規IM AP/AUROC・paired差・CIはMac L2へ引き継ぐ。IMPROVEは既に繰り返し参照した探索的集団であり、独立確認ではない。Neoの患者/assay crosswalk不完全という既存制約も維持する。',
      '', '## Figure2aへの提案', '',
      '現時点では1 epoch結果をpilotとして補足資料へ移すのが妥当。1 epoch lossだけで十分な学習を確認できず、Aの長時間曲線には追加学習による変化がある。一方、長時間版はsplit/rank参照集団が異なるため、旧pilotの数値を上書き・同一実験として置換してはならない。',
      '新しいA/W/Lの全paired-seed fit、checkpoint reload、予測整合性とMac L2の固定評価が完了した後に、Figure2aを「共通長時間protocolの新しい探索的比較」として再構成することは可能。学習未完了またはIM評価未実施の段階で改善/悪化や置換完了とは結論しない。',
      '', '## 原本と再現性', '',
      '実パス・SHA256・JSON source記録はaudit/source_inventory.json、extended_source_inventory.json、pilot_checkpoint_file_verification.json。新規入力の指紋はreports/preflight.json、重みはreports/weights.json、各fitの実行commit・epoch・loss・checkpointとhashはreports/に保存。完全なstep logと大容量checkpointはWSL runに保持し、配布ZIPには含めない。',
      'Windows known folderはPowerShellのShell:Downloadsから取得し、利用不能時だけ標準Desktopを使用。既存run、checkpoint、Git branchの書換え、merge/push、外部送信は実施していない。']
    return '\n'.join(lines)+'\n'


def export():
    p,c,d=m.paths_config()
    done=d/'reports/execution_completed.json'
    status=m.read(done)['status'] if done.exists() else ('FAILED' if list((d/'reports').glob('*_FAILED.json')) else 'IN_PROGRESS')
    timestamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root=d/'exports'/timestamp;root.mkdir(parents=True)
    model_rows=[];checkpoint_rows=[];prediction_rows=[]
    for seed in c['seeds']:
        for arm in c['arms']:
            prefix=f'{arm}_{seed}';reused=prefix=='A_42'
            completed=[len(list((d/'reports').glob(f'{prefix}_{s}_epoch_*.json'))) for s in ['EL','IM']]
            if reused:completed=[10,20]
            predreceipt=d/f'reports/{prefix}_prediction_receipt.json'
            predictions=m.read(predreceipt) if predreceipt.exists() else {}
            for name,entry in predictions.items():
                f=Path(entry['path'])
                if not f.is_file() or m.sha(f)!=entry['sha256']:raise ValueError('New prediction integrity failed')
                prediction_rows.append({'arm':arm,'seed':seed,'file':name,**entry})
            model_rows.append({'arm':arm,'seed':seed,'status':'REUSED_AUTHENTICATED' if reused else ('COMPLETE' if (d/f'reports/{prefix}_completed.json').exists() else ('FAILED' if (d/f'reports/{prefix}_FAILED.json').exists() else ('RUNNING' if (d/f'reports/{prefix}_started.json').exists() else 'NOT_STARTED'))),
                'EL_epochs_completed':completed[0],'IM_epochs_completed':completed[1],'prediction_files':len(predictions)})
            for stage,epoch in [('EL',10),('IM',20)]:
                rec=d/f'reports/{prefix}_{stage}_checkpoint.json'
                a=m.read(rec) if rec.exists() else None
                checkpoint_rows.append({'arm':arm,'seed':seed,'stage':stage,'configured_epochs':epoch,
                    'epochs_completed':completed[0 if stage=='EL' else 1], 'checkpoint_path':a['checkpoint'] if a else 'NOT_YET_GENERATED',
                    'checkpoint_map_sha256':m.scoring.digest(a['files']) if a else '',
                    'checkpoint_receipt_path':str(rec),'checkpoint_receipt_sha256':m.sha(rec) if a else '',
                    'strict_reload':a['strict_reload'] if a else False, 'reused':reused,
                    'configuration_path':str(p.repository_root/m.CONFIG),'configuration_sha256':m.sha(p.repository_root/m.CONFIG),
                    'selection':'fixed_final_EL10_IM20','train_partition':'Task2.23','IM_metrics_computed':False})
    if status=='COMPLETE' and (len(prediction_rows)!=36 or any(r['EL_epochs_completed']!=10 or r['IM_epochs_completed']!=20 or r['prediction_files']!=4 for r in model_rows)):
        raise ValueError('Completion status inconsistent with actual epochs/predictions')
    # Supplementary historical trajectory CSV: extract stored scalar values only.
    historical=[]
    curves=m.read(d/'audit/long_training_evidence.json')
    for key,value in curves.items():
        if key.endswith('/training_complete'):
            for fit,record in value['fits'].items():
                for item in record['history']:
                    historical.append({'source':key,'condition':fit,'epoch':item['pass'],'train_loss':item['pass_weighted_BCE'],'validation_loss':'','validation_AP':'','validation_AUROC':''})
        else:
            for item in value.get('epochs',value.get('curve',[])) if isinstance(value.get('epochs',value.get('curve',[])),list) else []:
                historical.append({'source':key,'condition':key.split('/')[-1],'epoch':item['epoch'],
                    'train_loss':item.get('train_update_BCE',item.get('train_weighted_update_BCE',item.get('native_BCE',''))),
                    'validation_loss':item.get('validation_BCE',''),'validation_AP':item.get('validation_AP',''),'validation_AUROC':item.get('validation_AUROC','')})
    for name,items in [('HLA_TRAINING_CONFIG_AND_CHECKPOINT_MANIFEST.csv',checkpoint_rows),('model_execution_status.csv',model_rows),('historical_training_validation_trajectories.csv',historical)]:
        (root/name).write_text(csv_text(items))
    if prediction_rows:(root/'prediction_files.csv').write_text(csv_text(prediction_rows))
    else:(root/'prediction_files.csv').write_text('status\nNOT_YET_GENERATED\n')
    (root/'HLA_EPOCH_AUDIT_REPORT.md').write_text(write_report(status,model_rows,historical))
    # Authenticate selected original sources again; no broad historical rehash.
    before=m.read(d/'audit/extended_source_inventory.json')
    checks=[]
    for item in before:
        if 'sha256' not in item:continue
        path=Path(item['source_path']);actual=m.sha(path)
        checks.append({'path':str(path),'before_sha256':item['sha256'],'after_sha256':actual,'unchanged':actual==item['sha256']})
    if not all(x['unchanged'] for x in checks):raise ValueError('Historical audit source changed')
    m.put(root/'original_source_invariance.json',checks)
    package=root/'package';package.mkdir()
    copies=[]
    candidates=[f for f in root.iterdir() if f.is_file()]
    candidates+=list((d/'audit').glob('*.json'))
    candidates += [f for f in (d/'reports').glob('*.json') if '_epoch_' not in f.name and 'initializations' not in f.name]
    candidates += list((d/'reports').glob('*_metrics_*.json'))
    candidates += list((d/'predictions').glob('*.jsonl')) if (d/'predictions').exists() else []
    candidates += list((d/'cohorts').glob('*.jsonl'))
    candidates += [d/'inputs/training_only_weights.csv.gz',p.repository_root/m.CONFIG,p.repository_root/m.PROTOCOL,p.repository_root/m.SCRIPT,p.repository_root/'tests/test_hla_extended_epochs.py',
        p.repository_root/'src/stability_label_curation/hla_extended_execution.py',p.repository_root/'docs/HLA_EXTENDED_EXECUTION_NOTE.md',p.repository_root/'tests/test_hla_extended_execution.py']
    for f in candidates:
        if not f.exists():continue
        relative=f.relative_to(root) if f.is_relative_to(root) else ('run/'+str(f.relative_to(d)) if f.is_relative_to(d) else 'code/'+str(f.relative_to(p.repository_root)))
        dest=package/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(f,dest)
        if m.sha(f)!=m.sha(dest):raise ValueError('Audit copy hash mismatch')
        copies.append({'original_path':str(f),'archive_path':str(relative),'size':f.stat().st_size,'sha256':m.sha(f)})
    (package/'export_file_manifest.csv').write_text(csv_text(copies))
    internal=[f for f in package.rglob('*') if f.is_file()]
    (package/'SHA256SUMS.txt').write_text(''.join(f'{m.sha(f)}  {f.relative_to(package)}\n' for f in sorted(internal)))
    z=root/'HLA_EXTENDED_TRAINING_EXPORT.zip'
    with zipfile.ZipFile(z,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for f in sorted(package.rglob('*')):
            if f.is_file():archive.write(f,str(f.relative_to(package)))
    with zipfile.ZipFile(z) as archive:
        if archive.testzip() is not None:raise ValueError('Archive CRC failed')
        for line in (package/'SHA256SUMS.txt').read_text().splitlines():
            checksum,name=line.split('  ',1)
            if hashlib.sha256(archive.read(name)).hexdigest()!=checksum:raise ValueError('Archive content hash failed')
        filecount=len(archive.namelist())
    folder,win,kind=windows_folder()
    target=folder/f'HLA_EXTENDED_TRAINING_{status}_{timestamp}';target.mkdir()
    deliver=['HLA_EPOCH_AUDIT_REPORT.md','HLA_EXTENDED_TRAINING_EXPORT.zip','HLA_TRAINING_CONFIG_AND_CHECKPOINT_MANIFEST.csv']
    sums=''.join(f'{m.sha(root/name)}  {name}\n' for name in deliver)
    (root/'SHA256SUMS.txt').write_text(sums)
    for name in deliver+['SHA256SUMS.txt']:
        # WSL DrvFS may reject POSIX utime even when bytes are writable.
        # Deliver bytes and authenticate them; do not mutate Windows ACLs.
        shutil.copyfile(root/name,target/name)
        if m.sha(root/name)!=m.sha(target/name):raise ValueError('Windows copy failed')
    receipt={'status':status,'windows_known_folder':kind,'windows_directory':win+'\\'+target.name,
        'windows_zip':win+'\\'+target.name+'\\'+z.name,'zip_sha256':m.sha(z),'zip_size':z.stat().st_size,'zip_files':filecount,
        'run_export':str(root),'manifest_copy_checks':len(copies),'original_sources_unchanged':len(checks),
        'external_IM_metrics_computed':False,'git_commit':m.git(p.repository_root,'rev-parse','HEAD')}
    m.put(root/'delivery_receipt.json',receipt)
    print(json.dumps(receipt,ensure_ascii=False,indent=2))


if __name__=='__main__':
    if sys.argv[1]=='collect':collect_details()
    elif sys.argv[1]=='export':export()
    elif sys.argv[1]=='watch':
        _,_,d=m.paths_config()
        while not (d/'reports/execution_completed.json').exists():
            launch=d/'reports/supervisor_fresh_process_launch.json'
            if not launch.exists():launch=d/'reports/supervisor_launch.json'
            if not (Path('/proc')/str(m.read(launch)['pid'])).exists():
                raise RuntimeError('Supervisor disappeared; preserve incomplete state and inspect logs')
            time.sleep(30)
        export()
