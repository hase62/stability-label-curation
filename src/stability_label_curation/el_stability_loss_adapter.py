"""Optional source-ID-safe EL loss weights; no training at import or preparation."""
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass, asdict
from fractions import Fraction
import gzip
import hashlib
import io
import platform
from pathlib import Path
import random
import struct

from . import el_positive_weighting_design as design
from . import netmhcstabpan_2016 as raw
from . import scientific_gate0_preflight as readers
from .paths import resolve_paths

VERSION = 'el_stability_loss_adapter_v1'
LOW_PROTOCOL = 'el_low_stability_positive_v1'
CONFIG = 'configs/el_stability_weight_adapter_v1.json'
RUN_ID = 'task-2_13-el-stability-weight-adapter'
SIDECAR = 'processed/el_positive_teacher_scores.csv.gz'
MANIFEST = 'reports/positive_score_manifest.json'
FIELDS = ('prepared_row_index', 'source_row_index', 'source_row_id', 'source_row_sha256',
          'original_hla', 'resolved_hla', 'original_peptide', 'original_label', 'predicted_half_life_hours')
IDENTITY = '_slc_source_row_id'
BINDING = '_slc_row_binding'


def digest(document) -> str:
    return hashlib.sha256(raw.json_report(document).encode()).hexdigest()


def f32(value) -> float:
    return struct.unpack('<f', struct.pack('<f', float(value)))[0]


@dataclass(frozen=True)
class PositiveScore:
    prepared_row_index: str
    source_row_index: str
    source_row_id: str
    source_row_sha256: str
    original_hla: str
    resolved_hla: str
    original_peptide: str
    original_label: str
    predicted_half_life_hours: str


class LossAdapter:
    """One immutable positive map and its weights; negatives are always unit weight."""
    def __init__(self, rows: list[PositiveScore], manifest: dict, mode: str, *, protocol_version=design.VERSION):
        low = protocol_version == LOW_PROTOCOL
        if protocol_version not in {design.VERSION, LOW_PROTOCOL} or mode not in ({'A', 'L', 'P'} if low else {'A', 'B', 'P'}):
            raise ValueError('EL loss mode does not belong to the selected protocol')
        if manifest.get('permutation_python') not in (None, platform.python_version()):
            raise ValueError('Use the protocol-pinned Python version for matched weight assignment')
        self.mode, self.manifest, self.protocol_version = mode, manifest, protocol_version
        self.scores, self.weights, self.rational, groups = {}, {}, {}, defaultdict(list)
        last_prepared = last_source = 0
        for row in rows:
            prepared, source = int(row.prepared_row_index), int(row.source_row_index)
            if (prepared <= last_prepared or source <= last_source or row.source_row_id in self.scores
                    or row.original_label != '1' or row.resolved_hla not in manifest['supported_HLA']
                    or design.prior.pilot.bigmhc.canonical_hla(row.original_hla) != row.resolved_hla
                    or not row.resolved_hla.startswith(('HLA-A*', 'HLA-B*')) or '(' in row.resolved_hla
                    or len(row.original_peptide) != 9 or any(a not in design.prior.teacher.ALPHABET for a in row.original_peptide)
                    or row.source_row_id != design.prior.pilot.row_id(manifest['archive_sha256'], 'el_train.csv', source)
                    or row.source_row_sha256 != design.prior.adapter.source_hash(
                        ['mhc', 'pep', 'tgt'], [row.original_hla, row.original_peptide, '1'])):
                raise ValueError('Duplicate, unsupported, unordered or unauthenticated positive score')
            last_prepared, last_source = prepared, source
            self.scores[row.source_row_id] = row
            groups[row.resolved_hla].append(row)
        counts = {h: len(g) for h, g in sorted(groups.items())}
        if (not groups or counts != manifest['positive_counts_by_HLA'] or sum(counts.values()) != manifest['rows']
                or len(groups) != manifest['HLA_groups']):
            raise ValueError('Missing/extra positive scores or HLA coverage mismatch')
        self.evidence = {'mode': mode, 'positive_weights': len(rows), 'HLA_groups': len(groups),
                         'by_HLA': {}, 'assignment_sha256_by_HLA': {}}
        for hla, group in sorted(groups.items()):
            ids = [r.source_row_id for r in group]
            b = design.midrank_weights(r.predicted_half_life_hours for r in group)
            if low:
                b = [min(Fraction(1), w) for w in b]
            p = design.permuted_weights(ids, b, hla, 42)
            weights = [Fraction(1)] * len(ids) if mode == 'A' else b if mode in {'B', 'L'} else p
            rounded = [f32(w) for w in weights]
            residual = sum(rounded) - (float(sum(weights)) if low else len(ids))
            if abs(residual) > 1e-6 * max(1, len(ids)) or sorted(b) != sorted(p):
                raise ValueError('Weight conservation or permutation invariant failed')
            self.rational.update(zip(ids, weights)); self.weights.update(zip(ids, rounded))
            lines = ''.join(f'{i}\t{w}\n' for i, w in sorted(zip(ids, weights)))
            self.evidence['assignment_sha256_by_HLA'][hla] = hashlib.sha256(lines.encode()).hexdigest()
            if low:
                from .el_low_stability_design import describe
                description = describe(weights)
            else:
                description = design.describe_weights(weights)
            self.evidence['by_HLA'][hla] = {**description,
                'FP32_total_residual': residual,
                ('L_P_identical_multiset' if low else 'B_P_identical_multiset'): True,
                'small_positive_group_below10': len(ids) < 10}

    def validate_positive(self, identity, hla, peptide, prepared_index):
        row = self.scores.get(identity)
        if row is None or (row.resolved_hla, row.original_peptide, int(row.prepared_row_index)) != (hla, peptide, prepared_index):
            raise ValueError('Missing or mismatched positive score; no fallback')


def load_sidecar(path, manifest_path, *, canonical=True) -> LossAdapter:
    """Read and authenticate an immutable score sidecar; return mode A by default."""
    manifest = readers._json(manifest_path)
    if (manifest.get('schema_version') != 1 or manifest.get('version') != VERSION
            or manifest.get('fields') != list(FIELDS) or manifest.get('score_unit') != 'hours'
            or manifest.get('score_scale') != 'untransformed_kinetic_half_life_hours'
            or manifest.get('protocol_version') != design.VERSION or manifest.get('source_member') != 'el_train.csv'
            or manifest.get('original_label') != '1'
            or (canonical and (manifest.get('rows') != 70069 or manifest.get('HLA_groups') != 49))):
        raise ValueError('Invalid positive score manifest schema, units or canonical population')
    if canonical and (manifest.get('Teacher_model_sha256') != 'a28660fcad771c9c1cfccf72d5defc5e3d98ca833cf85e57eba37a4a59f0ce99'
            or manifest.get('archive_sha256') != '0d152a452756cf2e0014ffced6afc25118e7c11cf1f626b26e49f50f79edffaa'
            or manifest.get('original_EL_view_sha256') != '5bf7fb7c25845aa171baae289a1bb8f00b185f1d5cce99c05609eabaca929fdf'):
        raise ValueError('Canonical score sidecar is not from the frozen Teacher/original EL source')
    with raw._read_file(path) as stream:
        stream.seek(0, 2); size = stream.tell()
    if size != manifest['artifact']['size_bytes'] or raw.sha256_file(path) != manifest['artifact']['sha256']:
        raise ValueError('Positive score sidecar size/SHA256 mismatch')
    with raw._read_file(path) as stream, gzip.GzipFile(fileobj=stream) as gz:
        # Narrow, bounded sidecar, not a general archive reader.
        content = gz.read(32 * 1024 * 1024 + 1)
    if len(content) > 32 * 1024 * 1024:
        raise ValueError('Positive score sidecar decompression bound exceeded')
    csv_rows = csv.DictReader(io.StringIO(content.decode('utf-8'), newline=''), strict=True)
    if csv_rows.fieldnames != list(FIELDS):
        raise ValueError('Positive score sidecar columns changed')
    rows = []
    for row in csv_rows:
        if len(rows) >= 70069 or None in row or any(v is None for v in row.values()):
            raise ValueError('Extra/malformed positive score rows')
        rows.append(PositiveScore(**row))
    return LossAdapter(rows, manifest, 'A')


def row_binding(identity, hla, peptide, label):
    return digest([identity, hla, peptide, str(int(label))])


def original_fields(record: dict, stage: str) -> tuple[list[str], list[str]]:
    """Verify Task 2.5's parsed-string serialization, retaining IM's raw flag.

    Historical ledgers omitted rand, but retain its four-column SHA256. Recover
    the audited literal binary flag only when the complete original hash matches.
    An explicit flag must match as supplied; never normalize its formatting.
    """
    header = ['mhc', 'pep', 'tgt']
    fields = [record['original_hla'], record['original_peptide'], record['original_label']]
    if stage == 'IM':
        header.append('rand')
        candidates = [record['original_rand']] if 'original_rand' in record else ['0', '1']
        matches = [flag for flag in candidates if flag in {'0', '1'} and
                   design.prior.adapter.source_hash(header, fields + [flag]) == record['source_row_sha256']]
        if len(matches) != 1:
            raise ValueError('IM four-column raw-row hash mismatch; original rand unavailable or modified')
        record['original_rand'] = matches[0]
        fields.append(matches[0])
    if design.prior.adapter.source_hash(header, fields) != record['source_row_sha256']:
        raise ValueError('Original raw-row hash mismatch')
    return header, fields


class IdentityDataset:
    """Delegate every native batching/encoding operation; carry only auxiliary IDs."""
    source_identity_audit = True
    def __init__(self, native, ledger_rows, *, stage: str, adapter: LossAdapter | None = None, archive_sha256=None):
        if stage not in {'EL', 'IM'} or (stage == 'EL' and adapter is None) or (stage == 'IM' and adapter is not None):
            raise ValueError('Loss weights apply only to original EL training')
        self.native, self.stage, self.adapter = native, stage, adapter
        archive = adapter.manifest['archive_sha256'] if adapter is not None else archive_sha256
        if not design.prior.pilot._sha(archive): raise ValueError('Authenticated archive identity required')
        if IDENTITY in native.df or BINDING in native.df:
            raise ValueError('Native input already contains identity columns')
        ids, bindings, seen_positive, last_source = [], [], set(), 0
        records = iter(ledger_rows)
        for index, row in enumerate(native.df.itertuples(index=False), 1):
            record = next(records, None)
            if record is None:
                raise ValueError('Native rows lack source identities')
            label, identity = str(int(row.tgt)), record['source_row_id']
            source = int(record['row_index'])
            expected_member = 'el_train.csv' if stage == 'EL' else 'im_train.csv'
            original_fields(record, stage)
            if (float(row.tgt) not in (0.0, 1.0) or source <= last_source
                    or identity != design.prior.pilot.row_id(archive, expected_member, source)
                    or record['source_file'] != expected_member or int(record['derived_row_index']) != index
                    or ('prepared_row_index' in record and int(record['prepared_row_index']) != index)
                    or ('retained' in record and record['retained'] != '1')
                    or int(record['source_line_number']) != source + 1
                    or [record['resolved_hla'], record['original_peptide'], record['original_label']] != [row.mhc, row.pep, label]
                    or design.prior.pilot.bigmhc.canonical_hla(record['original_hla']) != row.mhc):
                raise ValueError('Native source-row join/label/order mismatch')
            if stage == 'EL':
                if label == '1':
                    adapter.validate_positive(identity, row.mhc, row.pep, index)
                    if identity in seen_positive: raise ValueError('Duplicate positive native identity')
                    seen_positive.add(identity)
                elif identity in adapter.scores:
                    raise ValueError('Positive score attached to negative label')
            last_source = source
            ids.append(identity); bindings.append(row_binding(identity, row.mhc, row.pep, label))
        if next(records, None) is not None or (stage == 'EL' and seen_positive != set(adapter.scores)):
            raise ValueError('Missing/extra native training rows or positive scores')
        # These columns travel with DataFrame.sample/reset_index; native getbat
        # reads only mhc/pep/tgt. No numeric/model input or sampler key is changed.
        native.df[IDENTITY] = ids; native.df[BINDING] = bindings

    @property
    def df(self): return self.native.df

    def makebats(self, *args, **kwargs): return self.native.makebats(*args, **kwargs)

    def __len__(self): return len(self.native)

    def __getitem__(self, index):
        batch = self.native[index]
        frame = self.native.getbat(index, enc=False)
        identities, labels = [], []
        for identity, binding, hla, peptide, label in frame[[IDENTITY, BINDING, 'mhc', 'pep', 'tgt']].itertuples(index=False, name=None):
            if float(label) not in (0, 1) or row_binding(identity, hla, peptide, label) != binding:
                raise ValueError('Sampled source-row values or labels changed')
            identities.append(identity); labels.append(int(label))
        if batch.tgt.tolist() != labels:
            raise ValueError('Encoded batch identity/target order mismatch')
        batch.source_row_ids = identities
        batch.source_labels = labels
        batch.source_batch_sha256 = digest(list(zip(identities, labels)))
        if self.stage == 'EL':
            batch.EL_loss_weights = [self.adapter.weights[i] if label == 1 else 1.0
                                     for i, label in zip(identities, labels)]
        return batch


def weighted_bce(torch, logits, targets, weights):
    """External per-example weights; retain native batch-row mean denominator."""
    if logits.shape != targets.shape or targets.ndim != 1 or len(weights) != len(targets) or not len(weights):
        raise ValueError('Loss shapes or batch weights disagree')
    tensor = torch.tensor(weights, dtype=targets.dtype, device=targets.device)
    if (not torch.isfinite(tensor).all() or (tensor <= 0).any()
            or not ((targets == 0) | (targets == 1)).all() or (tensor[targets == 0] != 1).any()):
        raise ValueError('Invalid weights or negative/target preservation failed')
    losses = torch.nn.functional.binary_cross_entropy_with_logits(logits, targets, reduction='none')
    return (losses * tensor).mean()


def rng_identity(torch, np) -> dict:
    """Read states only: no random draws, reseeding or device initialization."""
    state = np.random.get_state()
    result = {'python': digest(random.getstate()),
              'numpy': digest([state[0], state[1].tolist(), *state[2:]]),
              'torch_cpu': hashlib.sha256(torch.get_rng_state().numpy().tobytes()).hexdigest()}
    if torch.cuda.is_initialized():
        result['torch_cuda'] = [hashlib.sha256(s.cpu().numpy().tobytes()).hexdigest() for s in torch.cuda.get_rng_state_all()]
    return result


def manifest_rows(path):
    """Read only the runner's original-row coordinate manifest, never corrected views."""
    with raw._read_file(path) as stream, gzip.GzipFile(fileobj=stream) as gz, io.TextIOWrapper(gz, encoding='utf-8', newline='') as text:
        yield from csv.DictReader(text, strict=True)


def validate_runtime_spec(spec: dict, condition: str):
    required = {'schema_version', 'version', 'mode', 'protocol_version', 'strength', 'seed',
                'training_authorized', 'matched_reference'}
    low = spec.get('protocol_version') == LOW_PROTOCOL
    if (set(spec) != required or spec['schema_version'] != 1 or spec['version'] != VERSION
            or spec['mode'] not in ({'A', 'L', 'P'} if low else {'A', 'B', 'P'}) or spec['mode'] != condition
            or spec['protocol_version'] not in {design.VERSION, LOW_PROTOCOL} or spec['strength'] != '0.5'
            or spec['seed'] != 42 or type(spec['training_authorized']) is not bool):
        raise ValueError('Runtime weighting specification differs from approved protocol')
    reference = spec['matched_reference']
    if condition == 'A' and reference is not None:
        raise ValueError('Fresh adapted A defines the matched reference')
    if condition != 'A' and reference is None:
        raise ValueError('B/P require a pinned fresh adapted A reference')
    if reference is not None:
        design.prior.pilot.registry._relative(reference['relative_path'])
        if (reference['area'] != 'runs' or (reference['sha256'] is not None and not design.prior.pilot._sha(reference['sha256']))
                or (spec['training_authorized'] and reference['sha256'] is None)):
            raise ValueError('Matched A reference is unresolved or unsafe')


def require_training_authorization(config):
    if config.get('loss_adapter') and not config['loss_adapter']['training_authorized']:
        raise ValueError('A/B/P training is not authorized by this engineering-preparation configuration')


def runtime_adapter(config, files):
    base = load_sidecar(files['positive_scores'], files['positive_score_manifest'])
    if base.manifest['original_EL_view_sha256'] != config['inputs']['EL']['sha256']:
        raise ValueError('Sidecar belongs to a different original EL population')
    return LossAdapter(list(base.scores.values()), base.manifest, config['condition'],
                       protocol_version=config['loss_adapter']['protocol_version'])


def matched_config_identity(config):
    fields = ('source_commit', 'seed', 'epochs', 'batch_size', 'learning_rate', 'device', 'cpu_threads',
              'num_workers', 'persistent_workers', 'label_policy', 'rows_per_class', 'expected_rows', 'expected_class_counts', 'inputs')
    return digest({key: config[key] for key in fields})


def check_reference(reference, *, initial=None, rng=None, stage=None, training=None):
    if reference is None: return
    if initial is not None and initial != reference['initial_tensor_sha256']:
        raise ValueError('Matched initial model tensors differ')
    if rng is not None and rng != reference['rng_before_' + stage]:
        raise ValueError('Matched model/sampler RNG boundary differs: ' + stage)
    if training is not None:
        expected = reference[stage]
        for key in ('optimization_steps', 'sampled_batch_sha256', 'optimizer_defaults', 'updated_parameters', 'optimizer_skip_mask'):
            # JSON references represent AdamW's tuple defaults as lists.
            if digest(training[key]) != digest(expected[key]):
                raise ValueError('Matched sampling/optimizer exposure differs: ' + stage + '/' + key)


def prepare(*, out=None, verify_existing=False, paths=None):
    """Make a score-only sidecar; hashes can also be calculated without writing."""
    paths = paths or resolve_paths()
    config_path = paths.repository_root / design.CONFIG
    config, previous, files, inputs, documents = design.load_inputs(config_path, paths)
    reference_path = paths.project_runs_dir / 'task-2_12-el-positive-weighting-preregistration/reports/weighting_design_feasibility.json'
    reference_sha = 'df6c8795cac616ba577e55e0b1ecaa1de4d1bc6a1ac56b0f5578921e1953eab3'
    if raw.sha256_file(reference_path) != reference_sha:
        raise ValueError('Approved Task2.12 weight-reference SHA256 mismatch')
    reference = readers._json(reference_path)
    inputs.append({'path': str(reference_path), 'sha256': reference_sha})
    context = design.prior.verify_lineage(previous, files)
    audit = {}
    records = design.prior.aligned_scores(design.prior.adapter._csv_rows(files['el_scores']),
        design.prior.ledger_rows(files['el_ledger']), design.prior.original_rows(files['el_original']), context, audit)
    directory = None
    if out is not None:
        directory, run_manifest = design.prior.teacher._run(out, paths)
        if any(i not in run_manifest['data_provenance']['input_artifacts'] for i in inputs):
            raise ValueError('Sidecar run must record all actual hashed inputs')
    target = directory / SIDECAR if directory and not verify_existing else None
    positives = []
    with design.prior.adapter.artifact_csv(target, list(FIELDS), True) as (writer, sink):
        for prepared, row in enumerate(records, 1):
            if row['original_label'] != '1': continue
            score = PositiveScore(str(prepared), row['row_index'], row['source_row_id'], row['source_row_sha256'],
                row['original_hla'], row['resolved_hla'], row['original_peptide'], '1', row['predicted_half_life_hours'])
            writer.writerow(asdict(score)); positives.append(score)
        if (audit['retained_rows'] != 1453578 or audit['retained_labels'] != {'0': 1383509, '1': 70069}
                or audit['removed_rows'] != 55 or audit['pre_purge_rows'] != 1453633
                or len(positives) != 70069 or len({r.resolved_hla for r in positives}) != 49):
            raise ValueError('Sidecar population differs from approved cohort')
    portable = []
    for item in inputs:
        path = Path(item['path'])
        area, root = ('data', paths.project_data_dir) if path.is_relative_to(paths.project_data_dir) else ('runs', paths.project_runs_dir)
        portable.append({'area': area, 'relative_path': str(path.relative_to(root)), 'sha256': item['sha256']})
        if raw.sha256_file(path) != item['sha256']: raise ValueError('Source input changed')
    counts = dict(sorted(Counter(r.resolved_hla for r in positives).items()))
    manifest = {'schema_version': 1, 'version': VERSION, 'protocol_version': design.VERSION,
        'artifact': {'relative_path': SIDECAR, 'sha256': sink.digest.hexdigest(), 'size_bytes': sink.size},
        'fields': list(FIELDS), 'rows': len(positives), 'HLA_groups': len(counts), 'positive_counts_by_HLA': counts,
        'permutation_python': platform.python_version(),
        'supported_HLA': sorted(h for h, m in context.model.document['alleles'].items() if m['status'] == 'trained'),
        'score_unit': 'hours', 'score_scale': 'untransformed_kinetic_half_life_hours',
        'source_member': 'el_train.csv', 'original_label': '1', 'archive_sha256': context.archive_sha256,
        'Teacher_model_sha256': context.model_sha256, 'original_EL_view_sha256': previous['inputs']['el_original']['sha256'],
        'parent_analysis_commit': config['parent_code_commit'], 'protocol_commit': '253921a7ff3e4b7d18e3062eb7e045dfe89be83e',
        'source_inputs': portable, 'alignment': audit, 'labels_modified': False,
        'content': 'Scores only; no labels changed, no development outcomes or training weights'}
    if len(positives) != 70069 or len(counts) != 49: raise ValueError('Positive coverage mismatch')
    adapters = {mode: LossAdapter(positives, manifest, mode) for mode in ('A', 'B', 'P')}
    evidence = {mode: a.evidence for mode, a in adapters.items()}
    for mode in ('B', 'P'):
        for hla, value in evidence[mode]['assignment_sha256_by_HLA'].items():
            if value != reference['permutation_assignment_sha256_by_HLA'][f'{hla}:{mode}']:
                raise ValueError('Weight assignment differs from approved Task2.12 reference')
    result = {'manifest': manifest, 'manifest_sha256': hashlib.sha256(raw.json_report(manifest).encode()).hexdigest(),
              'weight_evidence': evidence, 'inputs': inputs}
    if directory:
        outputs = {MANIFEST: raw.json_report(manifest), 'reports/weight_invariants.json': raw.json_report(evidence)}
        for relative, text in outputs.items():
            if verify_existing:
                if raw.sha256_file(directory / relative) != hashlib.sha256(text.encode()).hexdigest():
                    raise ValueError('Offline sidecar metadata differs')
            else: raw.write_text_report(directory / relative, text, paths=paths)
        if verify_existing and raw.sha256_file(directory / SIDECAR) != sink.digest.hexdigest():
            raise ValueError('Offline sidecar bytes differ')
    return result


def synthetic_noop_evidence(*, paths=None, device="cpu", protocol_version=design.VERSION):
    """Pinned synthetic forward/backward; CUDA also checks two matched AdamW steps.

    Optional existing tensor runtime; not called during sidecar preparation or on
    import. No scientific CSV, development outcomes or checkpoints are read.
    """
    import time
    import importlib.metadata
    import torch
    import numpy as np
    import pandas as pd
    from . import bigmhc_baseline_runner as runner
    paths = paths or resolve_paths()
    transfer = readers._json(paths.repository_root / 'configs/bigmhc_gpu_worker_transfer.json')
    files, inputs = {}, []
    for name in ('mhcuid', 'encseq', 'dataset', 'bigmhc'):
        spec = transfer['inputs']['source_' + name]
        path = paths.project_data_dir / spec['relative_path']
        if raw.sha256_file(path) != spec['sha256']: raise ValueError('Synthetic check source SHA256 mismatch')
        files['source_' + name] = path; inputs.append({'path': str(path), 'sha256': spec['sha256']})
    runtime = runner.load_config(paths.repository_root / CONFIG)
    if device not in {'cpu', 'cuda'}:
        raise ValueError('Synthetic gate requires explicit cpu or cuda')
    runtime['device'] = device
    selected_device = runner.runtime_device(torch, runtime)
    runner.seed_runtime(torch, np, runtime)
    hla, archive = 'HLA-A*02:01', 'a' * 64
    positives = []
    records = []
    peptides = []
    for i in range(1, 273):
        label = '1' if i <= 16 else '0'
        alphabet = design.prior.teacher.ALPHABET
        peptide = 'A' * 7 + alphabet[(i-1)//20] + alphabet[(i-1)%20]
        peptides.append(peptide)
        identity = design.prior.pilot.row_id(archive, 'el_train.csv', i)
        sha = design.prior.adapter.source_hash(['mhc', 'pep', 'tgt'], [hla, peptide, label])
        records.append({'source_file': 'el_train.csv', 'row_index': str(i), 'source_line_number': str(i+1),
            'source_row_id': identity, 'source_row_sha256': sha, 'resolved_hla': hla, 'original_hla': hla,
            'original_peptide': peptide, 'original_label': label, 'derived_row_index': str(i)})
        if label == '1': positives.append(PositiveScore(str(i), str(i), identity, sha, hla, hla, peptide, label, str(i)))
    metadata = {'rows': 16, 'HLA_groups': 1, 'positive_counts_by_HLA': {hla:16}, 'supported_HLA': [hla], 'archive_sha256': archive}
    modes = ('A', 'L', 'P') if protocol_version == LOW_PROTOCOL else ('A', 'B', 'P')
    weighted_mode = modes[1]
    start = time.monotonic()
    with runner.pinned_modules(files) as (BigMHC, Dataset):
        def native():
            frame = pd.DataFrame({'mhc':[hla]*272, 'pep':peptides, 'tgt':[1.0]*16+[0.0]*256, 'len':[9]*272})
            return Dataset(frame, mhcenc={hla:torch.zeros(414, dtype=torch.int8)})
        schedules, final_rngs = {}, {}
        for mode in ('legacy', *modes):
            random.seed(42); np.random.seed(42); torch.manual_seed(42)
            ds = native() if mode == 'legacy' else IdentityDataset(native(), records, stage='EL', adapter=LossAdapter(positives,metadata,mode,protocol_version=protocol_version))
            ds.makebats(16,shuffle=True,negfrac=.99)
            batches = list(torch.utils.data.DataLoader(ds,batch_size=None,shuffle=True,num_workers=0))
            if len(batches)!=16 or any(len(b.tgt)!=17 or int(b.tgt.sum())!=1 for b in batches):
                raise ValueError('Authentic native 17-row batch contract failed')
            schedules[mode] = [digest([b.mhc.tolist(),b.pep.tolist(),b.tgt.tolist()]) if mode=='legacy'
                               else b.source_batch_sha256 for b in batches]
            final_rngs[mode] = rng_identity(torch,np)
            if mode=='legacy': legacy_tensors=[(b.mhc,b.pep,b.tgt) for b in batches]
            else:
                for batch,(mhc,pep,tgt) in zip(batches,legacy_tensors):
                    if not all(torch.equal(a,b) for a,b in ((batch.mhc,mhc),(batch.pep,pep),(batch.tgt,tgt))):
                        raise ValueError('Adapter changed authentic encoded input/label sequence')
                if mode=='A': test_batch=batches[0]
        if schedules['A']!=schedules[weighted_mode] or schedules['A']!=schedules['P'] or len({digest(r) for r in final_rngs.values()})!=1:
            raise ValueError('Adapter changed native sampling or RNG streams')
        initial_by_mode = {}
        for mode in modes:
            random.seed(42); np.random.seed(42); torch.manual_seed(42)
            LossAdapter(positives, metadata, mode, protocol_version=protocol_version)
            model = runner.on_device(BigMHC(), selected_device).train()
            initial_by_mode[mode] = runner.state_hashes(model)
        initial = initial_by_mode['A']
        if any(state != initial for state in initial_by_mode.values()):
            raise ValueError('Synthetic A/B/P initialization mismatch')
        if len(initial)!=36: raise ValueError('Expected authentic 36-tensor architecture')
        rng=torch.get_rng_state().clone(); saved=None; maximum=0.0;exact=True;losses=[]
        cuda_rng = torch.cuda.get_rng_state_all() if selected_device != 'cpu' else None
        initial_state = {k: v.detach().clone() for k, v in model.state_dict().items()}
        update_hashes = []
        for adapted in (False,True):
            model.load_state_dict(initial_state)
            model.zero_grad(set_to_none=True);torch.set_rng_state(rng)
            if cuda_rng is not None: torch.cuda.set_rng_state_all(cuda_rng)
            optimizer = torch.optim.AdamW(model.parameters(), lr=5e-5) if cuda_rng is not None else None
            output,_=model(runner.on_device(test_batch.mhc.float(), selected_device),
                           runner.on_device(test_batch.pep.float(), selected_device))
            target=runner.on_device(test_batch.tgt.float(), selected_device)
            loss=weighted_bce(torch,output,target,test_batch.EL_loss_weights) if adapted else torch.nn.BCEWithLogitsLoss()(output,target)
            loss.backward();losses.append(float(loss.detach()))
            if not adapted:
                saved={k:p.grad.detach().clone() for k,p in model.named_parameters()}
                forward=output.detach().clone();after=rng_identity(torch,np)
            else:
                torch.testing.assert_close(output,forward,rtol=1e-6,atol=1e-7)
                if after != rng_identity(torch,np):raise ValueError('No-op loss consumed training RNG')
                for key,param in model.named_parameters():
                    torch.testing.assert_close(param.grad,saved[key],rtol=1e-6,atol=1e-7)
                    exact &= torch.equal(param.grad,saved[key])
                    maximum=max(maximum,float((param.grad-saved[key]).abs().max()))
            if optimizer is not None:
                optimizer.step()
                update_hashes.append(runner.state_hashes(model))
        if update_hashes and update_hashes[0] != update_hashes[1]:
            raise ValueError('CUDA no-op AdamW parameter updates differ')
        model.load_state_dict(initial_state)
        if initial!=runner.state_hashes(model) or abs(losses[0]-losses[1])>1e-7+1e-6*abs(losses[0]):
            raise ValueError('No-op changed parameters or loss')
    return {'schema_version':1,'protocol_version':protocol_version,'condition_names':list(modes),'fixture':'Synthetic 272 unique nine-mers: 16 positives + 256 negatives; zero receptor vector; not scientific observations',
        'source_commit':runner.SOURCE_COMMIT,'source_inputs':inputs,'device':selected_device,'precision':'FP32',
        'adapter_source_sha256':raw.sha256_file(Path(__file__)),
        'runner_source_sha256':raw.sha256_file(Path(runner.__file__)),
        'versions':{n:importlib.metadata.version(n) for n in ('torch','numpy','pandas')},
        'authentic_architecture_state_tensors':36,'legacy_loss':losses[0],'adapter_A_loss':losses[1],
        'loss_exactly_equal':losses[0]==losses[1],'gradient_maximum_absolute_difference':maximum,
        'gradients_exactly_equal':exact,'relative_tolerance':1e-6,'absolute_tolerance':1e-7,
        'native_batches_per_mode':16,'native_batch_rows':17,'native_positive_rows_per_batch':1,
        'A_B_P_ordered_source_identity_digest':digest(schedules['A']),
        'native_encoded_tensors_and_labels_identical':True,'model_sampler_RNG_states_identical':True,
        'source_row_identity_collation_verified':True,'model_parameters_unchanged':True,
        'authentic_model_optimizer_steps':len(update_hashes),'real_training_rows_read':0,'development_predictions_generated':0,
        'A_B_P_initial_tensor_sha256':initial_by_mode,'AdamW_updates_identical':bool(update_hashes) and update_hashes[0]==update_hashes[1],
        'elapsed_seconds':time.monotonic()-start}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out')
    parser.add_argument('--verify-existing', action='store_true')
    args = parser.parse_args()
    result = prepare(out=args.out, verify_existing=args.verify_existing)
    print(raw.json_report({k: v for k, v in result.items() if k != 'inputs'}), end='')
