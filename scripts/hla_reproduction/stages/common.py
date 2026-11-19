"""Runtime paths for the authenticated EL20→IM30 stage implementations."""
from __future__ import annotations

from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import time

from stability_label_curation.paths import resolve_paths
from stability_label_curation import hla_extended_epochs as native
from stability_label_curation import bigmhc_baseline_runner as runner
from stability_label_curation import bigmhc_el_multiepoch as baseline
from stability_label_curation import bigmhc_multiepoch as shared
from stability_label_curation import bigmhc_fully_trained_auxiliary as reuse
from stability_label_curation import bigmhc_el_positive_upweighting as prior
from stability_label_curation import el_stability_loss_adapter as binding
from stability_label_curation import el_only_zero_shot_im as scoring

D = Path(__file__).resolve().parents[1]
P = resolve_paths(repository_root=Path(os.environ.get("HLA_REPRO_REPOSITORY", Path(__file__).resolve().parents[3])))
W = {"official_download_dir": os.environ.get("HLA_REPRO_OFFICIAL_DIR")}
ARMS = ("A", "W_two", "L", "W_two_perm", "L_perm", "L_const")
SEEDS = (42, 123, 456)
CONTRASTS = (("W_two-A", "W_two", "A"), ("L-A", "L", "A"),
             ("W_two-W_two_perm", "W_two", "W_two_perm"),
             ("L-L_perm", "L", "L_perm"), ("L-L_const", "L", "L_const"))

def utc():
    return datetime.now(timezone.utc).isoformat()

def sha(path):
    return runner.raw.sha256_file(Path(path))

def read(path):
    return json.loads(Path(path).read_text())

def digest(value):
    return scoring.digest(value)

def put(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())

def atomic(path, value):
    temporary = path.with_name(path.name + f".pending.{os.getpid()}")
    put(temporary, value)
    os.replace(temporary, path)

def csvout(path, rows):
    fields = list(dict.fromkeys(key for row in rows for key in row))
    with Path(path).open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

def context():
    return read(D / "preflight/authenticated_context.json")

def resolved():
    return {key: Path(entry["path"]) for key, entry in context()["native_inputs"].items()}

def rows(name):
    return native.load_rows(D / "inputs" / f"{name}.csv.gz")

def records(path):
    with Path(path).open(encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]

def validate_seal(*, training=False):
    seal = read(D / "preflight/PRETRAINING_PROTOCOL_SEAL.json")
    if seal["status"] != "PASS":
        raise ValueError("Protocol seal did not pass")
    hashes = dict(seal["source_hashes"], **seal["input_hashes"])
    if not training:
        hashes.update(seal["evaluation_hashes"])
    for relative, expected in hashes.items():
        if sha(D / relative) != expected:
            raise ValueError(f"Run file changed: {relative}")
    for relative, expected in seal["native_hashes"].items():
        if sha(P.repository_root / relative) != expected:
            raise ValueError(f"Native source changed: {relative}")
    for entry in context()["native_inputs"].values():
        if sha(entry["path"]) != entry["sha256"]:
            raise ValueError("External native input changed")
    return seal

def commands():
    with (D / "logs/commands.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({"UTC": utc(), "argv": [sys.executable, *sys.argv]}) + "\n")

def train_boundary():
    """Reject evaluation access and writes to existing project storage from a fit."""
    log = (D / "logs" / f"file_access_{os.getpid()}.jsonl").open("x", encoding="utf-8")
    busy = False

    def hook(event, args):
        nonlocal busy
        if event != "open" or busy or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = Path(os.fsdecode(args[0])).resolve()
        mode, flags = args[1:3]
        write = (isinstance(mode, str) and any(char in mode for char in "wax+")
                 or isinstance(flags, int) and flags >= 0
                 and bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)))
        evaluation = any(path.is_relative_to(D / name) for name in ("cohorts", "private/predictions", "private/official_predictions", "private/mix"))
        protected = any(path.is_relative_to(root) for root in (P.codex_root, P.project_data_dir, P.project_runs_dir, P.repository_root))
        forbidden = evaluation or (write and protected and not path.is_relative_to(D))
        if protected or evaluation:
            busy = True
            try:
                log.write(json.dumps({"path": str(path), "write": bool(write), "denied": bool(forbidden),
                                      "evaluation_access": evaluation}) + "\n")
                log.flush()
            finally:
                busy = False
        if forbidden:
            raise PermissionError(f"Training storage boundary: {path}")

    sys.addaudithook(hook)
    return log
