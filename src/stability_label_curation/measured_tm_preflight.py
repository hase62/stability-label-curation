"""Task 2.35 data-only measured-Tm feasibility; no model or score access.

Identity/leakage freeze and outcome-support tabulation are separate entry points.
All dependencies are standard library except the existing pure sequence index.
"""
from __future__ import annotations

import ast
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, localcontext
import gzip
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import resource
import subprocess
import sys
import time
from typing import Any, Iterable
from urllib.request import urlopen
import xml.etree.ElementTree as ET
import zipfile

from .paths import StoragePaths, resolve_paths
from .sequence_hamming import NearestNineIndex, valid_ninemer
from .jappe_2020_sources import MAIN, DOCREL, _part, _relationships

RUN = 'task-2_35-measured-tm-eligibility-preflight'
BRANCH = 'task/2.35-measured-tm-eligibility-preflight'
BASE = '127d99c63c72c1511f751e0102ddd04536d1900e'
PROTOCOL = 'docs/MEASURED_TM_ELIGIBILITY_TASK2_35_PROTOCOL.md'
SOURCE_DIR = 'jappe2020_measured_tm_task2_35'
HLAS = ('HLA-A*02:01', 'HLA-B*07:02')
EXPECTED = {HLAS[0]: (6, 1094, 711, 'c15cdee1454aaeafc73574ebd456919e88a15acdc3d3e58cfabb0e44df6361aa'),
            HLAS[1]: (7, 1354, 782, '0b1b160265ae060a6fc353feb2290706c009628f9182ade778a9f2575bb619de')}
COHORTS = {'IMPROVE': (7788, 227, 36, 6576, '8118663ebf5c23de8f36a7a7c15aa0247a0609e04ade927657528d2986f6fee9'),
           'neoepitope': (267, 57, 46, 265, '9199c11b764c5e4913068125027c382d8229efc0020af743b37ed75bf6673bf7')}
SUPPORT = {'positive': 10, 'negative': 30, 'components': 5}


def utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha(path: Path) -> str:
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def assert_sha(path: Path, expected: str) -> None:
    if sha(path) != expected:
        raise ValueError('Input identity mismatch: '+str(path))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True, allow_nan=False)+'\n')


def write_rows(path: Path, values: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        for row in values:
            stream.write(json.dumps(row, sort_keys=True, allow_nan=False)+'\n')


def read_json(path: Path) -> dict:
    return json.loads(path.read_text())


def read_rows(path: Path) -> list[dict]:
    with path.open() as stream:
        return [json.loads(line) for line in stream]


def software(paths: StoragePaths) -> dict:
    return {n: sha(paths.repository_root/n) for n in [PROTOCOL,
        'src/stability_label_curation/measured_tm_preflight.py', 'src/stability_label_curation/sequence_hamming.py',
        'src/stability_label_curation/jappe_2020_sources.py', 'src/stability_label_curation/paths.py',
        'tests/test_measured_tm_preflight.py']}


def guard(paths: StoragePaths) -> str:
    git = lambda *args: subprocess.check_output(['git', *args], cwd=paths.repository_root, text=True).strip()
    if git('status', '--porcelain') or git('branch', '--show-current') != BRANCH or git('merge-base', BASE, 'HEAD') != BASE:
        raise ValueError('Clean committed authorized branch required')
    return git('rev-parse', 'HEAD')


def resources(start: float) -> dict:
    use = resource.getrusage(resource.RUSAGE_SELF)
    return {'elapsed_seconds': time.monotonic()-start, 'user_seconds': use.ru_utime, 'system_seconds': use.ru_stime,
            'peak_RSS_bytes': use.ru_maxrss*1024, 'completed_utc': utc(), 'platform': platform.platform(),
            'Python': platform.python_version(), 'GPU_used': False}


def acquire(paths: StoragePaths) -> dict:
    """Only the original article XML and its two exact journal attachments."""
    directory = paths.project_data_dir/SOURCE_DIR
    directory.mkdir(parents=True, exist_ok=True)
    article = directory/'PMC7726561.fullText.xml'
    if not article.exists():
        url = 'https://www.ebi.ac.uk/europepmc/webservices/rest/PMC7726561/fullTextXML'
        with urlopen(url, timeout=45) as response:
            data = response.read(2*1024*1024+1)
        if len(data)>2*1024*1024:
            raise ValueError('Unexpected article size')
        root = ET.fromstring(data)
        if not any(x.text == '10.1038/s41467-020-20166-4' for x in root.iter('article-id')):
            raise ValueError('Wrong publication')
        with article.open('xb') as stream:
            stream.write(data)
        write_json(directory/'article_xml_provenance.json', {'url': url, 'sha256': sha(article), 'retrieved_utc': utc()})
    provenance = read_json(directory/'article_xml_provenance.json')
    assert_sha(article, provenance['sha256'])
    root = ET.fromstring(article.read_bytes())
    outputs = {}
    for hla, (number, _, _, expected) in EXPECTED.items():
        filename = f'41467_2020_20166_MOESM{number}_ESM.xlsx'
        supplement = f'Supplementary Data {number-3}'
        if not any(x.attrib.get('{http://www.w3.org/1999/xlink}href') == filename and supplement in ' '.join(x.itertext()) for x in root.iter('media')):
            raise ValueError('Article supplement mapping differs')
        path = directory/filename
        if not path.exists():
            url = 'https://static-content.springer.com/esm/art%3A10.1038%2Fs41467-020-20166-4/MediaObjects/'+filename
            with urlopen(url, timeout=45) as response:
                data = response.read(1024*1024+1)
                headers, final = dict(response.headers), response.url
            if len(data)>1024*1024 or not data.startswith(b'PK') or hashlib.sha256(data).hexdigest()!=expected:
                raise ValueError('Unexpected original supplementary file')
            with path.open('xb') as stream:
                stream.write(data)
            write_json(directory/(filename+'.provenance.json'), {'requested_url': url, 'final_url': final,
                'file': filename, 'supplement': supplement, 'sha256': expected, 'bytes': len(data),
                'response_headers': headers, 'retrieved_utc': utc(), 'publication_DOI': '10.1038/s41467-020-20166-4'})
        assert_sha(path, expected)
        outputs[hla] = read_json(directory/(filename+'.provenance.json'))
    return {'article': provenance, 'files': outputs, 'files_source': 'journal attachments; article mapping via Europe PMC XML'}


def measurement_rows(path: Path, hla: str) -> tuple[list[dict], dict]:
    """Read A/B/C only. Column D's published affinity predictions are not decoded."""
    rows = []
    with zipfile.ZipFile(path) as archive:
        if sum(i.file_size for i in archive.infolist()) > 10*1024*1024:
            raise ValueError('Unexpected worksheet container size')
        book = ET.fromstring(archive.read('xl/workbook.xml'))
        relations = _relationships(archive, 'xl/_rels/workbook.xml.rels')
        strings = []
        for rel in relations.values():
            if rel['Type'] == DOCREL+'/sharedStrings':
                ss = ET.fromstring(archive.read(_part('xl/workbook.xml', rel['Target'])))
                strings = [''.join(x.text or '' for x in node.iter('{'+MAIN+'}t')) for node in ss]
        sheets = book.findall('{'+MAIN+'}sheets/{'+MAIN+'}sheet')
        if len(sheets) != 1:
            raise ValueError('Expected one original measurement worksheet')
        sheet = sheets[0]; part = _part('xl/workbook.xml', relations[sheet.get('{'+DOCREL+'}id')]['Target'])
        root = ET.fromstring(archive.read(part)); seen = set(); header = None
        physical_rows = list(root.find('{'+MAIN+'}sheetData'))
        for node in physical_rows:
            index = int(node.attrib['r'])
            if index in seen:
                raise ValueError('Repeated physical source row')
            seen.add(index); cells = {}; attributes = {}
            for cell in node:
                ref = cell.get('r', '')
                if ref not in {f'A{index}', f'B{index}', f'C{index}'}:
                    continue
                if cell.find('{'+MAIN+'}f') is not None:
                    raise ValueError('Source measurement formula cannot be silently evaluated')
                value = cell.find('{'+MAIN+'}v'); text = None if value is None else value.text
                kind = cell.get('t', 'n')
                if kind == 's':
                    text = strings[int(text)]
                elif kind == 'inlineStr':
                    text = ''.join(x.text or '' for x in cell.iter('{'+MAIN+'}t'))
                cells[ref[0]] = text; attributes[ref[0]] = dict(cell.attrib)
            if index == 1:
                header = cells
                if header != {'A':'Ligand', 'B':'Tm', 'C':'Transformed Tm'}:
                    raise ValueError('Original ligand/Tm schema differs')
                continue
            original = cells.get('A')
            if original is None or not original.strip():
                if cells.get('B') not in (None, ''):
                    raise ValueError('Tm without peptide identity')
                continue
            try:
                tm = Decimal(cells['B'])
            except (KeyError, InvalidOperation, TypeError) as error:
                raise ValueError('Peptide row lacks finite authentic Tm') from error
            if not tm.is_finite() or attributes['B'].get('t', 'n') != 'n':
                raise ValueError('Tm must be finite original numeric Celsius measurement')
            peptide = original.strip().upper()
            with localcontext() as context:
                context.prec = 50
                target = Decimal('.5')+(tm-Decimal(37))/Decimal(72)
            included = valid_ninemer(peptide)
            flags = []
            if not 37 <= tm <= 73:
                flags.append('outside_assay_temperature_interval_37_73')
            if included and not 0 <= target <= 1:
                raise ValueError('Nine-mer target outside valid BCE interval; no clipping permitted')
            rows.append({'source_id': f'Jappe2020:{path.name}:{sheet.attrib["name"]}:row:{index}',
                'source_file': path.name, 'worksheet': sheet.attrib['name'], 'worksheet_part': part,
                'source_row_index': index, 'peptide_cell': f'A{index}', 'Tm_cell': f'B{index}',
                'hla': hla, 'original_peptide': original, 'peptide': peptide, 'length': len(peptide),
                'Tm_C_original_numeric_text': str(tm), 'Tm_C': float(tm), 'target_decimal': str(target), 'target': float(target),
                'original_transformed_Tm_text': cells.get('C'), 'original_cell_attributes': attributes,
                'original_quality_flags': [], 'quality_flags': flags, 'canonical_ninemer': included,
                'inclusion_status': 'candidate' if included else 'excluded',
                'reason': 'canonical_ninemer_finite_measured_Tm' if included else 'length_or_noncanonical_sequence',
                'publication_DOI': '10.1038/s41467-020-20166-4', 'measurement': 'thermal_melting_temperature_Celsius'})
    keys = Counter((r['hla'],r['peptide']) for r in rows)
    contradictions = {k for k,n in keys.items() if n>1 and len({r['Tm_C_original_numeric_text'] for r in rows if (r['hla'],r['peptide'])==k})>1}
    if any(n>1 for n in keys.values()) or contradictions:
        raise ValueError('Unexpected duplicate/contradictory measured identity; stop for review')
    minimum = min(Decimal(r['Tm_C_original_numeric_text']) for r in rows)
    minimum_rows = [r for r in rows if Decimal(r['Tm_C_original_numeric_text']) == minimum]
    if len(minimum_rows)>1:
        for row in minimum_rows:
            row['quality_flags'].append('unresolved_repeated_minimum_Tm_not_assumed_censored')
    candidates = [r for r in rows if r['canonical_ninemer']]
    return rows, {'hla': hla, 'physical_rows_including_header': len(physical_rows), 'finite_measurement_rows': len(rows),
        'distinct_peptides': len(keys), 'canonical_ninemers': len(candidates), 'length_counts': dict(Counter(r['length'] for r in rows)),
        'duplicate_identities': sum(n-1 for n in keys.values()), 'contradictory_identities': len(contradictions),
        'repeated_minimum_all_lengths': len(minimum_rows), 'repeated_minimum_ninemers': sum(r['canonical_ninemer'] for r in minimum_rows),
        'Tm_C_range_all_lengths': [min(r['Tm_C'] for r in rows), max(r['Tm_C'] for r in rows)],
        'Tm_C_range_ninemers': [min(r['Tm_C'] for r in candidates), max(r['Tm_C'] for r in candidates)],
        'target_range_ninemers': [min(r['target'] for r in candidates), max(r['target'] for r in candidates)],
        'original_explicit_QC_flag_column_present': False, 'published_affinity_column_used': False,
        'targets_in_BCE_interval': all(0<=r['target']<=1 for r in candidates)}


def parent_manifest(paths: StoragePaths) -> tuple[Path, dict]:
    directory = paths.project_runs_dir/'task-2_32-el-only-zero-shot-im'
    receipt = read_json(paths.repository_root/'configs/bigmhc_el_only_zero_shot_im_task2_32.completed.json')
    path = directory/'reports/output_manifest.json'; assert_sha(path, receipt['sha256'])
    return directory, read_json(path)['files_sha256']


def cohort_identities(paths: StoragePaths) -> tuple[dict, dict]:
    directory, manifest = parent_manifest(paths)
    groups = {}; evidence = {}
    for name, (count, _, hla_count, unique, ordered) in COHORTS.items():
        rel = f'cohorts/{name}_identities.jsonl'; assert_sha(directory/rel, manifest[rel]); rows = read_rows(directory/rel)
        if (len(rows)!=count or len({r['source_id'] for r in rows})!=count or digest([r['source_id'] for r in rows])!=ordered
                or len({r['hla'] for r in rows})!=hla_count or len({r['peptide'] for r in rows})!=unique
                or any(not valid_ninemer(r['peptide']) or 'label' in r or 'scores' in r for r in rows)):
            raise ValueError('Original frozen cohort row order/identity/length differs')
        groups[name]=rows
        evidence[name]={'relative_path':str((directory/rel).relative_to(paths.project_runs_dir)), 'sha256':manifest[rel],
            'ordered_source_id_sha256':ordered,'observations':count,'unique_peptides':unique,'HLAs':hla_count,
            'canonical_ninemers':count,'length_incompatible_observations':0,'regenerated':False}
    return groups, evidence


def EL_references(paths: StoragePaths, query: list[dict]) -> tuple[dict, dict, dict, set, dict]:
    cfg = read_json(paths.repository_root/'configs/bigmhc_fully_trained_auxiliary_task2_24.json')
    base = paths.project_runs_dir/cfg['baseline']['run_id']
    preflight = base/'reports/preflight.json'; assert_sha(preflight,cfg['baseline']['reports']['preflight.json'])
    meta = read_json(preflight); manifest = paths.project_runs_dir/cfg['inputs']['EL_split']['relative_path']
    assert_sha(manifest, meta['immutable_artifacts']['processed/el_split_manifest_v1.csv.gz'])
    source = paths.project_runs_dir/cfg['inputs']['EL']['relative_path']; assert_sha(source,cfg['inputs']['EL']['sha256'])
    refs = {part:defaultdict(set) for part in ('train','validation')}; positives=set(); negatives={h:{} for h in HLAS}
    counts=Counter(); classes=defaultdict(Counter); negative_counts={h:Counter() for h in HLAS}; order=hashlib.sha256()
    with gzip.open(manifest,'rt',newline='') as stream,source.open(newline='') as original:
        for ordinal,(row,raw) in enumerate(zip(csv.DictReader(stream),csv.DictReader(original),strict=True),1):
            part,pep,hla,label=row['partition'],row['peptide'].strip().upper(),row['HLA'],int(row['original_label'])
            if (int(row['original_prepared_row_index'])!=ordinal or (pep,hla,label)!=(raw['pep'].strip().upper(),raw['mhc'],int(raw['tgt']))
                    or not valid_ninemer(pep) or part not in ('train','validation','excluded') or label not in (0,1)):
                raise ValueError('Authentic EL source partition/identity/label join differs')
            counts[part]+=1; classes[part][label]+=1
            order.update((row['source_row_id']+'\n').encode())
            if label:
                positives.add(pep)
            if part in refs:
                refs[part][hla].add(pep)
            if part=='train' and not label and hla in HLAS:
                negative_counts[hla][pep]+=1
                negatives[hla].setdefault(pep,{'source_id':row['source_row_id'],'source_row_sha256':row['source_row_sha256'],
                    'source_file':row['source_file'],'source_row_index':int(row['row_index']), 'source_line_number':int(row['source_line_number']),
                    'original_prepared_row_index':ordinal,'peptide':pep,'hla':hla,'original_EL_label':0})
    if counts != {'train':1308196,'validation':145371,'excluded':11} or classes['train']!={0:1245143,1:63053} or classes['validation']!={0:138365,1:7006}:
        raise ValueError('Frozen authentic EL census differs')
    evidence={'manifest_sha256':sha(manifest),'source_EL_sha256':sha(source),'manifest':str(manifest.relative_to(paths.project_runs_dir)),
        'original_source':str(source.relative_to(paths.project_runs_dir)),'ordered_source_row_digest':order.hexdigest(),
        'partition_counts':dict(counts),'classes':dict(classes),'all_peptides_canonical_ninemers':True,
        'partitions':{part:{'unique_peptides':len(set().union(*by_hla.values())),'unique_pairs':sum(map(len,by_hla.values())),
                            'HLAs':len(by_hla)} for part,by_hla in refs.items()},
        'baseline_EL_checkpoint':'task-2_23-el-multiepoch-baseline/checkpoints/EL_epoch_10',
        'baseline_EL_checkpoint_map_SHA256':'d8e3d7d3ac5d08d7f420e00b8032fa875b8b6fec1cd9da6b36d35bca0bec04d1',
        'checkpoint_loaded_or_scored':False}
    return refs, evidence, negatives, positives, negative_counts


def distance_bin(distance: int | None) -> str:
    return 'undefined_no_compatible_reference' if distance is None else str(distance) if distance<3 else '>=3'


def sequence_excluded(peptide: str, index: NearestNineIndex) -> bool:
    minimum,_=index.nearest(peptide)
    return minimum is not None and minimum<=2


def overlaps(query: list[dict], references: dict[str,set[str]]) -> tuple[list[dict],dict]:
    """Both allele-agnostic and same-HLA exact minimum Hamming with witnesses."""
    global_set=set().union(*references.values()) if references else set()
    agnostic=NearestNineIndex(global_set)
    indices={h:NearestNineIndex(references.get(h,set())) for h in HLAS}
    rows=[]
    for row in query:
        pep,hla=row['peptide'],row['hla']; d,w=agnostic.nearest(pep); hd,hw=indices[hla].nearest(pep)
        rows.append({'source_id':row['source_id'],'peptide':pep,'hla':hla,'exact_pair':pep in references.get(hla,set()),
            'exact_peptide':pep in global_set,'minimum_Hamming':d,'nearest_peptide':w,
            'minimum_same_HLA_Hamming':hd,'nearest_same_HLA_peptide':hw,'length_compatible':True})
    def summarize(part):
        return {'observations':len(part),'exact_pair':sum(r['exact_pair'] for r in part),'exact_peptide':sum(r['exact_peptide'] for r in part),
            'allele_agnostic_distance':dict(Counter(distance_bin(r['minimum_Hamming']) for r in part)),
            'same_HLA_distance':dict(Counter(distance_bin(r['minimum_same_HLA_Hamming']) for r in part)),
            'full_allele_agnostic_distance':dict(Counter(r['minimum_Hamming'] for r in part)),
            'full_same_HLA_distance':dict(Counter(r['minimum_same_HLA_Hamming'] for r in part))}
    return rows,{'total':summarize(rows),'per_HLA':{h:summarize([r for r in rows if r['hla']==h]) for h in HLAS},
        'reference_unique_peptides':len(global_set),'reference_unique_pairs':sum(map(len,references.values())),
        'length_compatibility':'All queries and references are canonical exact nine-mers; other source lengths excluded before distance computation.',
        'index_evidence':{'allele_agnostic':agnostic.evidence(),'per_HLA':{h:i.evidence() for h,i in indices.items()}}}


def group_peptides(rows: list[dict]) -> dict[str,set[str]]:
    groups=defaultdict(set)
    for row in rows:
        groups[row['hla']].add(row['peptide'])
    return groups


def source_structure(paths: StoragePaths) -> dict:
    cfg=read_json(paths.repository_root/'configs/bigmhc_el_multiepoch_task2_23.json')
    spec=cfg['inputs']['source_bigmhc']; path=paths.project_data_dir/spec['relative_path'];assert_sha(path,spec['sha256'])
    text=path.read_text();tree=ast.parse(text)
    condenser=next(n for outer in tree.body if isinstance(outer,ast.ClassDef) and outer.name=='BigMHC'
                   for n in outer.body if isinstance(n,ast.ClassDef) and n.name=='Condenser')
    forward=next(n for n in condenser.body if isinstance(n,ast.FunctionDef) and n.name=='forward')
    segment=ast.get_source_segment(text,forward)
    if 'self.out.weight * attention' not in segment or 'mhc.bool()' not in segment or 'self.out.bias' not in segment or 'self.out = torch.nn.Linear(mhclen, 1)' not in text:
        raise ValueError('Unexpected authentic final-output semantics')
    return {'source_file':spec,'source_SHA256':sha(path),'validation':'static text/AST only; no import/model construction',
        'trainable_keys':['condenser.out.weight','condenser.out.bias'],'trainable_values':415,
        'backbone_width':414,'out_forward_module_called':False,'HLA_boolean_mask_in_native_logit':True,
        'model_eval_preserves_autograd_for_last_weight_bias':True,'existing_four_parameter_IM_TRANSFER_must_not_be_used':True,
        'technical_conditions':['Keep whole model eval; freeze every parameter except exact two keys.',
            'Native forward reads out.weight directly, so an out.forward hook will not extract features.',
            'Do not wrap complete forward in no_grad when optimizing output weights.',
            'Ordinary batch64 including all-negative batches; no native positive-anchor sampling/skip mask.',
            'Identical fixed decoys, source ordering, target multiset, initialization and 20-pass budgets for D/P/T.',
            'Measured Celsius Tm target is not a kinetic-half-life target or experimental decoy instability.'],
        'optimizer':'AdamW','learning_rate':.001,'batch_size':64,'passes':20,'cohort_order_seed':235001,
        'within_HLA_target_permutation_seed':235002,'main_contrast':'T-P','practical_contrast':'T-A','descriptive_contrast':'T-D'}


def identities(paths: StoragePaths) -> dict:
    commit=guard(paths); directory=paths.project_runs_dir/RUN;directory.mkdir(parents=True,exist_ok=False);start=time.monotonic()
    write_json(directory/'reports/identity_stage_started.json',{'utc':utc(),'commit':commit,'software':software(paths),'IM_labels_loaded':False})
    provenance=acquire(paths);write_json(directory/'reports/source_provenance.json',provenance)
    all_rows=[]; source_summary={}
    for hla,(n,expected,expected_nine,_) in EXPECTED.items():
        rows,summary=measurement_rows(paths.project_data_dir/SOURCE_DIR/f'41467_2020_20166_MOESM{n}_ESM.xlsx',hla)
        if summary['distinct_peptides']!=expected or summary['canonical_ninemers']!=expected_nine:
            raise ValueError('Original source count discrepancy; stop, no approximate substitute')
        all_rows.extend(rows);source_summary[hla]=summary
    tm=[r for r in all_rows if r['canonical_ninemer']]
    if sum('unresolved_repeated_minimum_Tm_not_assumed_censored' in r['quality_flags'] for r in tm)!=5:
        raise ValueError('Unexpected repeated-minimum nine-mer flags; stop')
    write_rows(directory/'manifests/source_measurements_all_lengths.jsonl',all_rows)
    write_rows(directory/'manifests/measured_Tm_candidates.jsonl',tm)
    write_json(directory/'reports/source_counts.json',source_summary)
    print('source reproduced: 1094/1354 finite distinct peptides; 711/782 canonical nine-mers',flush=True)
    cohorts,evidence=cohort_identities(paths);write_json(directory/'reports/external_cohort_identity_references.json',evidence)
    refs,el_evidence,negatives,positive_peptides,negative_counts=EL_references(paths,tm)
    write_json(directory/'reports/EL_identity_references.json',el_evidence)
    print('authentic EL manifest aligned; no IM outcomes accessed',flush=True)
    comparison={}; overlap_rows={}
    for name,ref in [('EL_train',refs['train']),('EL_validation',refs['validation'])]+[(n,group_peptides(r)) for n,r in cohorts.items()]:
        rows,summary=overlaps(tm,ref);comparison[name]=summary;overlap_rows[name]=rows
        write_rows(directory/f'overlaps/Tm_to_{name}.jsonl',rows)
        print('distance witnesses frozen:',name,flush=True)
    write_json(directory/'reports/overlap_summary.json',comparison)
    external_peptides={r['peptide'] for rows in cohorts.values() for r in rows}; im_index=NearestNineIndex(external_peptides)
    eligible=[];policy_tm=[]
    for i,row in enumerate(tm):
        reasons=[n for n in cohorts if overlap_rows[n][i]['minimum_Hamming']<=2]
        kept=not reasons
        entry={**row,'preferred_training_eligible':kept,'exclusion_reasons':reasons,'exclusion_policy':'protect_both_frozen_IM_cohorts_distance_le_2_any_HLA'}
        policy_tm.append(entry)
        if kept:eligible.append(entry)
    write_rows(directory/'manifests/measured_Tm_preferred_panel.jsonl',policy_tm)
    tm_index=NearestNineIndex(r['peptide'] for r in tm);alternative={}
    for name,rows in cohorts.items():
        mask=[]
        for r in rows:
            dist,w=tm_index.nearest(r['peptide']);mask.append({'source_id':r['source_id'],'hla':r['hla'],'peptide':r['peptide'],
                'alternative_evaluation_retained':dist>2,'minimum_Hamming_to_full_Tm':dist,'nearest_Tm_peptide':w})
        write_rows(directory/f'policy_alternative/{name}_identity_only_mask.jsonl',mask)
        alternative[name]={'original':len(rows),'retained':sum(r['alternative_evaluation_retained'] for r in mask),
            'excluded':sum(not r['alternative_evaluation_retained'] for r in mask),
            'per_HLA':{h:{'original':sum(r['hla']==h for r in rows),'retained':sum(r['hla']==h and r['alternative_evaluation_retained'] for r in mask)} for h in HLAS}}
    policy={'preferred':'protect_all_frozen_external_IM_observations; remove_Tm_distance_le_2_any_HLA',
        'chosen_before_current_IM_outcome_counts':True,'IM_outcomes_or_scores_used':False,'original_Tm_candidates':len(tm),
        'preferred_Tm_retained':len(eligible),'preferred_Tm_excluded':len(tm)-len(eligible),
        'preferred_external_retained':{n:len(r) for n,r in cohorts.items()},'alternative_Tm_retained':len(tm),
        'alternative_external_attrition':alternative,
        'per_HLA_Tm':{h:{'original':sum(r['hla']==h for r in tm),'retained':sum(r['hla']==h for r in eligible),
                          'flagged_retained':sum(r['hla']==h and bool(r['quality_flags']) for r in eligible)} for h in HLAS}}
    write_json(directory/'reports/leakage_policy_comparison_label_blind.json',policy)
    print('preferred Tm panel frozen:',len(eligible),'; external observations unchanged',flush=True)
    measured_peptides={r['peptide'] for r in all_rows};decoy_summary={}
    for hla in HLAS:
        pool=[]
        # Exact distance to each benchmark, both same-HLA and allele-agnostic, no labels.
        for pep,row in sorted(negatives[hla].items()):
            pool.append({**row,'original_observation_multiplicity':negative_counts[hla][pep],
                'conflict_measured_Tm_peptide':pep in measured_peptides,'conflict_authenticated_EL_positive_peptide':pep in positive_peptides})
        distances={};decoy_dist_summary={}
        for name,rows in cohorts.items():
            distances[name],decoy_dist_summary[name]=overlaps(pool,group_peptides(rows))
        available=[];reasons_count=Counter()
        for i,row in enumerate(pool):
            reasons=[]
            if row['conflict_measured_Tm_peptide']:reasons.append('published_measured_Tm_ligand_exact_sequence')
            if row['conflict_authenticated_EL_positive_peptide']:reasons.append('authenticated_EL_positive_exact_sequence')
            for name in cohorts:
                detail=distances[name][i];row[name+'_distance']=detail
                if detail['minimum_Hamming']<=2:reasons.append(name+'_distance_le_2')
            row['adaptation_decoy_eligible']=not reasons;row['exclusion_reasons']=reasons
            reasons_count.update(reasons)
            if not reasons:available.append(row)
        count=16*sum(r['hla']==hla for r in eligible)
        available.sort(key=lambda r:(hashlib.sha256(('Task2.35-decoy-v1|'+r['hla']+'|'+r['peptide']).encode()).hexdigest(),r['hla'],r['peptide']))
        chosen=available[:count] if len(available)>=count else []
        name=hla.replace('HLA-','').replace('*','').replace(':','')
        write_rows(directory/f'decoys/{name}_candidate_identities.jsonl',pool)
        write_rows(directory/f'decoys/{name}_provisional_selected_identities.jsonl',chosen)
        decoy_summary[hla]={'original_negative_observations':sum(negative_counts[hla].values()),'unique_negative_pairs':len(pool),
            'duplicate_observation_excess':sum(n-1 for n in negative_counts[hla].values()),
            'duplicated_identities':sum(n>1 for n in negative_counts[hla].values()),'reason_counts_nonexclusive':dict(reasons_count),
            'available_after_label_blind_exclusions':len(available),'proposed_negative_count':count,'provisionally_selected':len(chosen),
            'sufficient_for_fixed_16_to_1':len(available)>=count,'distance_and_exact_overlap':decoy_dist_summary,
            'experimentally_measured_Tm_assigned':False,'selection_key':'SHA256(Task2.35-decoy-v1|HLA|PEPTIDE)',
            'D_P_T_same_negative_identity_digest':digest([(r['hla'],r['peptide']) for r in chosen])}
        print('decoy identities frozen:',hla,len(available),'available;',len(chosen),'provisional selected',flush=True)
    write_json(directory/'reports/decoy_feasibility.json',decoy_summary)
    write_json(directory/'reports/structural_feasibility.json',source_structure(paths))
    # No labels or score files were consumed; these hashes seal all outcome-independent decisions.
    hashes={str(f.relative_to(directory)):sha(f) for f in sorted(directory.rglob('*')) if f.is_file()}
    result={'status':'IDENTITIES_AND_LEAKAGE_FROZEN','utc':utc(),'software':software(paths),'protocol_commit':commit,
        'immutable_identity_artifact_hashes':hashes,'IM_labels_loaded':False,'model_scores_loaded':False,
        'support_gate':SUPPORT,'preferred_policy_immutable':True,'resources':resources(start)}
    write_json(directory/'reports/identities_frozen.json',result)
    return {'status':result['status'],'Tm_counts':source_summary,'label_blind_policy':policy,'resources':result['resources']}


def align_outcomes(rows: list[dict], outcomes: list[dict]) -> list[dict]:
    if len(rows)!=len(outcomes) or any(r['source_id']!=o['source_id'] or type(o.get('label')) is not int or o['label'] not in (0,1) for r,o in zip(rows,outcomes,strict=True)):
        raise ValueError('Frozen source outcome association differs')
    return [{**r,'label':o['label']} for r,o in zip(rows,outcomes,strict=True)]


def support_counts(rows: list[dict], component: str) -> dict:
    n=len(rows);positive=sum(r['label'] for r in rows);components=Counter(r[component] for r in rows)
    return {'n':n,'canonical_ninemers':sum(valid_ninemer(r['peptide']) for r in rows),'positive':positive,'negative':n-positive,
        'prevalence':positive/n if n else None,'unique_peptides':len({r['peptide'] for r in rows}),
        'patients':len({(r['study_DOI'],r['patient']) for r in rows if r['patient']}) or None,
        'studies':len({r['study_DOI'] for r in rows if r['study_DOI']}) or None,'dependence_components':len(components),
        'positive_bearing_components':len({r[component] for r in rows if r['label']}),
        'largest_component_observations':max(components.values(),default=0),
        'passes_minimum_support':positive>=SUPPORT['positive'] and n-positive>=SUPPORT['negative'] and len(components)>=SUPPORT['components'],
        'known_patient_peptide_dependence_available':component!='cluster_id',
        'complete_assay_level_independence_verified':False}


def support(paths: StoragePaths) -> dict:
    commit=guard(paths);directory=paths.project_runs_dir/RUN;start=time.monotonic()
    freeze=read_json(directory/'reports/identities_frozen.json')
    if freeze['software']!=software(paths) or freeze['support_gate']!=SUPPORT or freeze['IM_labels_loaded']:
        raise ValueError('Identity-only decisions or frozen support gates changed')
    for name,expected in freeze['immutable_identity_artifact_hashes'].items():
        assert_sha(directory/name,expected)
    write_json(directory/'reports/support_stage_started.json',{'utc':utc(),'commit':commit,'identity_freeze_sha256':sha(directory/'reports/identities_frozen.json'),
        'no_training_inference_performance':True,'software':software(paths)})
    cohort_rows,_=cohort_identities(paths);parent,manifest=parent_manifest(paths);results={}
    for name,rows in cohort_rows.items():
        rel=f'cohorts/{name}_outcomes.jsonl';assert_sha(parent/rel,manifest[rel])
        joined=align_outcomes(rows,read_rows(parent/rel))
        if sum(r['label'] for r in joined)!=COHORTS[name][1]:
            raise ValueError('Original external class balance differs')
        mask=read_rows(directory/f'policy_alternative/{name}_identity_only_mask.jsonl')
        if [r['source_id'] for r in mask]!=[r['source_id'] for r in joined]:
            raise ValueError('Fixed alternative row order differs')
        keep={r['source_id'] for r in mask if r['alternative_evaluation_retained']}
        field='patient_peptide_component' if name=='IMPROVE' else 'cluster_id'
        results[name]={'original_full_cohort':support_counts(joined,field),'preferred_full_cohort':support_counts(joined,field),
            'alternative_full_cohort':support_counts([r for r in joined if r['source_id'] in keep],field),
            'per_HLA':{h:{'preferred_unchanged':support_counts([r for r in joined if r['hla']==h],field),
                'alternative_excluded_near_Tm':support_counts([r for r in joined if r['hla']==h and r['source_id'] in keep],field)} for h in HLAS},
            'components_preserved_from_original_cohort_not_recomputed':True,'outcomes_sha256':manifest[rel]}
        results[name]['intended_two_HLA_primary_support']=all(results[name]['per_HLA'][h]['preferred_unchanged']['passes_minimum_support'] for h in HLAS)
        write_rows(directory/f'support/{name}_supported_HLA_observations.jsonl',[
            {'source_id':r['source_id'],'hla':r['hla'],'peptide':r['peptide'],'label':r['label'],'patient':r['patient'],'study_DOI':r['study_DOI'],
             'frozen_dependence_component':r[field],'preferred_retained':True,'alternative_retained':r['source_id'] in keep} for r in joined if r['hla'] in HLAS])
    decoys=read_json(directory/'reports/decoy_feasibility.json');policy=read_json(directory/'reports/leakage_policy_comparison_label_blind.json')
    go=results['IMPROVE']['intended_two_HLA_primary_support'] and all(v['sufficient_for_fixed_16_to_1'] for v in decoys.values()) and policy['preferred_Tm_retained']>0
    write_json(directory/'reports/HLA_support_and_policy_class_counts.json',results)
    verdict={'decision':'GO' if go else 'NO-GO','intended_primary':'equal-weight A0201/B0702 within-HLA AP macro on original IMPROVE >=3',
        'support_gate':SUPPORT,'cohorts':results,'preferred_policy_unchanged_after_outcome_tabulation':True,
        'training_inference_or_IM_performance_executed':False,'models_or_model_scores_loaded':False,
        'GPU_used':False,'single_HLA_not_promoted_to_primary':True,'resources':resources(start)}
    write_json(directory/'reports/feasibility_decision.json',verdict)
    return verdict


def main() -> None:
    if len(sys.argv)!=2 or sys.argv[1] not in ('acquire','identities','support'):
        raise SystemExit('acquire | identities | support')
    result=globals()[sys.argv[1]](resolve_paths())
    print(json.dumps(result,sort_keys=True,allow_nan=False),flush=True)


if __name__=='__main__':
    main()
