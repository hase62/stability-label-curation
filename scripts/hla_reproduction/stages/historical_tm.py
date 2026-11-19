"""Task 2.35/2.37 ligand selection, adaptation, inference and S9 summaries."""
from __future__ import annotations

import gzip
import hashlib

from common import D, csvout, digest, native, put, read, records, resolved, reuse, rows, runner, sha, shared, train_boundary, validate_seal
from historical_common import aligned_labels, ancestor, check_files, config, forward, identities, lock_files, native_el_predictions
from prepare import raw_path
from stability_label_curation import measured_tm_direct_transfer as tm
from stability_label_curation import measured_tm_direct_transfer_evaluation as metrics
from stability_label_curation import measured_tm_preflight as source
from stability_label_curation.sequence_hamming import NearestNineIndex
from stability_label_curation.third_party_evaluation import WeightedRanking

PRIVATE = D / "private/historical/s9"
RECEIPTS = D / "receipts/historical"
COHORTS = {"IMPROVE": "IMPROVE", "neoepitope": "Neo"}


def select_panel(measured, train, positive_el, external, specification):
    hla = specification["treatment_hla"]
    idx = NearestNineIndex(external)
    protected = positive_el | {r["peptide"] for r in measured}
    candidates = [r for r in measured if r["hla"] == hla and r["canonical_ninemer"]]
    retained = [r for r in candidates if not source.sequence_excluded(r["peptide"], idx)]
    if (len(candidates), len(retained)) != (specification["measured_uncurated"], specification["measured"]):
        raise ValueError("Historical A*02:01 Tm selection population changed")
    pool = {}
    for r in train:
        if r["hla"] == hla and r["original_label"] == "0" and r["peptide"] not in protected:
            pool.setdefault(r["peptide"], r)
    def key(peptide):
        return hashlib.sha256(f"Task2.35-decoy-v1|{hla}|{peptide}".encode()).hexdigest(), hla, peptide
    chosen = []
    for peptide in sorted(pool, key=key):
        if not source.sequence_excluded(peptide, idx):
            chosen.append(pool[peptide])
            if len(chosen) == specification["decoys"]:
                break
    if len(chosen) != specification["decoys"] or digest([(r["hla"], r["peptide"]) for r in chosen]) != specification["decoy_ordered_pair_sha256"]:
        raise ValueError("Historical decoy identity or order changed")
    panel = [{**r, "kind": "measured", "sample_weight": specification["measured_weight"]} for r in retained]
    panel.extend({"peptide": r["peptide"], "hla": r["hla"], "source_id": r["source_row_id"],
                  "prepared_row_index": r["prepared_row_index"], "kind": "decoy", "target": 0.,
                  "sample_weight": specification["decoy_weight"]} for r in chosen)
    panel.sort(key=lambda r: r["source_id"])
    if any(len({r[key] for r in panel}) != len(panel) for key in ("source_id", "peptide")):
        raise ValueError("Historical ligand/decoy identities collided")
    return panel


def prepare():
    validate_seal(training=True)
    measured = []
    for role, hla in (("jappe_a02", source.HLAS[0]), ("jappe_b07", source.HLAS[1])):
        workbook = raw_path(role)
        number, count, ninemers, expected_sha = source.EXPECTED[hla]
        if workbook.name != f"41467_2020_20166_MOESM{number}_ESM.xlsx" or sha(workbook) != expected_sha:
            raise ValueError("Jappe workbook filename or contents differ")
        data, summary = source.measurement_rows(workbook, hla)
        if (summary["distinct_peptides"], summary["canonical_ninemers"]) != (count, ninemers):
            raise ValueError("Historical measurement source census changed")
        measured.extend(data)
    positives = D / "inputs/all_el_positive_peptides.txt.gz"
    training_receipt = read(D / "preflight/training_inputs_generated.json")["generated_sha256"]
    if sha(positives) != training_receipt[positives.name]:
        raise ValueError("Changed EL positive veto list")
    with gzip.open(positives, "rt", encoding="ascii") as stream:
        positive_el = {line.strip() for line in stream}
    external = set()
    for name in COHORTS.values():
        external.update(r["peptide"] for r in identities(name))
    cfg = config()["tm"]
    rows_out = select_panel(measured, rows("EL_train"), positive_el, external, cfg)
    path = PRIVATE / "training.jsonl"
    source.write_rows(path, rows_out)
    artifacts = [path]
    for seed in tm.SEEDS:
        targets, permutation = tm.target_vectors(rows_out, seed)
        for name, data in (("targets", targets), ("permutation", permutation),
                           ("orders", tm.orders(len(rows_out), seed, cfg["passes"]))):
            output = PRIVATE / f"{name}_{seed}.json"
            put(output, data)
            artifacts.append(output)
    lock_files(RECEIPTS / "s9_inputs.json", artifacts)


def fit():
    import numpy as np
    import torch

    validate_seal(training=True)
    check_files(RECEIPTS / "s9_inputs.json")
    train_boundary()
    put(RECEIPTS / "S9_STARTED.json", {"objective": "historical measured Tm", "conditions": tm.CONDITIONS})
    cfg = config()["tm"]
    runtime = dict(config()["el10"], seed=123)
    device = tm.runtime(torch, np, runtime)
    enc = reuse.encodings_for(torch, resolved()["reference"])
    rows_in = records(PRIVATE / "training.jsonl")
    weights = torch.tensor([r["sample_weight"] for r in rows_in], dtype=torch.float32, device=device)
    if len(rows_in) != 12070 or float(weights.sum()) != 22720:
        raise ValueError("Historical treatment population or weight mass differs")
    artifacts = []
    with runner.pinned_modules(resolved()) as (BigMHC, Dataset):
        encoded = {k: v.to(device) for k, v in tm.encode_inputs(torch, Dataset, enc, rows_in, cfg["batch_size"]).items()}
        for seed in tm.SEEDS:
            targets = read(PRIVATE / f"targets_{seed}.json")
            orders = read(PRIVATE / f"orders_{seed}.json")
            for arm in tm.ADAPTED:
                native.reset(torch, np, seed)
                model = ancestor(torch, BigMHC, device)
                tm.freeze_output_only(model)
                initial = runner.state_hashes(model)
                optimizer = torch.optim.AdamW([v for v in model.parameters() if v.requires_grad],
                                              **{**cfg["optimizer"], "betas": tuple(cfg["optimizer"]["betas"])})
                y = torch.tensor(targets[arm], dtype=torch.float32, device=device)
                condition = f"{arm}_{seed}"
                updates = 0
                for epoch, order in enumerate(orders, 1):
                    losses = []
                    for offset in range(0, len(order), cfg["batch_size"]):
                        idx = torch.tensor(order[offset:offset + cfg["batch_size"]], dtype=torch.int64, device=device)
                        optimizer.zero_grad(set_to_none=True)
                        logits, _ = model(encoded["mhc"][idx], encoded["pep"][idx])
                        loss = tm.balanced_loss(torch, logits, y[idx], weights[idx])
                        loss.backward()
                        optimizer.step()
                        updates += 1
                        losses.append(loss.detach())
                    if any(m.training for m in model.modules()) or not torch.isfinite(torch.stack(losses)).all():
                        raise ValueError("Historical balanced-loss state changed or diverged")
                    put(RECEIPTS / f"s9_{condition}_pass_{epoch:02d}.json",
                        {"pass": epoch, "updates": updates, "mean_batch_BCE": float(torch.stack(losses).mean())})
                trained = runner.state_hashes(model)
                if {k for k in trained if trained[k] != initial[k]} != set(tm.OUTPUT_KEYS) or updates != 3780:
                    raise ValueError("Historical output-only transfer or update count differs")
                if shared.optimizer_steps(optimizer) != [updates] * len(tm.OUTPUT_KEYS):
                    raise ValueError("Historical persistent AdamW step count differs")
                path = D / f"checkpoints/historical_tm/{condition}.pt"
                tm.save_tensors(torch, path, {k: v.detach().cpu() for k, v in model.state_dict().items() if k in tm.OUTPUT_KEYS})
                restored = ancestor(torch, BigMHC, device)
                tm.replace_output(torch, restored, torch.load(path, map_location=device, weights_only=True))
                if runner.state_hashes(restored) != trained:
                    raise ValueError("Historical output checkpoint reload differs")
                artifacts.append(path)
                del restored, model, optimizer
    lock_files(RECEIPTS / "s9_fits.json", artifacts)


def infer():
    import numpy as np
    import torch

    validate_seal(training=True)
    check_files(RECEIPTS / "s9_fits.json")
    cfg = config()["tm"]
    device = tm.runtime(torch, np, dict(config()["el10"], seed=123))
    enc = reuse.encodings_for(torch, resolved()["reference"])
    cohorts = {name: identities(key) for name, key in COHORTS.items()}
    artifacts = []
    with runner.pinned_modules(resolved()) as (BigMHC, Dataset):
        encoded = {key: {k: v.to(device) for k, v in tm.encode_inputs(torch, Dataset, enc, rr, 16).items()}
                   for key, rr in cohorts.items()}
        for condition in tm.CONDITIONS:
            model = ancestor(torch, BigMHC, device)
            if condition != "A":
                path = D / f"checkpoints/historical_tm/{condition}.pt"
                tm.replace_output(torch, model, torch.load(path, map_location=device, weights_only=True))
                model.eval()
            for name, rr in cohorts.items():
                scores = (native_el_predictions(torch, Dataset, model, enc, rr, device) if condition == "A"
                          else forward(torch, model, encoded[name], rr, cfg["inference_batch_size"]))
                output = PRIVATE / f"{name}_{condition}.jsonl"
                source.write_rows(output, ({"source_id": r["source_id"], "native_logit": z, "score": p}
                                           for r, (z, p) in zip(rr, scores, strict=True)))
                artifacts.append(output)
            del model
    lock_files(RECEIPTS / "s9_predictions.json", artifacts)


def evaluate():
    validate_seal()
    check_files(RECEIPTS / "s9_predictions.json")
    cfg = config()["tm"]
    joined = {}
    for name, key in COHORTS.items():
        rr = identities(key)
        labels = aligned_labels(key, rr)
        predictions = {}
        for condition in tm.CONDITIONS:
            preds = records(PRIVATE / f"{name}_{condition}.jsonl")
            native.assert_alignment([r["source_id"] for r in rr], [r["source_id"] for r in preds])
            predictions[condition] = preds
        joined[name] = [{**r, "label": y, "peptide_component": r["peptide"],
                         "scores": {condition: preds[i]["score"] for condition, preds in predictions.items()}}
                        for i, (r, y) in enumerate(zip(rr, labels, strict=True))]
    populations = {"IMPROVE_A02": [r for r in joined["IMPROVE"] if r["hla"] == cfg["treatment_hla"]],
                   "IMPROVE_full": joined["IMPROVE"], "neoepitope": joined["neoepitope"]}
    output = []
    for cohort, rr in populations.items():
        field = "peptide_component" if cohort == "neoepitope" else "patient_peptide_component"
        expected = {"IMPROVE_A02": (616, 21, 16), "IMPROVE_full": (7788, 227, 38), "neoepitope": (267, 57, 265)}
        if (len(rr), sum(r["label"] for r in rr), len({r[field] for r in rr})) != expected[cohort]:
            raise ValueError("Historical S9 evaluation population changed")
        p = metrics.point(rr)
        u = metrics.bootstrap(rr, {c: WeightedRanking(rr, c) for c in tm.CONDITIONS}, field,
                              cfg["bootstrap_seeds"][cohort], cfg["draws"], PRIVATE / f"{cohort}_draws.jsonl.gz")
        put(PRIVATE / f"{cohort}_evaluation.json", {"point": p, "intervals": u})
        for other in (("P", "A", "D") if cohort == "IMPROVE_A02" else ("A", "P", "D")):
            contrast = "T-" + other
            comparison = u["confidence_intervals"][contrast]["AP"]
            use = "protocol-defined primary" if cohort == "IMPROVE_A02" and other == "P" else "secondary descriptive"
            output.append({"Publication record": f"P-{1+len(output):04d}",
                           "Experiment / analysis": "Measured-Tm output-layer transfer", "Section": use,
                           "Cohort": cohort, "Stage": "IM", "Contrast": f"T_seed_mean - {other}_seed_mean",
                           "Baseline": other + "_seed_mean", "Intervention": "T_seed_mean",
                           "N": len(rr), "Positive": sum(r["label"] for r in rr),
                           "AP baseline": p["seed_means"][other]["AP"], "AP intervention": p["seed_means"]["T"]["AP"],
                           "Saved delta AP": p["seed_mean_paired_contrasts"][contrast]["AP"],
                           "CI lower": comparison["lower_95"], "CI upper": comparison["upper_95"],
                           "Bootstrap unit": u["components"], "Bootstrap attempts": u["draws_executed"],
                           "Evidence": "REGENERATED_FROM_PINNED_ORIGINALS", "Manuscript_use": use,
                           "CI_method_saved": "paired components; seed-mean contrast",
                           "Training_independence": "NOT_CLAIMED",
                           "Patient_assay_independence": "Not established from peptide groups",
                           "Verification": "Matched frozen source identities, outcomes and components",
                           "CI_missing_reason": "No valid draws" if comparison["lower_95"] is None else ""})
    path = D / "metrics/S_Thermal_Transfer_9.csv"
    csvout(path, output)
    lock_files(RECEIPTS / "s9_evaluation.json", [path])


if __name__ == "__main__":
    import sys

    {"prepare": prepare, "fit": fit, "infer": infer, "evaluate": evaluate}[sys.argv[1]]()
