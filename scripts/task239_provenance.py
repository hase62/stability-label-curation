#!/usr/bin/env python3
"""Focused publication metadata reconciliation; no assay outcomes or IM labels."""
import json
import re
from stability_label_curation.paths import resolve_paths
from stability_label_curation.modern_model_preflight import digest

def main() -> None:
    paths=resolve_paths();data=paths.project_data_dir/'modern_models_task2_39'
    run=paths.project_runs_dir/'task-2_39-modern-el-stability-z790-preflight'
    # Preserve the focused Europe PMC response snapshots and their acquisition receipts.
    mapped={}
    unresolved=[]
    for i,doi in enumerate(['10.1038/s41467-022-29342-0','10.1172/JCI150535','10.1101/2024.03.17.585416']):
     p=data/f'publication_lookup_{i}.json'
     receipt=json.loads(p.with_name(p.name+'.provenance.json').read_text())
     if digest(p)!=receipt['sha256']:raise ValueError('Bibliography snapshot mismatch')
     result=json.loads(p.read_text())['resultList']['result']
     pmids={r['id'] for r in result if r.get('source')=='MED'}
     if len(pmids)==1:mapped[doi]=next(iter(pmids))
     else:unresolved.append(doi)
    summary={}
    for split in ['train','val','test']:
     rows=[json.loads(s) for s in (run/f's3_{split}_identity_index.jsonl').read_text().splitlines()]
     ids={re.sub(r'\.0$','',row['pmid']) for row in rows if row['pmid']}
     summary[split]={'total_source_rows':len(rows),'rows_with_PMID':sum(bool(row['pmid']) for row in rows),
                     'matches_to_resolved_IMPROVE_study_PMIDs':sorted(ids&set(mapped.values()))}
    result={'resolved_IMPROVE_study_PMIDs':mapped,'publications_without_resolved_PMID':unresolved,
            's3_available_metadata_comparison':summary,
            'S2_publication_and_donor_provenance':'not supplied in split CSVs',
            'donor_overlap':'unresolved; no matching donor identifiers in stability source indexes',
            'conclusion':'No matches among available S3 PMID annotations for two mapped studies. Incomplete S3 annotations, preprint linkage and absent S2 provenance prevent full study-independence verification. No ancestry-free claim.',
            'lookup_files':{f.name:digest(f) for f in data.glob('publication_lookup_*.json') if not f.name.endswith('.provenance.json')}}
    (run/'study_provenance_comparison.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print('Bibliographic metadata reconciliation complete; no outcome data')


if __name__ == '__main__':
    main()
