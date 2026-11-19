"""Orchestrate fresh, version-pinned HLA EL20→IM30 results in a new run."""
from __future__ import annotations

import argparse
from collections import Counter
import fcntl
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT / "src"))
from stability_label_curation.paths import resolve_paths

CONFIG = ROOT / "configs/hla_reproduction"
WRAPPERS = Path(__file__).resolve().parent / "stages"
ARM_ORDER = ("A", "W_two", "L", "W_two_perm", "L_perm", "L_const")
SEEDS = (42, 123, 456)
LAYOUT = ("config", "scripts", "preflight", "inputs", "cohorts", "controls_private", "logs",
          "private", "resume", "checkpoints", "receipts", "metrics", "figures", "reports")
GRAPH = {
    "init": ([], ["preflight/checkout.json", "config/expected.json", "scripts/"]),
    "verify-assets": (["preflight/checkout.json"], ["preflight/raw_inputs.json"]),
    "teacher": (["preflight/raw_inputs.json#dtu"], ["preflight/teacher_generated.json", "inputs/teacher.json", "inputs/teacher_partition.json"]),
    "teacher-sensitivity": (["preflight/teacher_generated.json"], ["metrics/STABILITY_TEACHER_ZERO_SENSITIVITY_REPORTED.csv"]),
    "prepare": (["preflight/teacher_generated.json", "preflight/raw_inputs.json#bigmhc_v4,reference"],
                ["preflight/training_inputs_generated.json", "inputs/{EL_train,EL_validation,IM_train}.csv.gz"]),
    "cohorts": (["preflight/training_inputs_generated.json", "preflight/raw_inputs.json#improve,improve_crosscheck"],
                ["preflight/cohorts_generated.json", "cohorts/{Neo,IMPROVE}_{identities,outcomes}.jsonl"]),
    "controls": (["preflight/training_inputs_generated.json", "preflight/teacher_generated.json"],
                 ["preflight/control_preparation_audit.json", "controls_private/positive_control_weights_seed{seed}.csv.gz"]),
    "seal": (["preflight/cohorts_generated.json", "preflight/control_preparation_audit.json"],
             ["preflight/initializations.json", "preflight/PRETRAINING_PROTOCOL_SEAL.json"]),
    "train": (["preflight/PRETRAINING_PROTOCOL_SEAL.json"],
              ["receipts/{arm}_{seed}_completed.json", "metrics/epochs/*.json", "checkpoints/"]),
    "infer": (["receipts/{arm}_{seed}_completed.json", "preflight/PRETRAINING_PROTOCOL_SEAL.json"],
              ["receipts/{arm}_{seed}_predictions_frozen.json", "private/predictions/*.jsonl"]),
    "official": (["preflight/PRETRAINING_PROTOCOL_SEAL.json", "preflight/official_acquisition.json"],
                 ["receipts/OFFICIAL_PREDICTIONS_FROZEN.json", "private/official_predictions/*.jsonl"]),
    "mix-score": (["preflight/PRETRAINING_PROTOCOL_SEAL.json", "preflight/raw_inputs.json#mix"],
                   ["private/mix/mix_native.jsonl", "private/mix/frozen.json"]),
    "mix-evaluate": (["private/mix/frozen.json", "preflight/PRETRAINING_PROTOCOL_SEAL.json"],
                     ["metrics/MIX_SAVED_REFERENCE_DIAGNOSTIC.csv"]),
    "official-exposure": (["preflight/PRETRAINING_PROTOCOL_SEAL.json", "preflight/raw_inputs.json#bigmhc_v4"],
                          ["metrics/OFFICIAL_PUBLIC_DATA_EXPOSURE.csv"]),
    "supplement": (["receipts/{arm}_{seed}_predictions_frozen.json", "preflight/cohorts_generated.json"],
                   ["metrics/ACTUAL_DEVELOPMENT_OVERLAP_EVIDENCE.csv", "metrics/NEO_EL20_AUROC_PAIR_DECOMPOSITION.csv"]),
    "evaluate": (["receipts/{arm}_{seed}_predictions_frozen.json"],
                 ["metrics/MAIN_72_METRICS.csv", "metrics/MAIN_CONDITIONAL_CI.csv", "private/bootstrap/*.jsonl.gz"]),
    "qa": (["metrics/MAIN_72_METRICS.csv", "metrics/epochs/*.json"],
           ["reports/FINAL_QA.json", "metrics/ALL900_EPOCH_METRICS.csv"]),
    "figures": (["reports/FINAL_QA.json", "metrics/ALL900_EPOCH_METRICS.csv"],
                ["figures/FIGURE_TABLE_SOURCE_MAP.csv", "figures/*_SOURCE.csv", "figures/manuscript/*.pdf"]),
}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True)
        stream.write("\n")


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def need(condition, explanation: str) -> None:
    if not condition:
        raise ValueError(explanation)


def git(*args: str) -> str:
    return subprocess.check_output(["git", "--no-optional-locks", "-C", str(ROOT), *args], text=True).strip()


def launch(path: Path, url: str, expected: str) -> None:
    if path.is_file():
        need(sha(path) == expected, f"Existing original source has wrong SHA256: {path}")
        return
    need(url.startswith("https://"), "Pinned source must use HTTPS")
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + ".download")
    with pending.open("xb") as target, urlopen(url, timeout=60) as stream:
        need(stream.geturl().startswith("https://"), "Source redirected outside HTTPS")
        shutil.copyfileobj(stream, target, 1024 * 1024)
    need(sha(pending) == expected, f"Downloaded SHA256 differs; preserved: {pending}")
    # Publish by no-clobber hard link. Preserve the acquisition staging name.
    os.link(pending, path)


def safe_asset(path: Path, storage) -> Path:
    path = path.expanduser().resolve()
    need(path.is_relative_to(storage.project_data_dir), f"Store the immutable original under project data: {path}")
    return path


def acquire(args, storage) -> None:
    sources = read(CONFIG / "sources.json")
    for role in args.role:
        spec = sources[role]
        base = safe_asset(storage.project_data_dir / spec["path"], storage)
        if role == "bigmhc_code":
            catalog = read(CONFIG / spec["manifest"])
            for f in catalog["files"]:
                relative = f["path"]
                if relative.startswith("models/") and not args.with_official_weights:
                    continue
                launch(safe_asset(base / relative, storage), spec["url_template"].format(path=relative), f["sha256"])
        elif "url" in spec:
            launch(base, spec["url"], spec["sha256"])
        else:
            print(f"{role}: {spec['access']} {spec['landing']}")


def verified_assets(args, storage, run: Path) -> None:
    specs = read(CONFIG / "sources.json")
    overrides = {}
    for arg in args.asset:
        role, separator, value = arg.partition("=")
        need(bool(separator and value) and role in specs and role not in overrides, f"Invalid source override: {role}")
        overrides[role] = Path(value)
    verified = {}
    missing = []
    for role, spec in specs.items():
        base = safe_asset(overrides.get(role, storage.project_data_dir / spec["path"]), storage)
        if role == "bigmhc_code":
            catalog = read(CONFIG / spec["manifest"])
            acquired = []
            for file in catalog["files"]:
                name = file["path"]
                if name.startswith("models/") and not args.with_official_weights:
                    continue
                path = safe_asset(base / name, storage)
                if not path.is_file():
                    missing.append(f"{role}:{name}")
                    continue
                need(sha(path) == file["sha256"] and path.stat().st_size == file["bytes"], f"Wrong pinned BigMHC bytes: {name}")
                acquired.append(file)
                key = "reference" if name == "data/pseudoseqs.csv" else "source_" + Path(name).stem
                if not name.startswith("models/"):
                    verified[key] = {"path": str(path), "sha256": file["sha256"]}
            if args.with_official_weights and len(acquired) == len(catalog["files"]):
                write(run / "preflight/official_acquisition.json", {
                    "status": "PASS", "commit": catalog["commit"], "root": str(base), "files": acquired,
                })
        elif not base.is_file():
            missing.append(role)
        else:
            need(sha(base) == spec["sha256"], f"Wrong SHA256: {role}")
            verified[role] = {"path": str(base), "sha256": spec["sha256"]}
    target = run / "preflight/raw_inputs.json"
    if target.exists():
        earlier = read(target)
        need(all(verified.get(k) == v for k, v in earlier.items()), "Previously authenticated inputs changed")
        temp = target.with_suffix(".next")
        write(temp, verified)
        os.replace(temp, target)
    else:
        write(target, verified)
    print(json.dumps({"verified_roles": sorted(verified), "missing": missing}, indent=2))


def sources_identity() -> dict[str, str]:
    files = sorted(WRAPPERS.glob("*.py")) + sorted(f for f in CONFIG.iterdir() if f.is_file())
    files += [Path(__file__).resolve()]
    return {str(p.relative_to(ROOT)): sha(p) for p in files}


def init(run: Path) -> None:
    need(not git("status", "--porcelain", "--untracked-files=normal"), "Initialize from a clean fixed checkout")
    contract = read(CONFIG / "02_EXPERIMENT_CONTRACT.json")
    execution = read(CONFIG / "EXECUTION_CONFIG.json")
    schedule = [[arm, seed] for seed in SEEDS for arm in ARM_ORDER]
    need(execution["execution_order"] == schedule and contract["arms"] == list(ARM_ORDER)
         and contract["seeds"] == list(SEEDS) and contract["training"]["EL_epochs"] == 20
         and contract["training"]["IM_epochs"] == 30, "Frozen experiment schedule changed")
    expected = read(CONFIG / "expected.json")["native_scientific_hashes"]
    for relative, digest in expected.items():
        need(sha(ROOT / relative) == digest, f"Authenticated native source differs: {relative}")
    run.mkdir(mode=0o700, exist_ok=False, parents=True)
    for directory in LAYOUT:
        (run / directory).mkdir(mode=0o700)
    for folder, files in (("config", CONFIG.iterdir()), ("scripts", WRAPPERS.glob("*.py"))):
        for path in files:
            if path.is_file():
                shutil.copyfile(path, run / folder / path.name)
    write(run / "preflight/checkout.json", {
        "git_commit": git("rev-parse", "HEAD"), "scientific_native_hashes": expected, "recipe_hashes": sources_identity(),
        "copied_hashes": {str(p.relative_to(run)): sha(p) for name in ("scripts", "config") for p in (run / name).iterdir()},
    })


def check_checkout(run: Path) -> None:
    receipt = read(run / "preflight/checkout.json")
    need(git("rev-parse", "HEAD") == receipt["git_commit"], "Checkout commit differs from run initialization")
    need(sources_identity() == receipt["recipe_hashes"], "Recipe differs from initialized source")
    for relative, expected in receipt["copied_hashes"].items():
        need(sha(run / relative) == expected, f"Run recipe file changed: {relative}")
    for relative, expected in receipt["scientific_native_hashes"].items():
        need(sha(ROOT / relative) == expected, f"Native code changed: {relative}")


def worker(run: Path, script: str, *arguments: str, official_dir: str | None = None) -> None:
    env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "PYTHONDONTWRITEBYTECODE": "1",
           "HLA_REPRO_REPOSITORY": str(ROOT), "MPLCONFIGDIR": str(run / "private/matplotlib_config"),
           "CUBLAS_WORKSPACE_CONFIG": ":4096:8"}
    if official_dir is not None:
        env["HLA_REPRO_OFFICIAL_DIR"] = official_dir
    for key in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "BLIS_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS", "NUMEXPR_NUM_THREADS"):
        env[key] = "1"
    subprocess.run([sys.executable, str(run / "scripts" / script), *arguments], cwd=run, env=env, check=True)


def make_seal(run: Path) -> None:
    raw = read(run / "preflight/raw_inputs.json")
    active = {k: v for k, v in raw.items() if k == "reference" or k.startswith("source_")}
    need({"reference", "source_bigmhc", "source_dataset", "source_mhcuid", "source_encseq"} <= set(active),
         "Missing native source or HLA reference")
    prepared = read(run / "preflight/training_inputs_generated.json")
    control = read(run / "preflight/control_preparation_audit.json")
    populations = read(run / "preflight/cohorts_generated.json")
    for name, expected in prepared["generated_sha256"].items():
        need(sha(run / "inputs" / name) == expected, f"Generated training input changed: {name}")
    for seed in control["seed_audits"]:
        need(sha(run / f"controls_private/positive_control_weights_seed{seed['seed']}.csv.gz") == seed["sha256"],
             "Generated controls changed")
    for cohort, fields in populations.items():
        for part in ("identities", "outcomes"):
            need(sha(run / f"cohorts/{cohort}_{part}.jsonl") == fields[f"{'identity' if part == 'identities' else 'outcome'}_sha256"],
                 "Generated evaluation input changed")
    write(run / "preflight/authenticated_context.json", {
        "native_inputs": active, "native_training_config": read(run / "config/native_runtime.json"),
        "cohorts": populations, "populations": prepared["counts"], "epoch_budgets": {"EL": 20, "IM": 30},
        "teacher_original_sha256": read(run / "config/expected.json")["teacher_original_sha256"],
    })
    worker(run, "preflight_model_gate.py")
    preflight_names = ("authenticated_context.json", "initializations.json", "model_storage_and_integration_gate.json")
    write(run / "preflight/PRETRAINING_PROTOCOL_SEAL.json", {
        "status": "PASS",
        "native_hashes": read(run / "preflight/checkout.json")["scientific_native_hashes"],
        "source_hashes": read(run / "preflight/checkout.json")["copied_hashes"],
        "input_hashes": {str(p.relative_to(run)): sha(p) for p in (
            *(run / f"inputs/{n}.csv.gz" for n in ("EL_train", "EL_validation", "IM_train")),
            *(run / "controls_private").glob("positive_control_weights_seed*.csv.gz"),
            *(run / "preflight" / n for n in preflight_names)) if p.is_file()},
        "evaluation_hashes": {str(p.relative_to(run)): sha(p) for p in (run / "cohorts").glob("*.jsonl")},
    })


def jobs(run: Path, phase: str) -> None:
    if phase == "infer":
        for seed in SEEDS:
            for arm in ARM_ORDER:
                receipt = run / "receipts" / f"{arm}_{seed}_completed.json"
                need(receipt.is_file() and read(receipt)["status"] == "COMPLETE", f"Fit incomplete: {arm}_{seed}")
    for seed in SEEDS:
        for arm in ARM_ORDER:
            prefix = f"{arm}_{seed}"
            completed = run / "receipts" / f"{prefix}_completed.json"
            if phase == "train":
                if completed.is_file() and read(completed)["status"] == "COMPLETE":
                    continue
                need(not any((run / "receipts" / f"{prefix}_{state}.json").exists() for state in ("started", "FAILED")),
                     f"{prefix} previously started; inspect preserved failure and checkpoint/resume receipts")
                script = "train_main.py"
            else:
                need(completed.is_file() and read(completed)["status"] == "COMPLETE", f"Fit incomplete: {prefix}")
                if (run / "receipts" / f"{prefix}_predictions_frozen.json").is_file():
                    continue
                script = "infer_main.py"
            worker(run, script, "--arm", arm, "--seed", str(seed))


def dispatch(args, run: Path, storage) -> None:
    if args.phase == "verify-assets":
        verified_assets(args, storage, run)
    elif args.phase in ("teacher", "prepare", "cohorts", "controls"):
        worker(run, "prepare.py", args.phase)
    elif args.phase == "teacher-sensitivity":
        worker(run, "teacher_sensitivity.py")
    elif args.phase == "seal":
        make_seal(run)
    elif args.phase in ("train", "infer"):
        jobs(run, args.phase)
    elif args.phase == "official":
        stage = read(run / "preflight/official_acquisition.json")
        worker(run, "official_diagnostic.py", official_dir=stage["root"])
    elif args.phase in ("mix-score", "mix-evaluate"):
        worker(run, "mix_diagnostic.py", "score" if args.phase == "mix-score" else "evaluate")
    elif args.phase == "official-exposure":
        worker(run, "official_exposure.py")
    elif args.phase == "supplement":
        worker(run, "supplement.py")
    elif args.phase == "evaluate":
        worker(run, "evaluate_main.py")
    elif args.phase == "qa":
        worker(run, "verify_saved_results.py")
    elif args.phase == "figures":
        worker(run, "render_main.py")
        worker(run, "plot_manuscript.py", str(run / "figures"), str(run / "figures/manuscript"))


def verify_environment(role: str) -> None:
    need(sys.version_info[:3] == (3, 13, 5), "Use the pinned Python 3.13.5 interpreter")
    for line in (CONFIG / f"requirements-{role}.txt").read_text().splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, expected = line.split("==")
        try:
            observed = metadata.version(name)
        except metadata.PackageNotFoundError:
            observed = "MISSING"
        need(observed == expected, f"{role} environment {name}: expected {expected}, found {observed}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("phase", choices=(*GRAPH, "plan", "acquire"))
    parser.add_argument("--run", type=Path)
    parser.add_argument("--asset", action="append", default=[], metavar="ROLE=ABSOLUTE_PATH")
    parser.add_argument("--role", action="append", default=[], choices=list(read(CONFIG / "sources.json")))
    parser.add_argument("--with-official-weights", action="store_true")
    args = parser.parse_args(argv)
    if args.phase == "plan":
        print(json.dumps({"stages": GRAPH, "frozen_experiment": read(CONFIG / "expected.json")["known_outputs"],
                          "existing_run_input_required": False}, indent=2))
        return 0
    if args.asset and args.phase != "verify-assets":
        parser.error("--asset applies only to verify-assets")
    storage = resolve_paths(repository_root=ROOT)
    if args.phase == "acquire":
        if not args.role:
            parser.error("acquire requires explicit --role selection")
        acquire(args, storage)
        return 0
    if args.run is None:
        parser.error("--run is required")
    run = args.run.expanduser().resolve()
    need(run.parent == storage.project_runs_dir, f"Use a new direct child of {storage.project_runs_dir}")
    roles = {"teacher": "teacher", "teacher-sensitivity": "cpu", "cohorts": "cpu",
             "seal": "gpu", "train": "gpu", "infer": "gpu", "official": "gpu",
             "mix-score": "mix", "mix-evaluate": "cpu", "evaluate": "cpu", "qa": "cpu", "figures": "render"}
    if args.phase in roles:
        verify_environment(roles[args.phase])
    if args.phase == "init":
        init(run)
    else:
        check_checkout(run)
        with (run / "preflight/pipeline.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            dispatch(args, run, storage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
