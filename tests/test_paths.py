"""Storage contract checks using isolated temporary directories."""

from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from stability_label_curation.__main__ import main
from stability_label_curation.paths import (
    PathConfigurationError, check_storage, initialize_storage, resolve_paths,
)


class TestPaths(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "home"
        self.repository = self.base / "checkout"
        self.repository.mkdir()

    def resolve(self, env=None):
        return resolve_paths({} if env is None else env, home=self.home,
                             repository_root=self.repository)

    def snapshot(self):
        return {str(p.relative_to(self.base)): (p.stat().st_mode, p.stat().st_mtime_ns,
                p.read_bytes() if p.is_file() else None) for p in self.base.rglob("*")}

    def cli(self, args, env=None):
        out, err = StringIO(), StringIO()
        # Retain the CLI's real resolver while supplying an isolated home/checkout.
        def resolver(environment):
            return self.resolve(environment)
        with patch("stability_label_curation.__main__.resolve_paths", side_effect=resolver), \
                redirect_stdout(out), redirect_stderr(err):
            status = main(args, env={} if env is None else env)
        return status, out.getvalue(), err.getvalue()

    def test_defaults(self):
        paths = self.resolve()
        self.assertEqual(paths.codex_root, self.home / "codex")
        for name in ("data", "repos", "runs"):
            self.assertEqual(getattr(paths, name + "_root"), self.home / "codex" / name)
        self.assertEqual(paths.repository_root, self.repository)
        self.assertEqual(paths.project_data_dir, paths.data_root / "stability-label-curation")
        self.assertEqual(paths.project_runs_dir, paths.runs_root / "stability-label-curation")

    def test_custom_codex_root(self):
        paths = self.resolve({"CODEX_ROOT": str(self.base / "custom")})
        self.assertEqual(paths.data_root, self.base / "custom/data")
        self.assertEqual(paths.repos_root, self.base / "custom/repos")
        self.assertEqual(paths.runs_root, self.base / "custom/runs")

    def test_independent_overrides(self):
        for name in ("DATA", "REPOS", "RUNS"):
            with self.subTest(name=name):
                paths = self.resolve({f"CODEX_{name}_ROOT": str(self.base / name)})
                self.assertEqual(getattr(paths, name.lower() + "_root"), self.base / name)
                self.assertEqual(paths.codex_root, self.home / "codex")

    def test_override_precedence(self):
        env = {"CODEX_ROOT": str(self.base / "custom")}
        env.update({f"CODEX_{name}_ROOT": str(self.base / name) for name in ("DATA", "REPOS", "RUNS")})
        paths = self.resolve(env)
        for name in ("DATA", "REPOS", "RUNS"):
            self.assertEqual(getattr(paths, name.lower() + "_root"), self.base / name)

    def test_tilde_and_normalization(self):
        paths = self.resolve({"CODEX_ROOT": "~/storage/../codex"})
        self.assertEqual(paths.codex_root, self.home / "codex")

    def test_relative_overrides_rejected(self):
        for name in ("CODEX_ROOT", "CODEX_DATA_ROOT", "CODEX_REPOS_ROOT", "CODEX_RUNS_ROOT"):
            for value in ("relative/path", "", "."):
                with self.subTest(name=name, value=value):
                    with self.assertRaisesRegex(PathConfigurationError, "absolute"):
                        self.resolve({name: value})

    def test_environment_mapping_isolated(self):
        with patch.dict("os.environ", {"CODEX_ROOT": "relative"}):
            self.assertEqual(self.resolve({}).codex_root, self.home / "codex")
            with self.assertRaises(PathConfigurationError):
                resolve_paths(home=self.home, repository_root=self.repository)

    def test_resolution_has_no_side_effects(self):
        before = self.snapshot()
        self.resolve()
        self.assertEqual(before, self.snapshot())

    def test_import_has_no_side_effects(self):
        before = self.snapshot()
        environment = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src"))
        result = subprocess.run(
            [sys.executable, "-B", "-c",
             "from pathlib import Path; from unittest.mock import patch; "
             "guard = patch.object(Path, 'mkdir', side_effect=AssertionError('Unexpected mkdir')); "
             "guard.start(); import stability_label_curation; "
             "import stability_label_curation.paths; import stability_label_curation.__main__"],
            cwd=self.base, env=environment, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_initialization_is_idempotent_and_limited(self):
        paths = self.resolve()
        initialize_storage(paths)
        before = self.snapshot()
        initialize_storage(paths)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(set(before), {"checkout", "home", "home/codex", "home/codex/data",
                                      "home/codex/data/stability-label-curation", "home/codex/runs",
                                      "home/codex/runs/stability-label-curation"})
        self.assertFalse(paths.repos_root.exists())

    def test_preserves_sibling_projects_and_permissions(self):
        paths = self.resolve()
        siblings = [root / "other-project" for root in (paths.data_root, paths.repos_root, paths.runs_root)]
        for sibling in siblings:
            sibling.mkdir(parents=True)
            (sibling / "sentinel.txt").write_text("untouched", encoding="utf-8")
            sibling.chmod(0o750)
        before = {p: (p.stat().st_mode, p.stat().st_mtime_ns,
                      (p / "sentinel.txt").read_bytes()) for p in siblings}
        initialize_storage(paths)
        self.assertEqual(before, {p: (p.stat().st_mode, p.stat().st_mtime_ns,
                                    (p / "sentinel.txt").read_bytes()) for p in siblings})

    def test_storage_inside_repository_rejected(self):
        for name in ("CODEX_DATA_ROOT", "CODEX_RUNS_ROOT"):
            for path in (self.repository, self.repository / "nested"):
                with self.subTest(name=name, path=path):
                    with self.assertRaises(ValueError):
                        self.resolve({name: str(path)})

    def test_symlink_into_repository_rejected(self):
        alias = self.base / "alias"
        alias.symlink_to(self.repository, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.resolve({"CODEX_DATA_ROOT": str(alias)})

    def test_project_symlink_into_repository_rejected(self):
        root = self.base / "data"
        root.mkdir()
        (root / "stability-label-curation").symlink_to(self.repository, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.resolve({"CODEX_DATA_ROOT": str(root)})

    def test_overlapping_storage_rejected(self):
        with self.assertRaises(ValueError):
            self.resolve({"CODEX_DATA_ROOT": str(self.base / "shared"),
                          "CODEX_RUNS_ROOT": str(self.base / "shared")})

    def test_json_output(self):
        status, output, error = self.cli(["paths", "--json"])
        self.assertEqual(status, 0)
        self.assertEqual(error, "")
        self.assertEqual(json.loads(output), self.resolve().as_dict())

    def test_doctor_is_read_only(self):
        before = self.snapshot()
        status, output, error = self.cli(["doctor"])
        self.assertEqual(status, 0)
        self.assertIn("WARNING", output)
        self.assertEqual(error, "")
        self.assertEqual(before, self.snapshot())

    def test_doctor_after_initialization(self):
        paths = self.resolve()
        initialize_storage(paths)
        paths.repos_root.mkdir()
        before = self.snapshot()
        self.assertEqual(check_storage(paths), [])
        self.assertEqual(before, self.snapshot())

    def test_doctor_reports_file_conflict(self):
        paths = self.resolve()
        paths.codex_root.mkdir(parents=True)
        paths.data_root.write_text("conflict", encoding="utf-8")
        before = self.snapshot()
        status, output, _ = self.cli(["doctor"])
        self.assertEqual(status, 1)
        self.assertIn("ERROR", output)
        self.assertEqual(before, self.snapshot())

    def test_cli_invalid_configuration(self):
        status, _, error = self.cli(["init-storage"], {"CODEX_DATA_ROOT": str(self.repository)})
        self.assertEqual(status, 1)
        self.assertIn("ERROR", error)


if __name__ == "__main__":
    unittest.main()
