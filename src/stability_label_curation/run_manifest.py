"""Versioned run evidence and explicit, exclusive creation; no import-time writes."""

from collections.abc import Sequence
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import secrets
import socket
import stat
import subprocess
import sys
from typing import Any, Iterator

from .paths import PROJECT_NAME, StoragePaths, resolve_paths

SCHEMA_VERSION = 1
SOURCE_MANIFEST = "configs/data_sources.toml"
RUN_SUBDIRECTORIES = (
    "logs", "interim", "processed", "checkpoints", "predictions", "metrics",
    "figures", "reports",
)
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
DIRTY_WARNING = "Noncanonical dirty development state; potentially nonreproducible."
LIMITATION = "Provenance evidence only; bitwise-identical reruns are not guaranteed."


class RunManifestError(ValueError):
    """Run creation, lookup, or metadata failed a safety/validation check."""


def validate_run_id(run_id: str) -> str:
    """Accept a conservative ASCII filename, including portable custom IDs."""
    if (not isinstance(run_id, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,95}", run_id) is None
            or run_id.upper() in {"CON", "PRN", "AUX", "NUL", *(
                f"{prefix}{i}" for prefix in ("COM", "LPT") for i in range(1, 10)
            )}):
        raise RunManifestError(
            "Unsafe run_id: use 1–96 ASCII letters, digits, '_' or '-', "
            "starting with a letter/digit; reserved device names are forbidden."
        )
    return run_id


def generate_run_id() -> str:
    """UTC to the second plus 96 random bits; collisions are never overwritten."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + secrets.token_hex(12)


def _git(repository: Path, *arguments: str, allow_detached: bool = False) -> bytes:
    environment = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    result = subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-c", "core.untrackedCache=false", *arguments],
        cwd=repository, env=environment, capture_output=True, check=False,
    )
    if result.returncode and not (allow_detached and result.returncode == 1):
        raise RunManifestError(
            f"Git provenance failed ({' '.join(arguments)}): "
            + result.stderr.decode("utf-8", errors="backslashreplace").strip()
        )
    return result.stdout


def capture_git_provenance(repository: Path, *, allow_dirty: bool = False) -> dict[str, Any]:
    """Include tracked, staged and all nonignored untracked files; permit detached HEAD."""
    repository = repository.resolve(strict=True)
    actual = Path(os.fsdecode(_git(repository, "rev-parse", "--show-toplevel").rstrip(b"\n"))).resolve()
    if actual != repository:
        raise RunManifestError("repository_root must be the Git checkout root.")
    commit = _git(repository, "rev-parse", "--verify", "HEAD").decode("ascii").strip()
    branch = _git(repository, "symbolic-ref", "--quiet", "--short", "HEAD",
                  allow_detached=True).decode("utf-8", errors="backslashreplace").strip() or None
    status = _git(repository, "status", "--porcelain=v1", "-z", "--untracked-files=all")
    entries = [entry.decode("utf-8", errors="backslashreplace") for entry in status.split(b"\0") if entry]
    if entries and not allow_dirty:
        raise RunManifestError(
            "Working tree is dirty (including nonignored untracked files). "
            "Commit changes first, or explicitly use --allow-dirty for a noncanonical development run."
        )
    return {"repository_name": repository.name, "commit_sha": commit, "branch": branch,
            "working_tree_clean": not bool(entries), "git_dirty": bool(entries),
            "working_tree_status": entries}


def capture_runtime_environment() -> dict[str, Any]:
    """Record observed CPU/Python/host metadata; do not probe or guess GPUs."""
    return {"operating_system": platform.system(), "os_version": platform.version(),
            "cpu_architecture": platform.machine(), "python_version": platform.python_version(),
            "python_executable": sys.executable, "hostname": socket.gethostname(),
            "gpu": {"status": "not_collected"}}


def sha256_file(path: str | Path) -> str:
    """Hash regular file bytes in 1 MiB chunks; detect ordinary concurrent edits."""
    file = Path(path).expanduser().absolute()
    with _directory(file.parent) as parent_fd, os.fdopen(
            os.open(file.name, FILE_FLAGS, dir_fd=parent_fd), "rb") as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode):
            raise RunManifestError(f"Expected a regular file for SHA256: {path}")
        digest = hashlib.sha256()
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
        after = os.fstat(stream.fileno())
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise RunManifestError(f"File changed while hashing; retry with stable inputs: {path}")
    return digest.hexdigest()


def _artifact(path: str | Path, paths: StoragePaths, *, configuration: bool = False) -> dict[str, str]:
    paths.validate()
    if (paths.project_data_dir != paths.data_root / PROJECT_NAME
            or paths.project_data_dir.resolve() != paths.project_data_dir):
        raise RunManifestError("Project data directory must not be a symlink or escape its configured root.")
    _runs_root(paths)
    resolved = Path(path).expanduser().resolve(strict=True)
    roots = [paths.project_data_dir, paths.project_runs_dir]
    if configuration:
        roots.append(paths.repository_root)
    if not any(resolved.is_relative_to(root) for root in roots):
        raise RunManifestError(f"File is outside authorized project storage: {path}")
    return {"path": str(resolved), "sha256": sha256_file(resolved)}


def build_manifest(
    *, paths: StoragePaths | None = None, run_id: str | None = None,
    kind: str, description: str | None = None, seed: int | None = None,
    config: str | Path | None = None, inputs: Sequence[str | Path] = (),
    argv: Sequence[str], allow_dirty: bool = False,
) -> dict[str, Any]:
    """Construct/validate evidence without writing; registry bytes come from recorded HEAD."""
    paths = resolve_paths() if paths is None else paths
    paths.validate()
    identity = validate_run_id(generate_run_id() if run_id is None else run_id)
    git = capture_git_provenance(paths.repository_root, allow_dirty=allow_dirty)
    committed_source = _git(paths.repository_root, "show", f"{git['commit_sha']}:{SOURCE_MANIFEST}")
    document = {
        "schema_version": SCHEMA_VERSION, "run_id": identity, "project_name": PROJECT_NAME,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "run_kind": kind, "description": description,
        "git": git, "runtime_environment": capture_runtime_environment(),
        "configuration": {"file": None if config is None else _artifact(config, paths, configuration=True),
                          "random_seed": seed, "argv": list(argv)},
        "data_provenance": {"data_source_manifest": {"path": SOURCE_MANIFEST,
                            "sha256": hashlib.sha256(committed_source).hexdigest()},
                            "input_artifacts": [_artifact(path, paths) for path in inputs]},
        "external_repositories": [],
        "reproducibility": {"status": "dirty_development" if git["git_dirty"] else "clean_committed",
                            "canonical": not git["git_dirty"],
                            "warnings": [DIRTY_WARNING] if git["git_dirty"] else [],
                            "limitations": LIMITATION},
    }
    validate_manifest(document)
    if capture_git_provenance(paths.repository_root, allow_dirty=allow_dirty) != git:
        raise RunManifestError("Git state changed during provenance capture; retry from a stable checkout.")
    return document


def _object(value: Any, keys: set[str], location: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise RunManifestError(f"{location} must be an object with exactly these fields: {', '.join(sorted(keys))}")
    return value


def _string(value: Any, location: str, *, nullable: bool = False) -> None:
    if nullable and value is None:
        return
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise RunManifestError(f"{location} must be a nonempty string" + (" or null." if nullable else "."))


def _checksum(value: Any, location: str) -> None:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise RunManifestError(f"{location} must be a lowercase 64-character SHA256.")


def _file_record(value: Any, location: str, *, absolute: bool = True) -> None:
    record = _object(value, {"path", "sha256"}, location)
    _string(record["path"], location + ".path")
    if absolute and not Path(record["path"]).is_absolute():
        raise RunManifestError(f"{location}.path must be absolute.")
    _checksum(record["sha256"], location + ".sha256")


def validate_manifest(document: Any) -> dict[str, Any]:
    """Validate schema/evidence consistency only; never write or rehash input files."""
    record = _object(document, {"schema_version", "run_id", "project_name", "created_at_utc",
                     "run_kind", "description", "git", "runtime_environment", "configuration",
                     "data_provenance", "external_repositories", "reproducibility"}, "manifest")
    if type(record["schema_version"]) is not int or record["schema_version"] != SCHEMA_VERSION:
        raise RunManifestError(f"Unsupported schema_version; expected {SCHEMA_VERSION}.")
    validate_run_id(record["run_id"])
    if record["project_name"] != PROJECT_NAME:
        raise RunManifestError(f"project_name must be {PROJECT_NAME!r}.")
    timestamp = record["created_at_utc"]
    if not isinstance(timestamp, str) or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", timestamp) is None:
        raise RunManifestError("created_at_utc must be an ISO 8601 UTC timestamp ending in Z.")
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as error:
        raise RunManifestError(f"Invalid created_at_utc: {error}") from error
    if not isinstance(record["run_kind"], str) or re.fullmatch(r"[a-z][a-z0-9_-]{0,63}", record["run_kind"]) is None:
        raise RunManifestError("run_kind must start with a lowercase letter and use lowercase letters, digits, '_' or '-'.")
    _string(record["description"], "description", nullable=True)
    git = _object(record["git"], {"repository_name", "commit_sha", "branch", "working_tree_clean",
                                  "git_dirty", "working_tree_status"}, "git")
    _string(git["repository_name"], "git.repository_name")
    _string(git["branch"], "git.branch", nullable=True)
    if not isinstance(git["commit_sha"], str) or re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", git["commit_sha"]) is None:
        raise RunManifestError("git.commit_sha must be a full Git object SHA.")
    status = git["working_tree_status"]
    if not isinstance(status, list) or any(not isinstance(item, str) or not item for item in status):
        raise RunManifestError("git.working_tree_status must be an array of nonempty status strings.")
    if (type(git["git_dirty"]) is not bool or type(git["working_tree_clean"]) is not bool
            or git["git_dirty"] != bool(status) or git["working_tree_clean"] == git["git_dirty"]):
        raise RunManifestError("git dirty/clean flags must agree with working_tree_status.")
    runtime = _object(record["runtime_environment"], {"operating_system", "os_version", "cpu_architecture",
                      "python_version", "python_executable", "hostname", "gpu"}, "runtime_environment")
    for key in runtime.keys() - {"gpu"}:
        _string(runtime[key], "runtime_environment." + key)
    if runtime["gpu"] != {"status": "not_collected"}:
        raise RunManifestError("Schema 1 runtime_environment.gpu must be {'status': 'not_collected'}.")
    config = _object(record["configuration"], {"file", "random_seed", "argv"}, "configuration")
    if config["file"] is not None:
        _file_record(config["file"], "configuration.file")
    if config["random_seed"] is not None and type(config["random_seed"]) is not int:
        raise RunManifestError("configuration.random_seed must be an integer or null.")
    if not isinstance(config["argv"], list) or not config["argv"] or any(
            not isinstance(item, str) or "\0" in item for item in config["argv"]):
        raise RunManifestError("configuration.argv must be a nonempty array of strings without NUL.")
    data = _object(record["data_provenance"], {"data_source_manifest", "input_artifacts"}, "data_provenance")
    _file_record(data["data_source_manifest"], "data_source_manifest", absolute=False)
    if data["data_source_manifest"]["path"] != SOURCE_MANIFEST:
        raise RunManifestError(f"data_source_manifest.path must be {SOURCE_MANIFEST!r}.")
    if not isinstance(data["input_artifacts"], list):
        raise RunManifestError("input_artifacts must be an array (empty when no inputs supplied).")
    for index, artifact in enumerate(data["input_artifacts"]):
        _file_record(artifact, f"input_artifacts[{index}]")
    external = record["external_repositories"]
    if not isinstance(external, list):
        raise RunManifestError("external_repositories must be an array.")
    for index, repository in enumerate(external):
        repository = _object(repository, {"repository_name", "commit_sha", "branch"}, f"external_repositories[{index}]")
        _string(repository["repository_name"], "external repository name")
        _string(repository["branch"], "external repository branch", nullable=True)
        if not isinstance(repository["commit_sha"], str) or re.fullmatch(
                r"(?:[0-9a-f]{40}|[0-9a-f]{64})", repository["commit_sha"]) is None:
            raise RunManifestError("External repository commit_sha must be a full Git object SHA.")
    expected = {"status": "dirty_development" if git["git_dirty"] else "clean_committed",
                "canonical": not git["git_dirty"], "warnings": [DIRTY_WARNING] if git["git_dirty"] else [],
                "limitations": LIMITATION}
    reproducibility = _object(record["reproducibility"], set(expected), "reproducibility")
    if type(reproducibility["canonical"]) is not bool or reproducibility != expected:
        raise RunManifestError("reproducibility must agree with Git evidence and include the schema 1 limitations/warnings.")
    return record


def _runs_root(paths: StoragePaths) -> Path:
    paths.validate()
    expected = paths.runs_root / PROJECT_NAME
    if paths.project_runs_dir != expected or expected.resolve() != expected:
        raise RunManifestError("Project runs directory must not be a symlink or escape the configured runs root.")
    return expected


@contextmanager
def _directory(path: Path, *, create: bool = False) -> Iterator[int]:
    """Traverse with no-follow directory descriptors; creation touches only missing ancestors."""
    descriptor = os.open(path.anchor, DIR_FLAGS)
    try:
        for part in path.parts[1:]:
            if create:
                try:
                    os.mkdir(part, dir_fd=descriptor)
                except FileExistsError:
                    pass
            child = os.open(part, DIR_FLAGS, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        yield descriptor
    finally:
        os.close(descriptor)


def create_run(
    *, paths: StoragePaths | None = None, run_id: str | None = None,
    kind: str, description: str | None = None, seed: int | None = None,
    config: str | Path | None = None, inputs: Sequence[str | Path] = (),
    argv: Sequence[str], allow_dirty: bool = False,
) -> Path:
    """Reserve exactly one run with atomic mkdir; publish manifest only after outputs exist."""
    paths = resolve_paths() if paths is None else paths
    root = _runs_root(paths)
    manifest = build_manifest(paths=paths, run_id=run_id, kind=kind, description=description,
                              seed=seed, config=config, inputs=inputs, argv=argv, allow_dirty=allow_dirty)
    run_id = manifest["run_id"]
    with _directory(root, create=True) as root_fd:
        try:
            os.mkdir(run_id, dir_fd=root_fd)
        except FileExistsError as error:
            raise RunManifestError(f"Run already exists; never overwritten: {run_id}") from error
        run_fd = os.open(run_id, DIR_FLAGS, dir_fd=root_fd)
        try:
            with os.fdopen(os.open(".incomplete", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                   0o666, dir_fd=run_fd), "w", encoding="utf-8") as marker:
                marker.write("Run creation has not completed. Do not use this directory as a valid run.\n")
            for name in RUN_SUBDIRECTORIES:
                os.mkdir(name, dir_fd=run_fd)
            with os.fdopen(os.open(".manifest.pending", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                   0o666, dir_fd=run_fd), "w", encoding="utf-8") as stream:
                json.dump(manifest, stream, indent=2, sort_keys=True, allow_nan=False)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            # Atomic publication with no replacement, even if a destination appears unexpectedly.
            os.link(".manifest.pending", "manifest.json", src_dir_fd=run_fd, dst_dir_fd=run_fd,
                    follow_symlinks=False)
            os.unlink(".manifest.pending", dir_fd=run_fd)
            os.unlink(".incomplete", dir_fd=run_fd)
        finally:
            os.close(run_fd)
    return root / run_id


def lookup_run(run_id: str, *, paths: StoragePaths | None = None) -> Path:
    """Read-only lookup; reject symlink components and missing directories."""
    paths = resolve_paths() if paths is None else paths
    target = _runs_root(paths) / validate_run_id(run_id)
    try:
        with _directory(target):
            pass
    except FileNotFoundError as error:
        raise RunManifestError(f"Run not found: {run_id}") from error
    except OSError as error:
        raise RunManifestError(f"Unsafe or inaccessible run directory {run_id}: {error}") from error
    return target


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RunManifestError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def load_manifest(run_id: str, *, paths: StoragePaths | None = None) -> dict[str, Any]:
    """Read/validate the completed JSON manifest without creating directories."""
    target = lookup_run(run_id, paths=paths)
    try:
        with _directory(target) as run_fd:
            try:
                os.stat(".incomplete", dir_fd=run_fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise RunManifestError(f"Run {run_id} is incomplete; creation did not finish.")
            with os.fdopen(os.open("manifest.json", FILE_FLAGS, dir_fd=run_fd), "r", encoding="utf-8") as stream:
                if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                    raise RunManifestError(f"Run {run_id} manifest must be a regular file.")
                document = json.load(stream, object_pairs_hook=_unique_keys)
    except FileNotFoundError as error:
        raise RunManifestError(f"Run {run_id} is incomplete: missing manifest.json.") from error
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise RunManifestError(f"Cannot read run {run_id} manifest.json: {error}") from error
    manifest = validate_manifest(document)
    if manifest["run_id"] != run_id:
        raise RunManifestError(f"Manifest run_id does not match directory {run_id}.")
    return manifest


def list_runs(*, paths: StoragePaths | None = None) -> list[dict[str, Any]]:
    """List project directories only; surface incomplete/invalid runs as errors in summaries."""
    paths = resolve_paths() if paths is None else paths
    root = _runs_root(paths)
    try:
        with _directory(root) as root_fd:
            names = sorted(name for name in os.listdir(root_fd) if stat.S_ISDIR(
                os.stat(name, dir_fd=root_fd, follow_symlinks=False).st_mode))
    except FileNotFoundError:
        return []
    summaries = []
    for name in names:
        try:
            manifest = load_manifest(name, paths=paths)
            summaries.append({"run_id": name, "status": "complete", "run_kind": manifest["run_kind"],
                              "created_at_utc": manifest["created_at_utc"],
                              "reproducibility": manifest["reproducibility"]})
        except RunManifestError as error:
            summaries.append({"run_id": name, "status": "invalid_or_incomplete", "error": str(error)})
    return summaries
