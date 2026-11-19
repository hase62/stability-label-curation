"""Common artifact bindings used by the independent historical EL10 analyses."""
from __future__ import annotations

import math
from pathlib import Path

from common import D, cohort_identities, native, put, read, records, runner, sha
from stability_label_curation import el_only_zero_shot_im as historical_el


def config():
    return read(D / "config/historical.json")


def lock_files(receipt, paths):
    put(receipt, {"files": {str(p.relative_to(D)): sha(p) for p in paths}})


def check_files(receipt, *, directory=D):
    expected = read(receipt)["files"]
    for relative, digest in expected.items():
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory.resolve()) or sha(path) != digest:
            raise ValueError(f"Historical artifact identity differs: {relative}")
    return expected


def identities(name):
    return cohort_identities(name)


def aligned_labels(name, rows):
    labels = records(D / f"cohorts/{name}_outcomes.jsonl")
    native.assert_alignment([r["source_id"] for r in rows], [r["source_id"] for r in labels])
    values = [r["label"] for r in labels]
    if any(type(v) is not int or v not in (0, 1) for v in values):
        raise ValueError("Non-binary historical outcome")
    return values


def ancestor(torch, BigMHC, device, arm="A"):
    cp = read(D / f"receipts/historical/{arm}_EL10.json")
    path = Path(cp["checkpoint"]).resolve()
    if not path.is_relative_to(D / "checkpoints"):
        raise ValueError("Historical checkpoint is outside this run")
    if runner.checkpoint_identity(path, cp["keys"]) != cp["files"]:
        raise ValueError("Historical checkpoint bytes changed")
    model = runner.load_checkpoint(torch, BigMHC, path, cp["keys"], device=device)
    if runner.state_hashes(model) != cp["state"]:
        raise ValueError("Historical checkpoint state changed")
    model.eval()
    return model


def forward(torch, model, encoded, identities, batch_size):
    scores = []
    state = runner.state_hashes(model)
    with torch.no_grad():
        for i in range(0, len(identities), batch_size):
            z, _ = model(encoded["mhc"][i:i+batch_size], encoded["pep"][i:i+batch_size])
            scores.extend((float(logit), float(p))
                          for logit, p in zip(z.cpu().tolist(), torch.sigmoid(z).cpu().tolist(), strict=True))
    if len(scores) != len(identities) or any(not math.isfinite(z) or not 0 <= p <= 1 for z, p in scores):
        raise ValueError("Missing or invalid historical scores")
    if runner.state_hashes(model) != state:
        raise ValueError("Historical scoring changed model state")
    return scores


def native_el_predictions(torch, Dataset, model, encoded_hla, rows, device):
    """The unadapted A and hard-filter arms use the original zero-shot EL forward."""
    dataset = historical_el.native_dataset(Dataset, torch, encoded_hla, rows)
    dataset.makebats(16, shuffle=False, negfrac=None)
    order, scores = [], []
    state = runner.state_hashes(model)
    with torch.no_grad():
        for idx in range(len(dataset)):
            batch = dataset[idx]
            order.extend(dataset.getbat(idx, enc=False)["_source_id"].tolist())
            logits, _ = model(batch.mhc.float().to(device), batch.pep.float().to(device))
            scores.extend(zip(logits.cpu().tolist(), torch.sigmoid(logits).cpu().tolist(), strict=True))
    native.assert_alignment([r["source_id"] for r in rows], order)
    if len(scores) != len(rows) or any(not math.isfinite(z) or not 0 <= p <= 1 for z, p in scores):
        raise ValueError("Invalid native EL predictions")
    if runner.state_hashes(model) != state:
        raise ValueError("Historical scoring changed model state")
    return scores
