"""Regenerate the Task 2.23 ancestor and Task 2.41-B EL-only comparisons."""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction

from common import D, baseline, binding, csvout, native, put, read, records, resolved, reuse, rows, runner, sha, shared, train_boundary, validate_seal
import hard_filter_metrics as metrics
from hard_filter_selection import select_exclusions
from historical_common import aligned_labels, ancestor, check_files, config, identities, lock_files, native_el_predictions
from storage import certify

PRIVATE = D / "private/historical"
RECEIPTS = D / "receipts/historical"


def prepare():
    validate_seal(training=True)
    from prepare import checked_training_bytes

    checked_training_bytes("training_only_weights")
    ranks = {r["source_row_id"]: Fraction(r["rank_exact"]) for r in rows("training_only_weights")}
    spec = config()["hard_filter"]
    selections, summary = select_exclusions(rows("EL_train"), ranks, spec["selection_seeds"])
    if summary["excluded"] != spec["removed_positives"] or summary["eligible_positive"] != 63053:
        raise ValueError("Task 2.41-B target or excluded positive population differs")
    path = PRIVATE / "s10/exclusions.json"
    put(path, {"selections": selections, "summary": summary})
    lock_files(RECEIPTS / "s10_selection.json", [path])


def fit(arm):
    import numpy as np
    import torch

    validate_seal(training=True)
    training, validation = rows("EL_train"), rows("EL_validation")
    if arm != "A":
        check_files(RECEIPTS / "s10_selection.json")
        excluded = set(read(PRIVATE / "s10/exclusions.json")["selections"][arm])
        keep = [r for r in training if r["source_row_id"] not in excluded]
        if len(training)-len(keep) != len(excluded) or any(r["original_label"] != "1" for r in training
                                                        if r["source_row_id"] in excluded):
            raise ValueError("Historical filtering changed classes or lost identities")
        training = keep
    train_boundary()
    cfg = config()["el10"]
    put(RECEIPTS / f"{arm}_EL10_STARTED.json", {"arm": arm, "seed": cfg["seed"], "epochs": cfg["epochs"]})
    device = runner.runtime_device(torch, cfg)
    runner.seed_runtime(torch, np, cfg)
    enc = reuse.encodings_for(torch, resolved()["reference"])
    positives = sum(r["original_label"] == "1" for r in training)
    with runner.pinned_modules(resolved()) as (BigMHC, Dataset):
        model = runner.on_device(BigMHC(), device)
        initial = runner.state_hashes(model)
        rng = binding.rng_identity(torch, np)
        expected = {"state": initial, "rng": rng}
        if arm == "A":
            put(RECEIPTS / "EL10_initial.json", expected)
            with shared.preserve_rng(torch, np):
                shared.evaluate(torch, model, reuse.native_dataset(Dataset, enc, validation[:16]), device)
        elif expected != read(RECEIPTS / "EL10_initial.json"):
            raise ValueError("Hard-filter arm initialization differs from regenerated Task 2.23 A")
        train = baseline.AuditedDataset(reuse.native_dataset(Dataset, enc, training),
                                        [r["prepared_row_index"] for r in training])
        val = reuse.native_dataset(Dataset, enc, validation)
        optimizer = torch.optim.AdamW(model.parameters(), lr=cfg["learning_rate"])
        cumulative = 0
        for epoch in range(1, cfg["epochs"] + 1):
            stats = runner.train_epoch(torch, model, train, cfg, False, device, optimizer=optimizer)
            if (stats["optimization_steps"] != positives or
                    stats["optimizer_class_exposures"] != {"1": positives, "0": 16 * positives}):
                raise ValueError("Historical native sampler exposure differs")
            cumulative += stats["optimization_steps"]
            if shared.optimizer_steps(optimizer) != [cumulative] * 36:
                raise ValueError("Historical optimizer continuation differs")
            with shared.preserve_rng(torch, np):
                probabilities, val_bce = shared.evaluate(torch, model, val, device)
            result = {**baseline.el_metrics(validation, probabilities), "validation_BCE": val_bce,
                      "epoch": epoch, "arm": arm, "steps": cumulative}
            put(RECEIPTS / f"{arm}_epoch_{epoch:02d}.json", result)
            print(f"{arm} historical EL epoch {epoch} complete", flush=True)
        val_path = PRIVATE / f"el10/{arm}_EL_validation.json"
        put(val_path, probabilities)
        checkpoint = certify(torch, np, BigMHC, Dataset, model, enc, validation[:16],
                             D / f"checkpoints/historical_{arm}_EL10", device)
        checkpoint.update({"validation_sha256": sha(val_path), "epochs": cfg["epochs"],
                           "validation_metrics": result, "arm": arm, "seed": cfg["seed"]})
        put(RECEIPTS / f"{arm}_EL10.json", checkpoint)


def infer():
    import numpy as np
    import torch

    validate_seal(training=True)
    cfg = config()["el10"]
    runner.seed_runtime(torch, np, cfg)
    device = runner.runtime_device(torch, cfg)
    enc = reuse.encodings_for(torch, resolved()["reference"])
    cohort = identities("IMPROVE")
    output = []
    with runner.pinned_modules(resolved()) as (BigMHC, Dataset):
        for arm in metrics.ARMS:
            model = ancestor(torch, BigMHC, device, arm)
            scores = native_el_predictions(torch, Dataset, model, enc, cohort, device)
            path = PRIVATE / f"s10/{arm}_IMPROVE.jsonl"
            from stability_label_curation.replicate_stability_association import write_rows
            write_rows(path, ({**row, "raw_EL_logit": z, "EL_probability": p}
                              for row, (z, p) in zip(cohort, scores, strict=True)))
            output.append(path)
            del model
    lock_files(RECEIPTS / "s10_predictions.json", output)


def evaluate():
    validate_seal()
    check_files(RECEIPTS / "s10_predictions.json")
    cohort = identities("IMPROVE")
    predictions = {arm: records(PRIVATE / f"s10/{arm}_IMPROVE.jsonl") for arm in metrics.ARMS}
    labels = aligned_labels("IMPROVE", cohort)
    joined = metrics.join(cohort, predictions,
                          [{"source_id": r["source_id"], "label": y} for r, y in zip(cohort, labels, strict=True)])
    points = metrics.points(joined)
    if (points["n"], points["positive"], points["components"]) != (7788, 227, 38):
        raise ValueError("Historical S10 cohort census changed")
    cfg = config()["hard_filter"]
    intervals = metrics.paired_bootstrap(joined, seed=cfg["bootstrap_seed"], draws=cfg["draws"],
                                        evidence=PRIVATE / "s10/component_draws.jsonl.gz")
    val = rows("EL_validation")
    arm_points = []
    for arm in metrics.ARMS:
        path = PRIVATE / f"el10/{arm}_EL_validation.json"
        if sha(path) != read(RECEIPTS / f"{arm}_EL10.json")["validation_sha256"]:
            raise ValueError("Changed historical EL validation vector")
        result = baseline.el_metrics(val, read(path))
        role = {"A": "Unchanged EL reference", "H": "Low-stability positive-row deletion"}.get(
            arm, "Size-matched random positive-row removal")
        arm_points.append({"Publication record": f"P-{len(arm_points)+1:04d}", "Arm": arm,
                           "Arm description": role, "IM_AP": points["arms"][arm]["AP"],
                           "IM_AUROC": points["arms"][arm]["AUROC"], "EL_validation_AP": result["validation_AP"],
                           "EL_validation_AUROC": result["validation_AUROC"], "Macro_HLA_EL_AP": result["macro_HLA_AP"]})
    delta = []
    for i, (contrast, description, pilot, annotation) in enumerate((
        ("H-A", "H − A", points["arms"]["A"]["AP"], "Bottom 10% of EL positives removed; EL negatives intact"),
        ("H-mean_R", "H − mean(R1–R5)", points["mean_random_AP"],
         "Comparator = arithmetic mean of five arm APs, not score ensemble"),
    ), 11):
        ci = intervals["intervals"][contrast]["AP"]
        delta.append({"Publication record": f"P-{i:04d}", "Experiment / analysis": "Low-stability hard filtering with matched random removal",
                      "Panel": "D", "Strategy": "Low-stability positive hard deletion", "Contrast": description,
                      "Cohort": "IMPROVE", "n": points["n"], "IM+": points["positive"], "Control AP": pilot,
                      "Tested AP": points["arms"]["H"]["AP"], "Delta AP": points["contrasts"][contrast]["AP"],
                      "CI lower": ci["lower_95"], "CI upper": ci["upper_95"], "CI / analysis qualifier": annotation,
                      "Bootstrap units": intervals["components"], "Bootstrap attempts": intervals["attempts"]})
    put(PRIVATE / "s10/evaluation.json", {"IMPROVE": points, "intervals": intervals})
    csvout(D / "metrics/S_LowStability_Removal_7_Arms.csv", arm_points)
    csvout(D / "metrics/Historical_Deletion_Contrasts.csv", delta)
    lock_files(RECEIPTS / "s10_evaluation.json", [D / "metrics/S_LowStability_Removal_7_Arms.csv",
                                                  D / "metrics/Historical_Deletion_Contrasts.csv"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("step", choices=("prepare", "fit", "infer", "evaluate"))
    parser.add_argument("--arm", choices=metrics.ARMS)
    args = parser.parse_args()
    if args.step == "fit":
        if args.arm is None:
            parser.error("--arm is required for fit")
        fit(args.arm)
    else:
        {"prepare": prepare, "infer": infer, "evaluate": evaluate}[args.step]()
