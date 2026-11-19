"""Generate the optional designated-HLA MixMHCpred diagnostic from the pinned release."""
from __future__ import annotations

import csv
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tarfile

from common import D, csvout, native, put, records, sha, validate_seal
from prepare import raw_path


def mix_allele(allele):
    return allele.removeprefix("HLA-").replace("*", "").replace(":", "")


def parse_scores(path, peptides, allele):
    with path.open(encoding="utf-8") as stream:
        payload = "\n".join(line for line in stream.read().splitlines() if line.strip() and not line.startswith("#"))
    reader = csv.DictReader(io.StringIO(payload), delimiter="\t")
    score_column = "Score_" + mix_allele(allele)
    rank_column = "%Rank_" + mix_allele(allele)
    if not {"Peptide", score_column, rank_column} <= set(reader.fieldnames or []):
        raise ValueError("Missing designated-HLA columns")
    for peptide, row in zip(peptides, reader, strict=True):
        score, rank = float(row[score_column]), float(row[rank_column])
        if row["Peptide"] != peptide or not math.isfinite(score) or not math.isfinite(rank) or not 0 <= rank <= 100:
            raise ValueError("MixMHCpred row alignment or finite score contract failed")
        yield score


def score_model():
    validate_seal(training=True)
    root = D / "private/mix"
    root.mkdir(mode=0o700)
    archive = raw_path("mix")
    with tarfile.open(archive, mode="r:gz") as tar:
        members = tar.getmembers()
        if any(not (member.isdir() or member.isfile()) for member in members):
            raise ValueError("Unexpected special file or link in authenticated Mix release")
        tar.extractall(root, members=members, filter="data")
    launcher = root / "MixMHCpred-0a7f9b9e20d1cf02236f4a0a90d16735be879b38/MixMHCpred"
    env = {**os.environ, "PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ["PATH"]}
    identities = records(D / "cohorts/IMPROVE_identities.jsonl")
    per_key = {}
    for allele in sorted({r["hla"] for r in identities}):
        slug = mix_allele(allele)
        subset = [r for r in identities if r["hla"] == allele]
        peps = [r["peptide"] for r in subset]
        source, result = root / (slug + ".txt"), root / (slug + ".tsv")
        with source.open("x", encoding="ascii") as stream:
            stream.writelines(p + "\n" for p in peps)
        with (root / (slug + ".log")).open("x", encoding="utf-8") as log:
            subprocess.run(["bash", str(launcher), "-i", str(source), "-o", str(result), "-a", slug, "-m", "0"],
                           check=True, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT)
        for row, score in zip(subset, parse_scores(result, peps, allele), strict=True):
            per_key[row["source_id"]] = {"source_id": row["source_id"], "peptide": row["peptide"],
                                        "hla": allele, "mix_el_native": score}
    score_path = root / "mix_native.jsonl"
    with score_path.open("x", encoding="utf-8") as stream:
        for row in identities:
            stream.write(json.dumps(per_key[row["source_id"]], sort_keys=True, allow_nan=False) + "\n")
    put(root / "frozen.json", {"scores_sha256": sha(score_path), "rows": len(per_key), "outcome_access": False})


def evaluate():
    import numpy as np
    from evaluate_main import WeightedRanking, average_precision_score, fractional_precision, frozen_cohort, roc_auc_score

    validate_seal()
    root = D / "private/mix"
    path = root / "mix_native.jsonl"
    freeze = root / "frozen.json"
    if sha(path) != json.loads(freeze.read_text())["scores_sha256"]:
        raise ValueError("Mix scores changed after freeze")
    identities, labels = frozen_cohort("IMPROVE")
    scores = records(path)
    native.assert_alignment([r["source_id"] for r in identities], [r["source_id"] for r in scores])
    for row, p in zip(identities, scores, strict=True):
        if (row["peptide"], row["hla"]) != (p["peptide"], p["hla"]):
            raise ValueError("Mix scored identity differs")
    values = [float(p["mix_el_native"]) for p in scores]
    ranking = WeightedRanking([{**r, "scores": {"mix": score}, "label": y}
                               for r, score, y in zip(identities, values, labels, strict=True)], "mix")
    expected = ranking.metrics(np.ones(len(scores), dtype=np.int64), top_k=False)
    result = {"AP": float(average_precision_score(labels, values)), "AUROC": float(roc_auc_score(labels, values)),
              "PPV10": fractional_precision(labels, values, 10), "PPV20": fractional_precision(labels, values, 20)}
    if not all(math.isclose(result[k], expected[k], rel_tol=0, abs_tol=1e-10) for k in ("AP", "AUROC")):
        raise ValueError("Independent Mix rank metric implementations disagree")
    csvout(D / "metrics/MIX_SAVED_REFERENCE_DIAGNOSTIC.csv", [{
        "cohort": "IMPROVE", "n": len(labels), "positive": sum(labels),
        "model": "MixMHCpred v3.0 native designated-HLA score", "prediction_SHA256": sha(path),
        "source_freeze_SHA256": sha(freeze), "identity_alignment": "same exact full7788 observations",
        **result, "score_min": min(values), "score_max": max(values),
        "score_outside_unit_interval_n": sum(not 0 <= v <= 1 for v in values),
        "interpretation": "descriptive comparison with fixed native scores, higher is stronger",
    }])


if __name__ == "__main__":
    {"score": score_model, "evaluate": evaluate}[sys.argv[1]]()
