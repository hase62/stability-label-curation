"""CPU preflight sentinels and byte/identity-only final handoff; no IM metrics."""
from __future__ import annotations

import base64
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import zipfile

from . import hla_epoch_recovery as recovery


def csv_write(path: Path, rows: list[dict]) -> None:
    with path.open('x',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)


def cpu_sentinel_tests(root: Path) -> dict:
    root.mkdir(parents=True)
    target=root/'checkpoints'/'sentinel';events=[]
    class Sentinel:
        def cpu(self):events.append('cpu');return self
        def save(self,path,*,tl):
            events.append('save');(Path(path)/'NOT_A_MODEL.bin').write_bytes(b'CPU IO TEST ONLY\n')
    failed=False
    try:
        recovery.science.runner.reserve_checkpoint(target)
        recovery.science.runner.save_checkpoint(Sentinel(),target,transfer=False,device='cpu')
    except FileNotFoundError as error:
        failed=error.filename=='checkpoints' and not events
    if not failed:raise AssertionError('Original missing-parent failure not reproduced')
    with recovery.science.runner.raw._directory(target.parent,create=True):pass
    recovery.science.runner.reserve_checkpoint(target)
    recovery.science.runner.save_checkpoint(Sentinel(),target,transfer=False,device='cpu')
    sentinel=target/'NOT_A_MODEL.bin';expected=recovery.sha(sentinel)
    if sentinel.read_bytes()!=b'CPU IO TEST ONLY\n':raise AssertionError('CPU sentinel differs')
    rejected=False
    try:recovery.science.runner.reserve_checkpoint(target)
    except FileExistsError:rejected=True
    if not rejected or recovery.sha(sentinel)!=expected:raise AssertionError('Overwrite prevention failed')
    return {'status':'PASS','tests':3,'original_failure_reproduced':True,'parent_fix_write_readback':True,'overwrite_rejected':True}


def incomplete_checkpoint_tests(root: Path, valid: Path) -> dict:
    files=sorted(valid.glob('*.lyr'));small=min(files,key=lambda f:f.stat().st_size)
    rejected=[]
    for name,all_files,marker in [('MISSING_FILES',False,False),('ALL_FILES_NO_MARKER',True,False),('CORRUPTED_WITH_MARKER',True,True)]:
        path=root/name;path.mkdir()
        for f in (files if all_files else [small]):
            if marker and f.name==small.name:
                (path/f.name).write_bytes(f.read_bytes()+b'INTENTIONAL_PREFLIGHT_CORRUPTION')
            else:os.link(f,path/f.name)
        if marker:
            spec=recovery.read(valid/recovery.MARKER);spec['checkpoint']=str(path)
            recovery.put(path/recovery.MARKER,spec)
        try:recovery.checkpoint_valid(path)
        except (ValueError,FileNotFoundError) as error:rejected.append({'case':name,'rejected':True,'reason':str(error)})
        else:raise AssertionError('Incomplete/corrupt checkpoint accepted')
    return {'status':'PASS','tests':len(rejected),'cases':rejected,'sources_modified':False}


def validate_scores(path: Path, keys: list[str]) -> dict:
    count=0
    with path.open() as stream:
        for count,line in enumerate(stream,1):
            row=json.loads(line)
            if (count>len(keys) or set(row)!={'source_id','native_logit','positive_probability'}
                or row['source_id']!=keys[count-1]):raise ValueError('Prediction schema/order/identity failure')
            if any(type(row[k]) not in (int,float) or not math.isfinite(row[k]) for k in ['native_logit','positive_probability']):
                raise ValueError('Nonfinite or nonnumeric score')
            if not 0<=row['positive_probability']<=1:raise ValueError('Score polarity/probability contract failed')
    if count!=len(keys):raise ValueError('Missing prediction rows')
    return {'n':count,'sha256':recovery.sha(path),'ordered_source_id_sha256':recovery.science.scoring.digest(keys)}


def windows_folders() -> list[tuple[Path,str]]:
    exe=shutil.which('powershell.exe')
    if not exe:raise RuntimeError('Windows known-folder lookup unavailable')
    code='[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);$ErrorActionPreference="Stop";$ProgressPreference="SilentlyContinue";$s=New-Object -ComObject Shell.Application;@{Downloads=$s.NameSpace("shell:Downloads").Self.Path;Desktop=[Environment]::GetFolderPath("Desktop")}|ConvertTo-Json -Compress'
    result=json.loads(subprocess.check_output([exe,'-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(code.encode('utf-16-le')).decode()],text=True,encoding='utf-8-sig'))
    return [(Path(subprocess.check_output(['wslpath','-u',result[k]],text=True).strip()),result[k]) for k in ['Downloads','Desktop'] if result.get(k)]


def windows_native_check(path: str, size: int, checksum: str, entries: int) -> dict:
    literal="'"+path.replace("'","''")+"'"
    code='[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false);$ErrorActionPreference="Stop";$ProgressPreference="SilentlyContinue";Add-Type -AssemblyName System.IO.Compression.FileSystem;$p='+literal+';$f=Get-Item -LiteralPath $p;$z=[IO.Compression.ZipFile]::OpenRead($p);$n=$z.Entries.Count;$z.Dispose();@{FullName=$f.FullName;Size=$f.Length;SHA256=(Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash;Entries=$n;Attributes=$f.Attributes.ToString()}|ConvertTo-Json -Compress'
    result=json.loads(subprocess.check_output([shutil.which('powershell.exe'),'-NoProfile','-NonInteractive','-EncodedCommand',base64.b64encode(code.encode('utf-16-le')).decode()],text=True,encoding='utf-8-sig'))
    if result['Size']!=size or result['SHA256'].lower()!=checksum or result['Entries']!=entries:
        raise ValueError('Windows-native ZIP verification failed')
    return result


def finish(execution: dict) -> dict:
    """Final CPU audit, frozen score receipt, then original outcome-byte handoff."""
    p,c,d,old=recovery.context();proof=recovery.read(d/'reports/preflight.json')
    recovery.check_code();recovery.verify_old_run()
    for name,expected in proof['frozen_inputs'].items():
        if recovery.sha(d/name)!=expected:raise ValueError('Input changed before final audit')
    complete=execution['status']=='COMPLETE'
    final=d/'final_export';final.mkdir()
    checkpoint_rows=[];prediction_rows=[];epoch_rows=[];tensor_rows=[]
    cohorts={}
    for name,spec in proof['config']['cohorts'].items():
        f=d/f'cohorts/{name}_identities.jsonl';rows=[json.loads(line) for line in f.read_text().splitlines()]
        keys=[r['source_id'] for r in rows]
        if len(keys)!=spec['n'] or len(set(keys))!=len(keys):raise ValueError('Frozen cohort count/duplicates differ')
        cohorts[name]=keys
    for seed in [42,123,456]:
        for arm in ['A','W','L']:
            prefix=f'{arm}_{seed}';reused=prefix=='A_42'
            for stage,epochs in [('EL',10),('IM',20)]:
                report=d/f'reports/{prefix}_{stage}_checkpoint.json'
                if not report.exists():
                    if complete:raise ValueError('Missing final checkpoint receipt')
                    checkpoint_rows.append({'arm':arm,'seed':seed,'stage':stage,'epochs':0,'checkpoint':'MISSING',
                        'checkpoint_map_sha256':'NOT_AVAILABLE','strict_reload':False,'reused':reused,'receipt_sha256':''})
                    continue
                spec=recovery.read(report);path=Path(spec['checkpoint'])
                actual=recovery.science.runner.checkpoint_identity(path,spec['state_keys'])
                if actual!=spec['files'] or len(actual)!=36:raise ValueError('Final checkpoint file identity differs')
                if reused:
                    if recovery.science.scoring.digest(actual)!=proof['config']['A_checkpoint_map_sha256'][stage]:
                        raise ValueError('Reused baseline changed')
                    child=d/f'reports/checkpoint_certification/A42_REUSED_{stage}_strict_reload.json'
                    if recovery.read(child)['state']!=spec['state']:raise ValueError('Baseline reload state differs')
                else:
                    marker=recovery.checkpoint_valid(path)
                    if marker['state']!=spec['state']:raise ValueError('Fit/marker state differs')
                    if stage=='IM' and set(spec['changed_parameters'])!=set(recovery.science.runner.TRANSFER):
                        raise ValueError('Non-native IM update detected')
                    files=sorted((d/'reports').glob(f'{prefix}_{stage}_epoch_*.json'))
                    if len(files)!=epochs:raise ValueError('Epoch count incomplete')
                    cumulative=0
                    for e,f in enumerate(files,1):
                        row=recovery.read(f)
                        if row['epoch']!=e or row['seed']!=seed or row['arm']!=arm:raise ValueError('Epoch identity differs')
                        cumulative+=row['optimization_steps']
                        if row['cumulative_optimizer_steps']!=cumulative:raise ValueError('Optimizer continuity differs')
                        if arm!='A':
                            base=p.project_runs_dir/proof['old_training_config']['baseline_run_id']
                            reference=(base/f'reports/{"EL" if stage=="EL" else "final_all_IM"}_epoch_{e:02d}.json'
                                if seed==42 else d/f'reports/A_{seed}_{stage}_epoch_{e:02d}.json')
                            baseline=recovery.read(reference)
                            for key in ['sampled_batch_sha256','optimizer_skip_mask','optimizer_defaults','updated_parameters','RNG_before','RNG_after']:
                                if row[key]!=baseline[key]:raise ValueError('Paired sampling/RNG/optimizer differs')
                        # Original failed EL traces are a reproducibility witness, never a selection criterion.
                        prior=old/f'reports/{prefix}_{stage}_epoch_{e:02d}.json'
                        if stage=='EL' and prior.exists():
                            witness=recovery.read(prior)
                            if any(row[k]!=witness[k] for k in ['sampled_batch_sha256','optimizer_skip_mask','optimizer_defaults','updated_parameters','RNG_before','RNG_after']):
                                raise ValueError('Retry scientific schedule differs from preserved failed run')
                        epoch_rows.append({'arm':arm,'seed':seed,'stage':stage,'epoch':e,'updates':row['optimization_steps'],
                            'cumulative_updates':cumulative,'sampler_sha256':recovery.science.binding.digest(row['sampled_batch_sha256']),
                            'source_path':str(f),'sha256':recovery.sha(f)})
                checkpoint_rows.append({'arm':arm,'seed':seed,'stage':stage,'epochs':spec['epochs'],'checkpoint':str(path),
                    'checkpoint_map_sha256':recovery.science.scoring.digest(actual),'strict_reload':True,'reused':reused,
                    'receipt_sha256':recovery.sha(report)})
                tensor_rows.extend({'arm':arm,'seed':seed,'stage':stage,'source_path':str(path/name),
                    'size_bytes':(path/name).stat().st_size,'sha256':checksum} for name,checksum in actual.items())
            prediction_receipt=d/f'reports/{prefix}_prediction_receipt.json'
            if not prediction_receipt.exists():
                if complete:raise ValueError('Missing prediction receipt')
                continue
            saved=recovery.read(prediction_receipt)
            if len(saved)!=4:raise ValueError('Prediction receipt file cardinality differs')
            for stage in ['EL','IM']:
                for name,keys in cohorts.items():
                    filename=f'{prefix}_{stage}_{name}.jsonl';path=d/'predictions'/filename
                    check=validate_scores(path,keys);expected=saved[filename]
                    if any(check[k]!=expected[k] for k in check) or expected['outcomes_accessed']:
                        raise ValueError('Frozen score receipt differs')
                    prediction_rows.append({'arm':arm,'seed':seed,'stage':stage,'cohort':name,'source_path':str(path),
                        'archive_path':'predictions/'+filename,'size_bytes':path.stat().st_size,**check,
                        'checkpoint_map_sha256':expected['checkpoint_map_sha256']})
    if complete and (len(checkpoint_rows)!=18 or len(prediction_rows)!=36 or sum(x['n'] for x in prediction_rows)!=144990):
        raise ValueError('Final 18 checkpoints / 36 files / 144990 rows not satisfied')
    recovery.put(d/'reports/final_predictions_frozen.json',{'UTC':recovery.utc(),'predictions':prediction_rows,
        'prediction_files':len(prediction_rows),'prediction_rows':sum(x['n'] for x in prediction_rows),
        'IM_outcomes_parsed':False,'IM_metrics_computed':False,'status':'FROZEN' if complete else 'INCOMPLETE'})
    # Only now may handoff read the original outcome identities (never model fitting).
    outcomes=[]
    for name,spec in (c['label_sources'].items() if complete else []):
        f=p.project_runs_dir/spec['path']
        if recovery.sha(f)!=spec['sha256']:raise ValueError('Original evaluation label bytes changed')
        keys=[]
        with f.open() as stream:
            for line in stream:
                row=json.loads(line);keys.append(row['source_id'])
                if row['label'] not in [0,1]:raise ValueError('Original outcome label is not binary')
        if keys!=cohorts[name]:raise ValueError('Original outcomes/identities row order differs')
        outcomes.append((f,'cohorts/'+name+'_outcomes.jsonl'))
    csv_write(final/'HLA_EXTENDED_TRAINING_CHECKPOINT_MANIFEST.csv',checkpoint_rows)
    if prediction_rows:csv_write(final/'HLA_EXTENDED_TRAINING_PREDICTION_MANIFEST.csv',prediction_rows)
    else:(final/'HLA_EXTENDED_TRAINING_PREDICTION_MANIFEST.csv').write_text('status\nNO_COMPLETED_PREDICTIONS\n')
    if epoch_rows:csv_write(final/'epoch_execution_audit.csv',epoch_rows)
    if tensor_rows:csv_write(final/'checkpoint_tensor_files.csv',tensor_rows)
    report='\n'.join(['# HLA拡張学習：保存修正後の復旧・最終監査','',
        f'状態: {"COMPLETE" if complete else "FAILED / INCOMPLETE"}。Recovery run: `{c["recovery_run_id"]}`。UTC: {recovery.utc()}。',
        f'新規fit完了: {len(execution["jobs"])}/8。A42は旧認証済みEL10/IM20を再利用し、再学習していない。',
        'Phase1: CPU sentinel、実authentic BigMHCのEL/IM保存→別process strict reload→全36 state hash一致、保存不完全・marker欠落・改ざん拒否、A42別process reloadにPASS。model update0、Phase1のmodel forward0。',
        f'最終checkpoint: {len(checkpoint_rows)} sets。予測: {len(prediction_rows)} files、{sum(x["n"] for x in prediction_rows)} rows。',
        '全成功時はA/W/L×seeds42/123/456×EL10/IM20の18 checkpoint、36予測・144,990行。IMPROVE7,788・Neo267の各元row key順を保持。各組の保存とstate hashを検証してからIM20へ進み、学習後推論は別process。',
        '科学的source/configは元commitとbyte同一。変更はpaths_config/require/save_completeの明示的IO binding、新run親作成、保存前hash永続化、検証済みmarker、実行管理・停止検査のみ。元rank、Teacher sidecar、データ、labels、native loss/optimizer/sampler/初期化/seed/予算を維持。',
        'W/Lのbatch順・skip・optimizer・RNGを同seed Aと照合し、失敗4fitの旧EL traceともscheduleを照合。旧失敗runの全ファイルsize/SHA256は開始時inventoryと一致。失敗receiptや旧checkpointを改変していない。',
        '元ラベルは36予測が凍結された後のhandoffでのみidentity整合性を確認し、元byteのままZIPへ同梱。IM AP/AUROC、paired delta、CI、bootstrap、calibration、IM結果による選択は一切実行していない。Mac L2へ引き継ぐ。',
        '巨大なモデルcheckpointはZIPに含めず、manifestのWSL実パスとfile-map SHA256、各tensor file hashはcheckpoint receiptに保持。ZIPは内部監査用のcohort・原ラベル・個別scoreを含む。外部upload、Mac自動転送、merge/push/Releaseなし。',
        '元の1 epoch pilotはそのまま保持。Figure2aの再構成やIM予測の改善/悪化の判断はMac評価後に行う。',
        '未知の失敗は自動retryせず、failure/aborted/unstartedをexecution_completed.jsonに記録。FAILEDのZIPは完成した実験結果ではない。', ''])
    (final/'HLA_EXTENDED_TRAINING_FINAL_REPORT.md').write_text(report)
    package=final/'package';package.mkdir()
    files=[(final/name,name) for name in ['HLA_EXTENDED_TRAINING_CHECKPOINT_MANIFEST.csv','HLA_EXTENDED_TRAINING_PREDICTION_MANIFEST.csv','HLA_EXTENDED_TRAINING_FINAL_REPORT.md']]
    if epoch_rows:files.append((final/'epoch_execution_audit.csv','epoch_execution_audit.csv'))
    if tensor_rows:files.append((final/'checkpoint_tensor_files.csv','checkpoint_tensor_files.csv'))
    files += [(d/f'cohorts/{name}_identities.jsonl',f'cohorts/{name}_identities.jsonl') for name in cohorts]+outcomes
    files += [(Path(row['source_path']),row['archive_path']) for row in prediction_rows]
    files += [(f,'receipts/'+str(f.relative_to(d/'reports'))) for f in sorted((d/'reports').rglob('*.json')) if not re.search(r'_(EL|IM)_epoch_\d{2}\.json$',f.name)]
    files += [(Path(row['checkpoint'])/recovery.MARKER,f'checkpoint_markers/{row["arm"]}_{row["seed"]}_{row["stage"]}.json') for row in checkpoint_rows if row['checkpoint']!='MISSING' and not row['reused']]
    files += [(f,'code/'+name) for name in recovery.source_proof()['scientific_hashes'] if (f:=p.repository_root/name).is_file()]
    files += [(p.repository_root/name,'code/'+name) for name in c['implementation_files']]
    copies=[]
    for source,relative in files:
        destination=package/relative;destination.parent.mkdir(parents=True,exist_ok=True)
        if destination.exists():raise ValueError('Duplicate export destination')
        shutil.copyfile(source,destination);checksum=recovery.sha(source)
        if recovery.sha(destination)!=checksum:raise ValueError('Final package byte copy differs')
        copies.append({'source_path':str(source),'archive_path':relative,'size_bytes':source.stat().st_size,'sha256':checksum})
    for row in prediction_rows:
        if recovery.sha(Path(row['source_path']))!=row['sha256'] or recovery.sha(package/row['archive_path'])!=row['sha256']:
            raise ValueError('Prediction changed during packaging')
    recovery.verify_old_run()
    csv_write(package/'source_copy_manifest.csv',copies)
    internal=sorted(f for f in package.rglob('*') if f.is_file())
    if any(f.suffix in {'.lyr','.pt','.safetensors'} for f in internal):raise ValueError('Model weights must not enter export')
    (package/'SHA256SUMS.txt').write_text(''.join(f'{recovery.sha(f)}  {f.relative_to(package)}\n' for f in internal))
    archive_path=final/'HLA_EXTENDED_TRAINING_FINAL_EXPORT.zip'
    with zipfile.ZipFile(archive_path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for f in sorted(package.rglob('*')):
            if f.is_file():archive.write(f,str(f.relative_to(package)))
    with zipfile.ZipFile(archive_path) as archive:
        if archive.testzip() is not None:raise ValueError('Final ZIP CRC failed')
        extracted=final/'verified_extraction';archive.extractall(extracted)
        for line in (extracted/'SHA256SUMS.txt').read_text().splitlines():
            expected,name=line.split('  ',1)
            if recovery.sha(extracted/name)!=expected:raise ValueError('Re-extracted member hash differs')
        member_count=len(archive.namelist())
    names=['HLA_EXTENDED_TRAINING_FINAL_EXPORT.zip','HLA_EXTENDED_TRAINING_FINAL_REPORT.md',
        'HLA_EXTENDED_TRAINING_CHECKPOINT_MANIFEST.csv','HLA_EXTENDED_TRAINING_PREDICTION_MANIFEST.csv']
    (final/'SHA256SUMS.txt').write_text(''.join(f'{recovery.sha(final/name)}  {name}\n' for name in names))
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ');delivered=None;errors=[]
    for folder,windows in windows_folders():
        if not folder.is_dir():continue
        target=folder/f'HLA_EXTENDED_TRAINING_RECOVERY_{"FINAL" if complete else "FAILED"}_{stamp}'
        try:
            target.mkdir()
            for name in names+['SHA256SUMS.txt']:
                with (final/name).open('rb') as src,(target/name).open('xb') as dst:shutil.copyfileobj(src,dst)
                if recovery.sha(target/name)!=recovery.sha(final/name):raise ValueError('Windows delivery differs')
            delivered=target;win_dir=str(PureWindowsPath(windows)/target.name);break
        except OSError as error:errors.append(repr(error))
    if delivered is None:raise RuntimeError('Windows Downloads/Desktop delivery failed: '+str(errors))
    with zipfile.ZipFile(delivered/archive_path.name) as archive:
        if archive.testzip() is not None:raise ValueError('Windows final ZIP CRC failed')
        for line in (package/'SHA256SUMS.txt').read_text().splitlines():
            expected,name=line.split('  ',1)
            if hashlib.sha256(archive.read(name)).hexdigest()!=expected:raise ValueError('Windows member hash differs')
    result={'status':'COMPLETE' if complete else 'FAILED_INCOMPLETE','UTC':recovery.utc(),
        'source_failed_run_id':c['source_run_id'],'recovery_run_id':c['recovery_run_id'],
        'Windows_directory':win_dir,'Windows_zip':str(PureWindowsPath(win_dir)/archive_path.name),
        'zip_size_bytes':archive_path.stat().st_size,'zip_sha256':recovery.sha(archive_path),'zip_files':member_count,
        'checkpoint_sets':len(checkpoint_rows),'prediction_files':len(prediction_rows),'prediction_rows':sum(x['n'] for x in prediction_rows),
        'CRC_all_members_reextraction_Windows_copy':'PASS','IM_metrics_computed':False,'old_failed_run_unchanged':True}
    result['Windows_native_verification']=windows_native_check(result['Windows_zip'],result['zip_size_bytes'],result['zip_sha256'],member_count)
    recovery.put(d/'reports/final_delivery_receipt.json',result)
    return result
