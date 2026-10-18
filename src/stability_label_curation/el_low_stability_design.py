"""Task 2.18 aggregate exposure analysis; no training or permutation execution."""
from collections import Counter, defaultdict
import csv
from fractions import Fraction
import gzip
import hashlib
import json
from pathlib import Path
import platform
from typing import Iterable

from . import el_positive_weighting_design as prior_design
from .el_positive_weighting_design import midrank_weights
from .paths import StoragePaths, resolve_paths

RUN_ID = 'task-2_18-low-stability-positive-design'
CONFIG = 'configs/bigmhc_abp_task2_14b.json'


def low_weights(scores: Iterable[str]) -> list[Fraction]:
    """Retain Task 2.12 Decimal ties/ranks and cap its exact weights at one."""
    return [min(Fraction(1), w) for w in midrank_weights(scores)]


def describe(weights: list[Fraction]) -> dict:
    if not weights or any(not Fraction(3, 4) < w <= 1 for w in weights):
        raise ValueError('Invalid one-sided positive weights')
    ordered = sorted(weights)
    n = len(weights)
    total = sum(weights, Fraction())
    median = (ordered[(n - 1) // 2] + ordered[n // 2]) / 2
    return dict(n=n, affected=sum(w < 1 for w in weights),
                affected_fraction=sum(w < 1 for w in weights) / n,
                min=float(ordered[0]), median=float(median), mean=float(total / n),
                max=float(ordered[-1]), total_before=n, total_after=float(total),
                total_after_exact=str(total), reduction=float(n - total),
                reduction_exact=str(n - total), reduction_fraction=float(1 - total / n))


def summarize(groups: dict[str, list[str]], negatives: dict[str, int]) -> dict:
    all_weights: list[Fraction] = []
    by_hla = {}
    if not groups or set(groups) != set(negatives):
        raise ValueError('Missing positive/negative HLA group')
    for hla, scores in sorted(groups.items()):
        weights = low_weights(scores)
        all_weights.extend(weights)
        by_hla[hla] = {**describe(weights), 'negatives': negatives[hla],
                       'small_positive_group_below10': len(scores) < 10}
    overall = describe(all_weights)
    n, total = overall['n'], Fraction(overall['total_after_exact'])
    return dict(status='design_only_scientific_approval_pending', overall=overall,
                by_HLA=by_hla, negative_count=sum(negatives.values()),
                native_EL_epoch=dict(steps=n, positive_exposures=n,
                    negative_exposures=16 * n, batch_denominator=17,
                    positive_coefficient_A=n / 17,
                    positive_coefficient_L_P=float(total / 17),
                    negative_coefficient_all_arms=16 * n / 17,
                    mean_positive_to_negative_coefficient_ratio=float(total / (16 * n)),
                    mean_batch_weight_A=1.0,
                    mean_batch_weight_L_P=float((16 + total / n) / 17)),
                training_performed=False, permutations_generated=False,
                row_weights_exported=False, labels_modified=False)


def inspect(paths: StoragePaths | None = None) -> dict:
    """Read only the existing score bindings and original EL; no outcome inputs."""
    paths = paths or resolve_paths()
    config_path = paths.repository_root / CONFIG
    config = json.loads(config_path.read_text())
    inputs = []

    def bound(name: str) -> Path:
        spec = config['inputs'][name]
        if spec['area'] != 'runs':
            raise ValueError('Expected an existing runs binding')
        path = (paths.project_runs_dir / spec['relative_path']).resolve()
        if not path.is_relative_to(paths.project_runs_dir):
            raise ValueError('Input outside project runs')
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        if digest != spec['sha256']:
            raise ValueError('Existing input binding mismatch: ' + name)
        inputs.append(dict(name=name, **spec))
        return path

    manifest = json.loads(bound('positive_score_manifest').read_text())
    with gzip.open(bound('positive_scores'), 'rt', newline='') as stream:
        rows = list(csv.DictReader(stream))
    if len(rows) != 70069 or manifest['rows'] != len(rows):
        raise ValueError('Positive population mismatch')
    positive = {}
    source_ids = set()
    last_source = last_prepared = 0
    for row in rows:
        index, source = int(row['prepared_row_index']), int(row['source_row_index'])
        if (index <= last_prepared or source <= last_source or
                row['source_row_id'] in source_ids or row['original_label'] != '1'):
            raise ValueError('Duplicate, unordered or nonpositive score identity')
        # Reuse the existing immutable source identity/hash definitions.
        if (row['source_row_id'] != prior_design.prior.pilot.row_id(
                manifest['archive_sha256'], 'el_train.csv', source) or
                row['source_row_sha256'] != prior_design.prior.adapter.source_hash(
                    ['mhc', 'pep', 'tgt'],
                    [row['original_hla'], row['original_peptide'], '1'])):
            raise ValueError('Score source identity mismatch')
        positive[index] = row
        source_ids.add(row['source_row_id'])
        last_prepared, last_source = index, source
    groups: dict[str, list[str]] = defaultdict(list)
    negatives: Counter[str] = Counter()
    count = found = 0
    with bound('EL').open(newline='') as stream:
        for count, row in enumerate(csv.DictReader(stream), 1):
            hla = prior_design.prior.pilot.bigmhc.canonical_hla(row['mhc'])
            if row['tgt'] == '1':
                score = positive.get(count)
                if score is None or (score['original_hla'], score['resolved_hla'],
                                     score['original_peptide']) != (row['mhc'], hla, row['pep']):
                    raise ValueError('Original EL positive/score alignment mismatch')
                groups[hla].append(score['predicted_half_life_hours'])
                found += 1
            elif row['tgt'] == '0' and count not in positive:
                negatives[hla] += 1
            else:
                raise ValueError('Original EL label mismatch')
    if (count != 1453578 or found != 70069 or sum(negatives.values()) != 1383509
            or len(groups) != 49 or {h: len(v) for h, v in groups.items()}
            != manifest['positive_counts_by_HLA']):
        raise ValueError('Original population changed')
    result = summarize(groups, dict(negatives))
    result['provenance'] = dict(inputs=inputs, configuration=CONFIG,
        configuration_sha256=hashlib.sha256(config_path.read_bytes()).hexdigest(),
        analysis_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        python=platform.python_version(), hostname=platform.node(), platform=platform.platform(),
        IM_or_development_payloads_opened=False, sealed_payloads_opened=False)
    return result


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write', action='store_true', help='Publish aggregates to the fixed new run')
    args = parser.parse_args()
    paths = resolve_paths()
    result = inspect(paths)
    content = json.dumps(result, indent=2, sort_keys=True) + '\n'
    if args.write:
        out = paths.project_runs_dir / RUN_ID
        out.mkdir()  # Exclusive creation: never overwrite a previous analysis.
        (out / 'weight_exposure.json').write_text(content)
        print(out / 'weight_exposure.json')
    else:
        print(content, end='')


if __name__ == '__main__':
    main()
