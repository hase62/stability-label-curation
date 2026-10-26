#!/usr/bin/env python3
"""Task 2.39 data/security audit. Never loads outcomes or predicts cohort rows."""
from __future__ import annotations
import ast
import csv
import hashlib
import json
import platform
import subprocess
import sys
from collections import Counter
from pathlib import Path

from stability_label_curation.paths import resolve_paths
from stability_label_curation.modern_model_preflight import (
    audit_identities, coverage, digest, full_hla_reference, load_identities,
    mix_allele, object_hash, read_identity_csv, verify_digest, verify_git_tree,
)


def write_json(path: Path, obj: object) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True, allow_nan=False) + '\n')


def jsonl(path: Path, rows: list) -> None:
    path.write_text(''.join(json.dumps(row, sort_keys=True, allow_nan=False) + '\n' for row in rows))


def git_blob(path: Path) -> str:
    data = path.read_bytes()
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def verify_tree(root: Path, tree: list[dict]) -> list[dict]:
    results = []
    for row in tree:
        if row['type'] != 'blob':
            continue
        path = root / row['path']
        if git_blob(path) != row['sha']:
            raise ValueError('Pinned Git blob mismatch: ' + row['path'])
        results.append({'path': row['path'], 'sha256': digest(path), 'git_blob': row['sha'],
                        'bytes': path.stat().st_size})
    return results


def main() -> None:
    paths = resolve_paths()
    root = paths.project_data_dir / 'modern_models_task2_39'
    run = paths.project_runs_dir / 'task-2_39-modern-el-stability-z790-preflight'
    run.mkdir(parents=True, exist_ok=True)
    cfg_path = Path(__file__).resolve().parents[1] / 'configs/modern_models_task239.json'
    cfg = json.loads(cfg_path.read_text())
    allowed_identity = (paths.project_runs_dir / cfg['cohort']['relative_path']).resolve()
    accessed: set[str] = set()
    def guard(event, arguments):
        if event != 'open' or not isinstance(arguments[0], (str, bytes)):
            return
        target = Path(arguments[0]).resolve()
        mode = arguments[1]
        if target.is_relative_to(paths.project_runs_dir):
            # All historical scientific reads except the exact identity-only
            # input are forbidden, including outcome and prediction files.
            if not target.is_relative_to(run) and target != allowed_identity:
                raise PermissionError('Task 2.39 forbids historical scientific artifact access')
            if mode is None or 'r' in mode:
                accessed.add(str(target.relative_to(paths.project_runs_dir)))
    sys.addaudithook(guard)
    for relative, sha in cfg['file_sha256'].items():
        verify_digest(root / relative, sha)
    mix_commit = json.loads((root / 'mix_tag.json').read_text())
    mix_tree = json.loads((root / 'mix_tree.json').read_text())
    source_commit = json.loads((root / 'spearmint_source.json').read_text())
    source_tree_metadata = json.loads((root / 'spearmint_tree.json').read_text())
    hf_metadata = json.loads((root / 'spearmint_hf.json').read_text())
    if (mix_commit['sha'] != cfg['mix']['revision'] or
            source_commit['sha'] != cfg['spearmint']['source_revision'] or
            hf_metadata['sha'] != cfg['spearmint']['revision']):
        raise ValueError('Upstream commit/tree/revision chain mismatch')
    verify_git_tree(mix_tree['tree'], mix_commit['commit']['tree']['sha'])
    verify_git_tree(source_tree_metadata['tree'], source_commit['commit']['tree']['sha'])
    verify_digest(root / 'mix_v3.0.tar.gz', cfg['mix']['archive_sha256'])
    verify_digest(root / 'ipd_imgt_3.64.0/hla_prot.fasta', cfg['ipd']['sha256'])
    mix = root / 'mix_release' / ('MixMHCpred-' + cfg['mix']['revision'])
    inventory = verify_tree(mix, mix_tree['tree'])
    write_json(run / 'mix_artifact_inventory.json', inventory)
    hf = root / 'spearmint_stage3' / cfg['spearmint']['revision']
    model_config = json.loads((hf / 'config.json').read_text())
    if (model_config['architectures'] != ['SpearmintForStabilityPrediction'] or
            model_config['assay_types'] != ['SPA', 'Purified_Fluor', 'Cellular_Fluor', 'Other'] or
            model_config['default_temp_c'] != 37.0):
        raise ValueError('Wrong model stage or assay configuration')
    hf_meta = json.loads((root / 'spearmint_hf_tree.json').read_text())
    for meta in hf_meta:
        p = hf / meta['path']
        if p.exists() and 'lfs' not in meta and git_blob(p) != meta['oid']:
            raise ValueError('HF source blob mismatch: ' + p.name)
    weight = hf / 'model.safetensors'
    verify_digest(weight, cfg['spearmint']['weights_sha256'])
    if weight.stat().st_size != cfg['spearmint']['weights_bytes'] or (hf / 'pytorch_model.bin').exists():
        raise ValueError('Unsafe/incomplete weight path')
    # Inspect AST without executing downloaded modules.
    source_review = {}
    for p in sorted(hf.glob('*.py')):
        tree = ast.parse(p.read_text())
        imports = sorted({n.module or '' for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} |
                         {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names})
        calls = sorted({ast.unparse(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)})
        source_review[p.name] = {'sha256': digest(p), 'imports': imports,
                                 'network_or_serialization_calls': [s for s in calls if any(
                                     t in s for t in ('load', 'exec', 'eval', 'system', 'subprocess'))]}
    write_json(run / 'source_review.json', source_review)
    rows = load_identities(paths.project_runs_dir / cfg['cohort']['relative_path'],
                           cfg['cohort']['sha256'], cfg['cohort']['rows'])
    keys = [r['source_id'] for r in rows]
    if object_hash(keys) != cfg['cohort']['ordered_keys_sha256']:
        raise ValueError('Frozen ordered identity hash mismatch')
    jsonl(run / 'IMPROVE_label_blind_identities.jsonl', rows)
    alleles = sorted({r['hla'] for r in rows})
    with (root / 'spearmint_source/refs/2field_hla_consensus_seqs.csv').open() as stream:
        consensus = {r['Allele']: r['Full Sequence'] for r in csv.DictReader(stream)}
    sequences = full_hla_reference(alleles, consensus, root / 'ipd_imgt_3.64.0/hla_prot.fasta')
    registry_path = cfg_path.parent / 'task239_hla_reference_checksums.json'
    verify_digest(registry_path, cfg['full_length_reference_registry_sha256'])
    frozen_sequences = json.loads(registry_path.read_text())
    if set(frozen_sequences) != set(alleles):
        raise ValueError('Frozen reference allele coverage mismatch')
    for allele, entry in sequences.items():
        for key in ('length', 'sha256', 'ipd_designation', 'ipd_accession'):
            if entry[key] != frozen_sequences[allele][key]:
                raise ValueError('Frozen full-length HLA reference mismatch')
    for value in sequences.values():
        value['ipd_release'] = cfg['ipd']['release']
        value['ipd_revision'] = cfg['ipd']['revision']
        value['ipd_tag'] = cfg['ipd']['tag']
        value['reference_file_sha256'] = cfg['ipd']['sha256']
    write_json(run / 'hla_full_length_references.json', sequences)
    with (mix / 'lib/alleles_list.txt').open() as f:
        direct_rows = {r['Allele']: r for r in csv.DictReader(f, delimiter='\t')}
    with (mix / 'lib/MHC_I_sequences.txt').open() as f:
        available = {r['Allele'] for r in csv.DictReader(f, delimiter='\t')}
    support = {a: {'eligible': mix_allele(a) in available,
                   'mode': 'direct_learned_reference' if mix_allele(a) in direct_rows else 'pan_allele',
                   'native_allele': mix_allele(a),
                   'nine_mer_motifs': int(direct_rows.get(mix_allele(a), {}).get('9', 0)),
                   'nearest_reference': 'see mix_nearest_reference.json (retain tied upstream choice)'}
               for a in alleles}
    write_json(run / 'mix_hla_support.json', support)
    cov = coverage(rows, sequences, support)
    jsonl(run / 'coverage.jsonl', cov)
    common = [r['source_id'] for r in cov if r['common_eligible']]
    write_json(run / 'common_coverage_row_keys.json', common)
    summaries = {}
    split_results = {}
    reference_support = {a: {} for a in alleles}
    source_tree = {r['path']: r for r in json.loads((root / 'spearmint_tree.json').read_text())['tree']}
    for stage, directory, expected in [('s2', 'binding_stability', 27031),
                                        ('s3', 'stage3_assay_conditioning', 10141)]:
        total = 0
        for split in ['train', 'val', 'test']:
            p = root / 'spearmint_source' / f'{stage}_{split}.csv'
            original = f'data/{directory}/{split}.csv'
            if git_blob(p) != source_tree[original]['sha']:
                raise ValueError('Source CSV blob mismatch')
            reference = read_identity_csv(p, stage, split)
            total += len(reference)
            name = f'{stage}_{split}'
            for allele in alleles:
                reference_support[allele][name] = sum(r['hla'] == allele for r in reference)
            jsonl(run / (name + '_identity_index.jsonl'), reference)
            audited = audit_identities(rows, reference)
            jsonl(run / (name + '_overlap.jsonl'), audited)
            split_results[name] = audited
            counts = Counter('undefined' if r['min_hamming'] is None else str(min(r['min_hamming'], 3)) for r in audited)
            same = Counter('undefined' if r['same_hla_min_hamming'] is None else str(min(r['same_hla_min_hamming'], 3)) for r in audited)
            summaries[name] = {'source_rows': len(reference), 'source_sha256': digest(p),
                'index_sha256': digest(run / (name + '_identity_index.jsonl')),
                'peptide_lengths': dict(Counter(len(r['peptide']) for r in reference)),
                'non_nine_reference_rows': sum(len(r['peptide']) != 9 for r in reference),
                'exact_pair_observations': sum(r['exact_pair'] for r in audited),
                'exact_peptide_observations': sum(r['exact_peptide'] for r in audited),
                'min_hamming_0_1_2_ge3': dict(counts),
                'same_hla_min_hamming_0_1_2_ge3': dict(same),
                'source_pmids': sorted({r['pmid'] for r in reference if r['pmid']}),
                'source_reference_iris': sorted({r['ref_iri'] for r in reference if r['ref_iri']})}
        if total != expected:
            raise ValueError('S2/S3 source inventory discrepancy')
    # Exposure is descriptive; it never changes common coverage.
    flags = []
    for i, row in enumerate(rows):
        flags.append({'source_id': row['source_id'], 'exposure': {
            s: {k: records[i][k] for k in ('exact_pair', 'exact_peptide', 'min_hamming', 'same_hla_min_hamming')}
            for s, records in split_results.items()},
            'unverified_ancestry': ['MINT_Stage1_BA', 'MINT_PPI', 'MixMHCpred_EL'],
            'upstream_IM_development_independence': 'not fully verifiable from training indexes'})
    jsonl(run / 'exposure_flags.jsonl', flags)
    write_json(run / 'overlap_summary.json', summaries)
    write_json(run / 'spearmint_source_hla_support.json', reference_support)
    summary = {'observations': len(rows), 'distinct_peptides': len({r['peptide'] for r in rows}),
        'distinct_pairs': len({(r['peptide'], r['hla']) for r in rows}),
        'distinct_hlas': len(alleles), 'patients': len({r['patient'] for r in rows}),
        'studies': len({r['study'] for r in rows}),
        'patient_peptide_components': len({r['patient_peptide_component'] for r in rows}),
        'A0201_components': len({r['patient_peptide_component'] for r in rows if r['hla']=='HLA-A*02:01'}),
        'by_hla': {a: {'observations': sum(r['hla']==a for r in rows),
                       'full_length': sequences[a]['eligible'], 'mix_mode': support[a]['mode'],
                       'stability_source_rows': reference_support[a]}
                   for a in alleles},
        'by_length': dict(Counter(r['peptide_length'] for r in rows)),
        'mix_eligible': sum(r['mix_eligible'] for r in cov),
        'spearmint_input_eligible': sum(r['spearmint_eligible'] for r in cov),
        'common_coverage': len(common), 'common_ordered_keys_sha256': object_hash(common),
        'unknown_ancestry_observations': len(rows),
        'exact_either_stage_training_pair': sum(any(split_results[s][i]['exact_pair'] for s in ['s2_train','s3_train']) for i in range(len(rows))),
        'exact_either_stage_training_peptide': sum(any(split_results[s][i]['exact_peptide'] for s in ['s2_train','s3_train']) for i in range(len(rows))),
        'within_two_substitutions_either_training_split': sum(any(
            split_results[s][i]['min_hamming'] is not None and split_results[s][i]['min_hamming'] <= 2
            for s in ['s2_train','s3_train']) for i in range(len(rows))),
        'exclusion_reasons': dict(Counter(reason for r in cov for reason in r['reason_codes'])),
        'outcome_columns_accessed': False, 'cohort_predictions_generated': False}
    write_json(run / 'coverage_summary.json', summary)
    write_json(run / 'scientific_file_access.json', {
        'historical_reads': sorted(p for p in accessed if not p.startswith(run.name + '/')),
        'allowed_identity_path': cfg['cohort']['relative_path'],
        'policy': 'deny every historical run file except exact authenticated identity-only input',
        'outcomes_accessed': False, 'historical_scores_accessed': False})
    receipt = {'task': cfg['task'], 'base_commit': cfg['base_commit'],
               'configuration_sha256': digest(cfg_path), 'source_identity_sha256': cfg['cohort']['sha256'],
               'ordered_row_key_hash': object_hash(keys),
               'artifacts': {p.name: digest(p) for p in sorted(run.iterdir()) if p.is_file() and p.name not in ('preflight_receipt.json',)},
               'platform': platform.platform(), 'python': sys.version,
               'command': 'PYTHONPATH=src python scripts/task239_preflight.py',
               'labels_read': False, 'benchmark_inference': False}
    write_json(run / 'preflight_receipt.json', receipt)
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
