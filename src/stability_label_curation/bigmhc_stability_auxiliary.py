"""Prespecified kinetic-stability auxiliary targets and non-invasive BigMHC head.

Torch is injected/lazy. Import and path resolution have no filesystem side effects.
Historical baseline, A/B/P and A/L/P modules remain unchanged.
"""
from collections import defaultdict
from fractions import Fraction
import hashlib
import random
from typing import Any

from . import bigmhc_baseline_runner as runner
from . import el_stability_loss_adapter as binding

VERSION = 'hla_relative_stability_auxiliary_v1'
HEAD_SEED = 22042


def permute(ids: list[str], ranks: list[Fraction], hla: str) -> list[Fraction]:
    """Source-ID-sorted Fisher–Yates in a protocol-specific independent stream."""
    if not ids or len(ids) != len(ranks) or len(set(ids)) != len(ids) or not hla:
        raise ValueError('Invalid auxiliary permutation identities')
    order = sorted(range(len(ids)), key=ids.__getitem__)
    material = f'{VERSION}\0targets\0{42}\0{hla}'.encode()
    rng = random.Random(int.from_bytes(hashlib.sha256(material).digest(), 'big'))
    shuffled = [ranks[i] for i in order]
    for j in range(len(shuffled) - 1, 0, -1):
        k = rng.randrange(j + 1)
        shuffled[j], shuffled[k] = shuffled[k], shuffled[j]
    result = list(ranks)
    for i, value in zip(order, shuffled, strict=True):
        result[i] = value
    if sorted(result) != sorted(ranks):
        raise ValueError('Auxiliary target multiset changed')
    return result


class Targets:
    """Reuse authenticated score identities, never attach targets to negatives/IM."""
    def __init__(self, sidecar: binding.LossAdapter, mode: str, *, source_ids: set[str] | None = None):
        if mode not in {'S', 'P'}:
            raise ValueError('Auxiliary mode must be S or P')
        self.mode, self.sidecar = mode, sidecar
        if source_ids is not None and (not source_ids or not source_ids <= sidecar.scores.keys()):
            raise ValueError('Missing/empty training-positive score identities')
        self.exact: dict[str, Fraction] = {}
        self.values: dict[str, float] = {}
        groups: dict[str, list] = defaultdict(list)
        for row in sidecar.scores.values():
            if source_ids is not None and row.source_row_id not in source_ids:
                continue
            groups[row.resolved_hla].append(row)
        self.evidence: dict[str, Any] = {'mode': mode, 'by_HLA': {}}
        for hla, rows in sorted(groups.items()):
            ids = [r.source_row_id for r in rows]
            # Existing w = 3/4 + r/2, inverted exactly; includes numeric-text ties.
            ranks = [2 * w - Fraction(3, 2) for w in binding.design.midrank_weights(
                r.predicted_half_life_hours for r in rows)]
            assigned = ranks if mode == 'S' else permute(ids, ranks, hla)
            rounded = [binding.f32(r) for r in assigned]
            if any(not 0 <= r <= 1 for r in assigned):
                raise ValueError('Rank outside unit interval')
            self.exact.update(zip(ids, assigned, strict=True))
            self.values.update(zip(ids, rounded, strict=True))
            self.evidence['by_HLA'][hla] = {
                'n': len(ids), 'exact_multiset_sha256': binding.digest(list(map(str, sorted(assigned)))),
                'FP32_multiset_sha256': binding.digest(sorted(rounded)),
                'assignment_sha256': binding.digest(sorted((i, str(r)) for i, r in zip(ids, assigned))),
                'unchanged_from_S': sum(a == b for a, b in zip(ranks, assigned)),
                'mean_exact': str(sum(assigned) / len(assigned))}
        self.evidence.update(positive_observations=len(self.values), HLA_groups=len(groups),
                             negative_targets=0, IM_targets=0,
                             rank_reference_population='full_positive_cohort' if source_ids is None else 'EL_training_positives_only')

    def anchor(self, identities: list[str], labels: list[int]) -> tuple[int, float]:
        if len(identities) != len(labels) or not labels or any(y not in (0, 1) for y in labels):
            raise ValueError('Invalid sampled auxiliary binding')
        positions = [j for j, y in enumerate(labels) if y == 1]
        if positions != [0] or any(i in self.values for i, y in zip(identities, labels) if y == 0):
            raise ValueError('Native EL batch must have exactly one positive anchor first')
        if identities[0] not in self.values:
            raise ValueError('Missing positive auxiliary target; no fallback')
        return 0, self.values[identities[0]]


def compare_targets(s: Targets, p: Targets) -> dict:
    if s.mode != 'S' or p.mode != 'P' or set(s.exact) != set(p.exact):
        raise ValueError('S/P source population mismatch')
    if set(s.values) != set(p.values) or set(s.values) != set(s.exact):
        raise ValueError('S/P FP32 source population mismatch')
    for hla, a in s.evidence['by_HLA'].items():
        ids = [i for i, row in s.sidecar.scores.items() if row.resolved_hla == hla and i in s.exact]
        if (any(p.sidecar.scores[i] != s.sidecar.scores[i] for i in ids)
                or sorted(s.exact[i] for i in ids) != sorted(p.exact[i] for i in ids)
                or sorted(s.values[i] for i in ids) != sorted(p.values[i] for i in ids)):
            raise ValueError('S/P actual per-HLA targets differ')
        b = p.evidence['by_HLA'].get(hla, {})
        if any(a[k] != b.get(k) for k in ('n', 'exact_multiset_sha256', 'FP32_multiset_sha256', 'mean_exact')):
            raise ValueError('S/P per-HLA target distribution mismatch')
    if set(s.evidence['by_HLA']) != set(p.evidence['by_HLA']):
        raise ValueError('S/P HLA groups mismatch')
    return {'same_source_identities': True, 'per_HLA_exact_and_FP32_multisets_equal': True,
            'only_source_to_target_assignment_differs': True, 'S': s.evidence, 'P': p.evidence}


class AuxiliaryHead:
    """Separate head + read-only hook: authentic forward and state_dict stay intact."""
    def __init__(self, torch: Any, backbone: Any, *, device: str = 'cpu', width: int = 414):
        if backbone.condenser.att.out_features != width:
            raise ValueError('Unexpected authentic shared representation width')
        # Only the CPU generator is seeded/restored; never touch CUDA/Python/NumPy RNG.
        with torch.random.fork_rng(devices=[]):
            torch.random.default_generator.manual_seed(HEAD_SEED)
            self.head = torch.nn.Linear(width, 1, device='cpu', dtype=torch.float32)
        self.head.to(device)
        self.features: Any = None
        self.handle: Any = None
        self.backbone = backbone

    def capture(self) -> None:
        if self.handle is not None:
            raise ValueError('Auxiliary hook already active')
        def receive(module, inputs, output):
            self.features = output  # Keep autograd graph; no detach/second backbone pass.
        self.handle = self.backbone.condenser.att.register_forward_hook(receive)

    def close(self) -> None:
        if self.handle is not None:
            self.handle.remove()
            self.handle = None
        self.features = None

    def prediction(self, anchor: int):
        if self.features is None or self.features.ndim != 2:
            raise ValueError('Shared representation was not captured')
        return self.head(self.features[anchor:anchor + 1]).reshape(())


def losses(torch: Any, logits: Any, labels: Any, prediction: Any = None,
           target: float | None = None, *, coefficient: float = 0.1):
    """Native batch-mean BCE plus ONE anchored squared error; no BCE weights."""
    bce = torch.nn.BCEWithLogitsLoss()(logits, labels)
    if coefficient == 0:
        return bce, bce, None  # No extra arithmetic/autograd path when disabled.
    if coefficient != 0.1 or prediction is None or target is None or not 0 <= target <= 1:
        raise ValueError('Auxiliary loss differs from the fixed protocol')
    if prediction.numel() != 1:
        raise ValueError('One native positive anchor required')
    mse = (prediction.reshape(()) - prediction.new_tensor(target)).square()
    return bce + coefficient * mse, bce, mse


def train_el(torch: Any, model: Any, dataset: Any, config: dict, auxiliary: AuxiliaryHead,
             targets: Targets, reference: dict, *, device: str = 'cpu', coefficient: float = 0.1,
             optimizer: Any = None) -> dict:
    """Native EL schedule, original AdamW group, appended head and fixed loss.

    IM delegates directly to runner.train_epoch. This dedicated EL loop avoids
    changing the historical baseline/weighted runner or its compatibility ASTs.
    """
    if coefficient not in (0, 0.1):
        raise ValueError('Only fixed auxiliary loss or synthetic disabled-equivalence path supported')
    if not getattr(dataset, 'source_identity_audit', False) or dataset.adapter is not targets.sidecar:
        raise ValueError('Auxiliary targets require the authenticated identity wrapper')
    runner.on_device(model, device).train()
    auxiliary.head.train()
    parameters = list(model.parameters()) + list(auxiliary.head.parameters())
    if optimizer is None:
        optimizer = torch.optim.AdamW(parameters, lr=config['learning_rate'])
    elif [id(p) for group in optimizer.param_groups for p in group['params']] != [id(p) for p in parameters]:
        raise ValueError('Persistent auxiliary optimizer parameter order changed')
    if binding.digest(optimizer.defaults) != binding.digest(reference['optimizer_defaults']):
        raise ValueError('Original optimizer hyperparameters changed')
    names = [k for k, _ in model.named_parameters()]
    if names != reference['updated_parameters']:
        raise ValueError('Shared optimizer parameter order changed')
    dataset.makebats(config['batch_size'], shuffle=True, negfrac=0.99)
    loader = torch.utils.data.DataLoader(dataset, batch_size=None, shuffle=True, num_workers=0, persistent_workers=False)
    steps, hashes = [], []
    first_head_gradient_norms = None
    if coefficient:
        auxiliary.capture()
    try:
        for index, batch in enumerate(loader, 1):
            hashes.append(batch.source_batch_sha256)
            expected = reference['sampled_batch_sha256']
            if index > len(expected) or hashes[-1] != expected[index - 1]:
                raise ValueError('Matched batch identities differ before optimizer update')
            labels = runner.on_device(batch.tgt.float(), device)
            if batch.source_labels != labels.tolist():
                raise ValueError('Original labels changed')
            anchor, target = targets.anchor(batch.source_row_ids, batch.source_labels)
            optimizer.zero_grad()
            auxiliary.features = None
            logits, _ = model(mhc=runner.on_device(batch.mhc.float(), device),
                              pep=runner.on_device(batch.pep.float(), device))
            total, bce, mse = losses(torch, logits, labels,
                                      auxiliary.prediction(anchor) if coefficient else None, target, coefficient=coefficient)
            if not torch.isfinite(total):
                raise ValueError('Nonfinite auxiliary objective')
            total.backward()
            if coefficient and any(p.grad is None or not torch.isfinite(p.grad).all() for p in auxiliary.head.parameters()):
                raise ValueError('Auxiliary head has missing/nonfinite gradients')
            if coefficient and first_head_gradient_norms is None:
                first_head_gradient_norms = {k: float(p.grad.norm()) for k, p in auxiliary.head.named_parameters()}
            optimizer.step()
            steps.append({'batch': index, 'rows': len(labels), 'positives': 1,
                          'BCE_loss': float(bce.detach()), 'auxiliary_MSE': float(mse.detach()) if mse is not None else 0.0,
                          'total_loss': float(total.detach())})
            print(f'EL batch {index}/{len(loader)} BCE {steps[-1]["BCE_loss"]:.6f} MSE {steps[-1]["auxiliary_MSE"]:.6f}', flush=True)
    finally:
        auxiliary.close()
    if not steps:
        raise ValueError('No native EL optimization steps executed')
    result = {'optimization_steps': len(steps), 'sampled_batch_sha256': hashes,
              'optimizer_defaults': optimizer.defaults, 'updated_parameters': names,
              'auxiliary_updated_parameters': ['weight', 'bias'], 'optimizer_skip_mask': [False] * len(steps),
              'batches': len(loader), 'step_log': steps, 'lambda_aux': coefficient,
              'consumed_rows': sum(s['rows'] for s in steps),
              'optimizer_class_exposures': {'1': len(steps), '0': sum(s['rows'] - 1 for s in steps)},
              'sampled_class_exposures': {'1': len(steps), '0': sum(s['rows'] - 1 for s in steps)},
              'all_negative_batches_skipped': 0, 'skipped_batch_log': [],
              'requested_batch_size': config['batch_size'],
              'maximum_optimized_batch_rows': max(s['rows'] for s in steps),
              'sampling': 'Pinned makebats(shuffle=True,negfrac=0.99); no sampler changes',
              'source_style_epoch_BCE_loss': sum(s['BCE_loss'] for s in steps) / len(loader),
              'auxiliary_denominator': 'one positive anchor per native EL batch',
              'BCE_denominator': 'all native batch rows',
              'row_weighted_BCE_loss': sum(s['BCE_loss'] * s['rows'] for s in steps) / sum(s['rows'] for s in steps),
              'mean_auxiliary_MSE': sum(s['auxiliary_MSE'] for s in steps) / len(steps),
              'mean_total_loss': sum(s['total_loss'] for s in steps) / len(steps)}
    result['auxiliary_gradient_evidence'] = {
        'finite_head_gradient_checks': len(steps) if coefficient else 0,
        'first_update_head_gradient_norms': first_head_gradient_norms,
        'isolated_auxiliary_backbone_flow_checked_by_focused_synthetic_tests': True}
    binding.check_reference({'EL': reference}, stage='EL', training=result)
    return result
