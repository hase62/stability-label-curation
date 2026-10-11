"""Portable storage configuration; resolution never writes to disk."""

from collections.abc import Mapping
from dataclasses import dataclass, fields
import os
from pathlib import Path

PROJECT_NAME = "stability-label-curation"


class PathConfigurationError(ValueError):
    """A storage override is ambiguous or unsafe."""


def _normalize(value: str | Path, name: str, home: Path) -> Path:
    raw = str(value)
    if raw == "~" or raw.startswith("~/"):
        path = home / raw[2:] if raw != "~" else home
    else:
        path = Path(raw).expanduser()
    if not path.is_absolute():
        raise PathConfigurationError(
            f"{name} must be an absolute path or start with ~/; got {raw!r}. "
            "Set an absolute storage location or unset the override."
        )
    return path.resolve()


@dataclass(frozen=True)
class StoragePaths:
    codex_root: Path
    data_root: Path
    repos_root: Path
    runs_root: Path
    repository_root: Path
    project_data_dir: Path
    project_runs_dir: Path

    def as_dict(self) -> dict[str, str]:
        return {field.name: str(getattr(self, field.name)) for field in fields(self)}

    def validate(self) -> None:
        for name in ("data_root", "runs_root", "project_data_dir", "project_runs_dir"):
            path = getattr(self, name).resolve()
            repository = self.repository_root.resolve()
            if path.is_relative_to(repository):
                raise PathConfigurationError(
                    f"{name} ({path}) is inside the repository. "
                    "Set CODEX_DATA_ROOT and CODEX_RUNS_ROOT to external storage."
                )
        for name in ("project_data_dir", "project_runs_dir"):
            if self.repository_root.resolve().is_relative_to(getattr(self, name).resolve()):
                raise PathConfigurationError(f"{name} must not contain the repository.")
        data, runs = self.project_data_dir.resolve(), self.project_runs_dir.resolve()
        if data.is_relative_to(runs) or runs.is_relative_to(data):
            raise PathConfigurationError("Project data and runs directories must be separate and non-nested.")


def resolve_paths(
    env: Mapping[str, str] | None = None,
    *,
    home: Path | None = None,
    repository_root: Path | None = None,
) -> StoragePaths:
    """Resolve overrides without creating directories; injectable inputs aid tests."""
    environment = os.environ if env is None else env
    user_home = Path.home() if home is None else home
    user_home = user_home.expanduser().resolve()

    def root(name: str, default: Path) -> Path:
        return _normalize(environment.get(name, str(default)), name, user_home)

    codex = root("CODEX_ROOT", user_home / "codex")
    data = root("CODEX_DATA_ROOT", codex / "data")
    repos = root("CODEX_REPOS_ROOT", codex / "repos")
    runs = root("CODEX_RUNS_ROOT", codex / "runs")
    repository = _normalize(
        repository_root if repository_root is not None else Path(__file__).resolve().parents[2],
        "repository_root", user_home,
    )
    paths = StoragePaths(codex, data, repos, runs, repository,
                         (data / PROJECT_NAME).resolve(), (runs / PROJECT_NAME).resolve())
    paths.validate()
    return paths


def initialize_storage(paths: StoragePaths) -> tuple[Path, ...]:
    """Create only project data/runs directories and their missing parents."""
    paths.validate()
    targets = (paths.project_data_dir, paths.project_runs_dir)
    for target in targets:
        target.mkdir(parents=True, exist_ok=True)
    return targets


def check_storage(paths: StoragePaths) -> list[tuple[str, str]]:
    """Inspect only configured paths and their parents; never create or edit files."""
    paths.validate()
    findings: list[tuple[str, str]] = []
    for name, value in paths.as_dict().items():
        path = Path(value)
        if path.exists():
            if not path.is_dir():
                findings.append(("ERROR", f"{name} is not a directory: {path}"))
            elif name != "repository_root" and not os.access(path, os.W_OK | os.X_OK):
                findings.append(("WARNING", f"{name} is not writable/searchable: {path}"))
        else:
            severity = "ERROR" if name == "repository_root" else "WARNING"
            findings.append((severity, f"{name} does not exist: {path}"))
            parent = path.parent
            while not parent.exists() and parent != parent.parent:
                parent = parent.parent
            if not parent.is_dir():
                findings.append(("ERROR", f"Parent is not a directory: {parent}"))
            elif not os.access(parent, os.W_OK | os.X_OK):
                findings.append(("WARNING", f"Nearest existing parent is not writable/searchable: {parent}"))
    return findings
