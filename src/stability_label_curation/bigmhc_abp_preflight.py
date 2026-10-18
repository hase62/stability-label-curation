"""Read-only full-cohort A/B/P integration gate; no model or optimizer creation."""
from collections import Counter
from copy import deepcopy
import csv
import hashlib
import io
from itertools import zip_longest
from pathlib import Path
import time

from . import bigmhc_baseline_runner as runner
from . import el_stability_loss_adapter as weights
from .paths import StoragePaths, resolve_paths


def planned_configurations(base: dict) -> dict[str, dict]:
    """Resolve scientific settings now; fresh A's runtime reference exists later.

    B/P remain explicitly unauthorized until the launcher supplies the verified
    fresh A receipt. This is the existing protocol gate, not a fabricated hash.
    """
    from .bigmhc_abp_experiment import arm_configuration, RUN_ID
    result = {'A': arm_configuration(base, 'A')}
    pending = {'area': 'runs', 'relative_path': f'{RUN_ID}/A/reports/matched_state.json', 'sha256': None}
    low = base['loss_adapter']['protocol_version'] == weights.LOW_PROTOCOL
    if low:
        pending = base['baseline_reuse']['reference']
    for mode in (('L', 'P') if low else ('B', 'P')):
        c = deepcopy(base)
        c['loss_adapter']['training_authorized'] = False
        result[mode] = arm_configuration(c, mode, pending)
    if len({weights.matched_config_identity(c) for c in result.values()}) != 1:
        raise ValueError('A/B/P scientific configurations differ')
    return result


def historical_prerequisites(paths: StoragePaths, config: dict) -> dict:
    if config['loss_adapter']['protocol_version'] == weights.LOW_PROTOCOL:
        from .bigmhc_baseline_compatibility import baseline_evidence
        return baseline_evidence(config, paths)
    from .bigmhc_abp_experiment import HISTORICAL, COMMON_FIELDS, training_report, prediction_rows
    directory = paths.project_runs_dir / HISTORICAL
    # Historical evidence belongs to its recorded commit, not today's checkout.
    manifest = runner.runs.validate_manifest(runner.readers._json(directory / 'manifest.json'))
    receipt = runner.readers._json(directory / 'reports/execution_verification.json')
    if receipt['code_commit'] != manifest['git']['commit_sha']:
        raise ValueError('Historical receipt/manifest code differs')
    for relative, expected in receipt['outputs'].items():
        runner.adapter.pilot.registry._relative(relative)
        if runner.raw.sha256_file(directory / relative) != expected:
            raise ValueError('Historical output identity mismatch: ' + relative)
    old = runner.readers._json(directory / 'reports/training_configuration.json')
    if any(old[k] != config[k] for k in COMMON_FIELDS) or any(
            config['inputs'][k] != v for k, v in old['inputs'].items()):
        raise ValueError('Historical scientific configuration/input mismatch')
    initial = runner.readers._json(directory / 'reports/initial_el_state_identity.json')
    lineage = runner.readers._json(directory / 'reports/checkpoint_lineage.json')
    runner.verify_parent(directory / 'checkpoints/el', directory / 'checkpoints/el/im', lineage)
    summary = training_report(directory)
    if len(initial) != 36 or summary['architecture']['state_tensors'] != 36:
        raise ValueError('Historical architecture/initial identity mismatch')
    for stage, steps in (('EL', 70069), ('IM', 214)):
        item = summary[stage]
        required = ('batches', 'optimizer_class_exposures', 'sampled_class_exposures',
                    'optimizer_defaults', 'updated_parameters', 'skipped_batch_log', 'sampling')
        if item['optimization_steps'] != steps or len(item['step_log']) != steps or any(k not in item for k in required):
            raise ValueError('Incomplete historical trajectory: ' + stage)
        for step in item['step_log']:
            if set(step) != {'batch', 'rows', 'positives', 'BCE_loss'}:
                raise ValueError('Malformed historical loss trajectory')
    for stage in ('el', 'im'):
        if len(prediction_rows(directory, stage)) != 383:
            raise ValueError('Historical prediction cohort missing')
    return {'status': 'verified', 'run_id': HISTORICAL, 'code_commit': manifest['git']['commit_sha'],
            'training_report_sha256': receipt['outputs']['reports/training_summary.json'],
            'training_report_bytes': (directory / 'reports/training_summary.json').stat().st_size,
            'authenticated_outputs': len(receipt['outputs'])}


def validate(*, config_path: str | Path, paths: StoragePaths | None = None,
             files: dict | None = None) -> dict:
    """Validate both complete stages using the actual native reader and wrapper.

    Only one native cohort is held at a time. No dataset copies, batching, model
    construction, optimizer, checkpoint writes or development scoring occur.
    """
    from . import bigmhc_gpu_worker as gpu
    paths = paths or resolve_paths()
    start = time.monotonic()
    config = runner.load_config(config_path)
    configurations = planned_configurations(config)
    verification = gpu.verify_inputs(config_path=config_path, paths=paths)
    resolved, identities = runner.resolve_inputs(config, paths, files)
    historical = historical_prerequisites(paths, config)
    sidecar = weights.runtime_adapter(config, resolved)
    low = config['loss_adapter']['protocol_version'] == weights.LOW_PROTOCOL
    modes = {mode: weights.LossAdapter(list(sidecar.scores.values()), sidecar.manifest, mode,
                protocol_version=config['loss_adapter']['protocol_version'])
             for mode in (('A', 'L', 'P') if low else ('A', 'B', 'P'))}
    weighted_mode = 'L' if low else 'B'
    if set(modes['A'].weights.values()) != {1.0}:
        raise ValueError('A weights must be unit weights')
    if modes[weighted_mode].evidence['by_HLA'] != modes['P'].evidence['by_HLA']:
        raise ValueError('Weighted/permuted per-HLA weight invariants differ')
    if low:
        from .el_low_stability_design import describe, RUN_ID as design_run
        expected = runner.readers._json(paths.project_runs_dir / design_run / 'weight_exposure.json')
        for hla in sidecar.manifest['positive_counts_by_HLA']:
            ids = [i for i, row in sidecar.scores.items() if row.resolved_hla == hla]
            if (sorted(modes['L'].rational[i] for i in ids) != sorted(modes['P'].rational[i] for i in ids) or
                    sorted(modes['L'].weights[i] for i in ids) != sorted(modes['P'].weights[i] for i in ids)):
                raise ValueError('Exact L/P per-HLA rational/FP32 multiset mismatch')
        for mode in ('L', 'P'):
            actual = describe(list(modes[mode].rational.values()))
            if actual != expected['overall']:
                raise ValueError('Approved Task 2.18 weight invariants differ')
            for hla, group in modes[mode].evidence['by_HLA'].items():
                if any(group[k] != v for k, v in expected['by_HLA'][hla].items() if k not in {'negatives'}):
                    raise ValueError('Approved per-HLA weight invariants differ')
    inventory = runner.readers._json(resolved['inventory'])
    allowed = set().union(*(v['by_HLA'] for v in inventory.values()))
    development = list(runner.input_rows(resolved['development'], allowed))
    if (len(development) != 383 or Counter(r['original_label'] for r in development) != {'1':120, '0':263}
            or len({r['hla'] for r in development}) != 31):
        raise ValueError('Frozen development cohort mismatch')
    runner.attach_provenance(development, resolved['development_provenance'])
    blocked = runner.adapter.substitution_neighborhood({r['peptide'] for r in development})
    with runner.raw._read_file(resolved['reference']) as stream, io.TextIOWrapper(stream, encoding='utf-8-sig', newline='') as text:
        report, _, reference = runner.data._reference(enumerate(csv.reader(text, strict=True), 1))
    if (report['feature_count'] != 414 or report['invalid_one_hot_rows'] or report['duplicate_identifier_count']
            or report['sanitized_UID_collision_groups'] or any(len(reference.get(h, ())) != 1 for h in allowed)):
        raise ValueError('Invalid or missing exact receptor encoding')
    import torch
    device = runner.runtime_device(torch, config)
    encodings = {}
    with runner.raw._read_file(resolved['reference']) as stream, io.TextIOWrapper(stream, encoding='utf-8-sig', newline='') as text:
        rows = csv.reader(text); next(rows)
        for row in rows:
            hla = runner.data.canonical_hla(row[0])
            if hla in allowed:
                encodings[hla] = torch.tensor([int(v) for v in row[1:]], dtype=torch.int8)
    cohorts = {}
    with runner.pinned_modules(resolved) as (_, Dataset):
        for stage, member in (('EL', 'el_train.csv'), ('IM', 'im_train.csv')):
            counts, flags = Counter(), Counter()
            fingerprint = hashlib.sha256()
            def records():
                ledger = (r for r in weights.manifest_rows(resolved[stage + '_provenance']) if r['retained'] == '1')
                for row, record in zip_longest(runner.input_rows(resolved[stage], allowed), ledger):
                    if row is None or record is None:
                        raise ValueError('Missing/extra original provenance rows')
                    if ([record['resolved_hla'], record['original_peptide'], record['original_label']]
                            != [row['hla'], row['peptide'], row['original_label']]
                            or int(record['derived_row_index']) != row['prepared_row_index']):
                        raise ValueError('Prepared input/provenance join differs')
                    if row['peptide'] in blocked:
                        raise ValueError('Exact/one-mismatch development exposure')
                    counts[row['original_label']] += 1
                    fingerprint.update((record['source_row_id'] + '\n').encode())
                    yield record  # IdentityDataset validates full raw hash and all source coordinates.
                    if stage == 'IM':
                        flags[record['original_rand']] += 1
            native = Dataset(Dataset.readPMHCs(str(resolved[stage]), allele=0, pepcol=1, tgtcol=2, hdrcnt=1, verbose=False), mhcenc=encodings)
            bound = weights.IdentityDataset(native, records(), stage=stage, adapter=modes['A'] if stage == 'EL' else None,
                                            archive_sha256=sidecar.manifest['archive_sha256'])
            if (len(bound.df) != config['expected_rows'][stage] or counts != config['expected_class_counts'][stage]
                    or counts != inventory[member]['class_balances']['original']):
                raise ValueError('Full original population/class counts differ: ' + stage)
            # Native encoding depends only on validated alphabet/length and exact HLA lookup.
            for amino_acid in runner.teacher.ALPHABET:
                encoded = native.encpep(amino_acid * 9)
                if tuple(encoded.shape) != (180,) or int(encoded.sum()) != 9:
                    raise ValueError('Native peptide encoder incompatible')
            cohorts[stage] = {'status': 'verified', 'rows': len(bound.df), 'original_labels': dict(counts),
                              'raw_hash_fields': ['mhc', 'pep', 'tgt'] + (['rand'] if stage == 'IM' else []),
                              'original_rand_counts': dict(flags), 'ordered_source_ids_sha256': fingerprint.hexdigest(),
                              'sampling_performed': False}
            del bound, native
    if low:
        from .bigmhc_baseline_compatibility import BASELINE_RUN
        saved = runner.readers._json(paths.project_runs_dir / BASELINE_RUN / 'reports/full_cohort_preflight.json')
        if cohorts != saved['cohorts']:
            raise ValueError('Original source-row cohort fingerprints differ from reused A')
    for identity in identities:
        if runner.raw.sha256_file(identity['path']) != identity['sha256']:
            raise ValueError('Immutable preflight input changed during validation')
    return {'schema_version': 1, 'status': 'passed', 'elapsed_seconds': time.monotonic() - start,
            'implementation_sha256': {path.name: runner.raw.sha256_file(path) for path in
                (Path(__file__), Path(runner.__file__), Path(weights.__file__),
                 paths.repository_root / 'src/stability_label_curation/bigmhc_abp_experiment.py')},
            'device': device, 'input_verification': verification, 'sources': identities,
            'cohorts': cohorts, 'Teacher': {'status': 'verified', 'positive_observations': len(sidecar.scores),
                'HLA_groups': sidecar.manifest['HLA_groups'], 'model_sha256': sidecar.manifest['Teacher_model_sha256']},
            'conditions': {mode: {'status': 'passed', 'scientific_configuration_sha256': weights.matched_config_identity(c),
                'loss_specification': c['loss_adapter'], 'weight_invariants': modes[mode].evidence}
                for mode, c in configurations.items()},
            'historical': historical, 'optimizer_initializations': 0, 'optimizer_steps': 0,
            'model_checkpoints_produced': 0, 'development_observations_scored': 0,
            'runtime_gate': ('L/P require pinned Task 2.17 A and current compatibility receipt' if low else
                             'B/P require the completed fresh A matched-state hash before training; checked by existing launcher'),
            'sealed_payloads_opened': []}


def record(*, config_path: str | Path, report: Path, paths: StoragePaths | None = None) -> dict:
    """Publish a compact success/failure receipt without overwriting evidence."""
    paths = paths or resolve_paths()
    try:
        result = validate(config_path=config_path, paths=paths)
    except Exception as error:
        runner.raw.write_report(report, {'schema_version': 1, 'status': 'failed', 'failure_reason': repr(error),
            'config_path': str(config_path), 'optimizer_initializations': 0, 'optimizer_steps': 0,
            'model_checkpoints_produced': 0, 'development_observations_scored': 0}, paths=paths)
        raise
    runner.raw.write_report(report, result, paths=paths)
    return result
