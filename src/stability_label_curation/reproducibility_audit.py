"""Filesystem/provenance inventory only: never opens scientific table rows or ZIP members."""
from collections import Counter, defaultdict
import os
from pathlib import Path
import stat
import subprocess

from . import artifact_restore as restore
from . import netmhcstabpan_2016 as raw
from .paths import resolve_paths

PLAN = 'configs/artifact_reconstruction_plan.json'
RUN_ID = 'task-2_15-mac-reproducibility-audit'


def portable_record(item):
    """Historical absolute evidence is read as evidence, never used as a local path."""
    value=item['path'].replace('\\','/')
    for area in ('data','runs'):
        marker='/'+area+'/stability-label-curation/'
        if marker in value:
            return {'area':area,'relative_path':value.split(marker,1)[1],'sha256':item['sha256']}
    return {'area':'unresolved','relative_path':None,'sha256':item['sha256']}


def inspect(*, paths=None, plan_path=None):
    paths=paths or resolve_paths()
    plan=restore.read_json(plan_path or paths.repository_root/PLAN)
    artifacts=restore.load_registry(paths.repository_root/restore.REGISTRY)
    covered=defaultdict(list)
    for aid,a in artifacts.items():
        if a.get('external_publication') == 'pending': continue
        for member in restore.restoration_members(a):
            covered[(member['area'],member['relative_path'],member['sha256'])].append(aid)
    groups=[];files=[];links=[];physical=Counter();hashes={}
    planned={g['group_id']:g for g in plan['groups']}
    for area,root in [('data',paths.project_data_dir),('runs',paths.project_runs_dir)]:
        if not root.exists():continue
        for child in sorted(root.iterdir()):
            if child.name=='artifacts' and area=='data' or child.name==RUN_ID and area=='runs':continue
            if child.is_symlink():links.append({'area':area,'relative_path':child.name});continue
            gid=area+':'+child.name;group_files=[];group_links=[]
            for current,dirs,names in os.walk(child,followlinks=False) if child.is_dir() else [(str(root),[],[child.name])]:
                dirs.sort()
                for name in list(dirs):
                    path=Path(current)/name
                    if path.is_symlink():
                        group_links.append(str(path.relative_to(root)));dirs.remove(name)
                for name in sorted(names):
                    path=Path(current)/name;info=path.lstat();relative=str(path.relative_to(root))
                    if not stat.S_ISREG(info.st_mode):group_links.append(relative);continue
                    record={'area':area,'relative_path':relative,'size_bytes':info.st_size}
                    physical[area+'_files']+=1;physical[area+'_bytes']+=info.st_size
                    # Installed environments are platform-local trees, not immutable datasets.
                    if not (area=='data' and child.name=='environments'):
                        record['sha256']=raw.sha256_file(path);files.append(record)
                        hashes[(area,relative)]=record['sha256']
                        record['download_artifacts']=covered.get((area,relative,record['sha256']),[])
                    group_files.append(record)
            descriptor=planned.get(gid,{'group_id':gid,'classification':'GAP','reason':'Discovered group lacks a reviewed Git-managed recipe','priority':'historical_analysis','recipe':None})
            n_covered=sum(bool(f.get('download_artifacts')) for f in group_files)
            group={**descriptor,'local_file_count':len(group_files),'local_bytes':sum(f['size_bytes'] for f in group_files),
                   'symlink_or_special_count':len(group_links),'download_covered_file_count':n_covered,
                   'complete_exact_byte_directory_recovery':bool(group_files) and n_covered==len(group_files),
                   'registered_artifact_ids':sorted({aid for f in group_files for aid in f.get('download_artifacts',[])}),
                   'hash_coverage':'metadata_only_installed_environment' if child.name=='environments' and area=='data' else 'all_regular_files'}
            manifest=child/'manifest.json'
            if area=='runs' and manifest.is_file():
                doc=restore.read_json(manifest);cfg=doc['configuration']['file']
                config=None if cfg is None else {'repository_path':'configs/'+Path(cfg['path']).name,'sha256':cfg['sha256']}
                group['observed_provenance']={'producing_commit':doc['git']['commit_sha'],
                    'manifest_sha256':raw.sha256_file(manifest),'configuration':config,
                    'seed':doc['configuration']['random_seed'],
                    'inputs':[portable_record(i) for i in doc['data_provenance']['input_artifacts']],
                    'historical_absolute_paths_present':True,
                    'creation_argv_is_not_assumed_to_be_a_generation_recipe':True}
                if config:
                    command=['git','--no-optional-locks','show',doc['git']['commit_sha']+':'+config['repository_path']]
                    content=subprocess.run(command,cwd=paths.repository_root,capture_output=True)
                    group['observed_provenance']['recorded_config_found_at_producer_commit']=content.returncode==0
                    if content.returncode==0:
                        import hashlib
                        group['observed_provenance']['producer_config_hash_matches']=hashlib.sha256(content.stdout).hexdigest()==config['sha256']
            groups.append(group);links.extend({'area':area,'relative_path':s} for s in group_links)
    existing={g['group_id'] for g in groups}
    for g in plan['groups']:
        if g['group_id'] in existing:continue
        subset=[m for aid in g.get('artifact_ids',[]) if artifacts[aid].get('external_publication') != 'pending'
                for m in restore.restoration_members(artifacts[aid])]
        local=[m for m in subset if hashes.get((m['area'],m['relative_path']))==m['sha256']]
        groups.append({**g,'local_file_count':len(local),'local_bytes':sum(m['size_bytes'] for m in local),
            'local_availability':'verified_payload_files_present' if local else 'absent_on_Mac',
            'download_covered_file_count':len(local),
            'complete_exact_byte_directory_recovery':bool(subset) and len(subset)==len(local)})
    edges=[];integrity=[]
    for group in groups:
        for item in group.get('observed_provenance',{}).get('inputs',[]):
            key=(item['area'],item['relative_path'])
            state='missing_or_external' if key not in hashes else 'verified' if hashes[key]==item['sha256'] else 'mismatch'
            source=item['area']+':'+item['relative_path'].split('/')[0] if item['relative_path'] else 'unresolved'
            edges.append({'from':source,'to':group['group_id'],'input':item,'local_status':state})
            if state!='verified':integrity.append(edges[-1])
    for group in groups:
        derived=sorted({e['to'] for e in edges if e['from']==group['group_id']})
        declared=[c for aid in group.get('artifact_ids',[]) for c in artifacts[aid].get('downstream_consumers',[])]
        group['downstream_consumers']=sorted(set(derived+declared+group.get('downstream_consumers',[])))
    checkpoints=[f for f in files if '/checkpoints/' in f['relative_path']]
    by_hash=defaultdict(list)
    for f in files:by_hash[f['sha256']].append({'area':f['area'],'relative_path':f['relative_path'],'size_bytes':f['size_bytes']})
    return {'artifact_inventory.json':{'schema_version':1,'groups':groups,'physical_totals':dict(physical),
        'file_records':files,'symlink_or_special_metadata':links,'classification_counts':dict(Counter(g['classification'] for g in groups)),
        'group_count':len(groups),'hashed_regular_files':len(files),'scope':'Whole historical project roots; excludes this audit and controlled artifacts/cache workspace',
        'scientific_rows_parsed':0,'sealed_zip_members_opened':[]},
        'artifact_dependency_graph.json':{'edges':edges,'unavailable_or_mismatched_inputs':integrity,
            'downstream_consumers':{g['group_id']:sorted({e['to'] for e in edges if e['from']==g['group_id']}) for g in groups}},
        'checkpoint_recovery_coverage.json':{'local_checkpoint_files':checkpoints,
            'exact_download_covered_files':sum(bool(f.get('download_artifacts')) for f in checkpoints),
            'known_Windows_groups':[g for g in groups if g.get('Windows_verification_pending')],
            'restore_before_retrain':True,'new_checkpoint_uploads_performed':False},
        'reproducibility_gaps.json':{'gaps':[g for g in groups if g['classification']=='GAP'],
            'exact_backup_gaps':[{'group_id':g['group_id'],'reason':'No authenticated external copy covers the complete historical directory'}
                               for g in groups if not g.get('complete_exact_byte_directory_recovery')],
            'dependency_integrity_findings':integrity,'whole_project_unattended_recovery_established':False,
            'historical_lineage_warning':'Regenerated manifests contain new times, host paths and commits; old hash-pinned consumers may require explicit versioned provenance rebinding. Never edit old receipts or silently relax their hashes.'},
        'duplicate_content_inventory.json':{'groups':[{'sha256':h,'occurrences':v} for h,v in sorted(by_hash.items()) if len(v)>1],
                                            'files_removed_or_deduplicated':False}}


def verify_snapshot(report, paths=None):
    paths=paths or resolve_paths();count=0
    for item in report['file_records']:
        path=(paths.project_data_dir if item['area']=='data' else paths.project_runs_dir)/item['relative_path']
        if raw.sha256_file(path)!=item['sha256']:raise ValueError('Historical file changed during audit: '+item['relative_path'])
        count+=1
    return {'historical_file_hashes_preserved':count,'sealed_members_opened':[]}


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out')
    args=parser.parse_args();paths=resolve_paths();reports=inspect(paths=paths)
    if args.out:
        from .stability_teacher import _run
        directory,_=_run(args.out,paths)
        for name,doc in reports.items():raw.write_report(directory/'reports'/name,doc,paths=paths)
        print(raw.json_report({'run':str(directory),'groups':reports['artifact_inventory.json']['group_count'],
                              'classification_counts':reports['artifact_inventory.json']['classification_counts']}),end='')
    else: print(raw.json_report(reports),end='')
