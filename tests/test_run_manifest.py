"""Run infrastructure checks in temporary storage/checkouts, without scientific work."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stderr, redirect_stdout
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from io import StringIO
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib import request

from stability_label_curation.__main__ import main
from stability_label_curation.paths import resolve_paths
from stability_label_curation import run_manifest as runs


class TestRunManifest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.repository = self.base / "checkout"
        self.repository.mkdir()
        self.git("init", "-b", "main")
        self.git("config", "user.name", "Run Manifest Test")
        self.git("config", "user.email", "run-test@example.invalid")
        (self.repository / "configs").mkdir()
        self.source = self.repository / runs.SOURCE_MANIFEST
        self.source.write_bytes(b"schema_version = 1\n# Metadata fixture, no observations.\n")
        (self.repository / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-m", "Commit metadata fixture")
        self.commit = self.git("rev-parse", "HEAD").strip()
        self.paths = resolve_paths({}, home=self.base / "home", repository_root=self.repository)

    def git(self, *arguments):
        result = subprocess.run(
            ["git", "-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null", *arguments],
            cwd=self.repository, capture_output=True, text=True,
            env=dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def build(self, **kwargs):
        options = dict(paths=self.paths, kind="infrastructure", argv=["test", "runs", "create"])
        options.update(kwargs)
        return runs.build_manifest(**options)

    def create(self, **kwargs):
        options = dict(paths=self.paths, kind="infrastructure", argv=["test", "runs", "create"])
        options.update(kwargs)
        return runs.create_run(**options)

    def snapshot(self, directory=None):
        directory = self.base if directory is None else directory
        return {str(p.relative_to(directory)): (p.lstat().st_mode, p.lstat().st_mtime_ns,
                p.read_bytes() if p.is_file() and not p.is_symlink() else None)
                for p in directory.rglob("*")}

    def cli(self, argv):
        out, err = StringIO(), StringIO()
        with patch("stability_label_curation.__main__.resolve_paths", return_value=self.paths), \
                redirect_stdout(out), redirect_stderr(err):
            status = main(argv, env={})
        return status, out.getvalue(), err.getvalue()

    def test_run_id_format_and_uniqueness(self):
        identifiers = {runs.generate_run_id() for _ in range(1000)}
        self.assertEqual(len(identifiers), 1000)
        for identifier in identifiers:
            self.assertRegex(identifier, r"^\d{8}T\d{6}Z-[0-9a-f]{24}$")
            self.assertEqual(runs.validate_run_id(identifier), identifier)

    def test_unsafe_run_ids(self):
        for value in ["", ".", "..", "a..b", "../other", "/absolute", "C:\\other", "a/b",
                      "a\\b", "a\n", "a\0b", " a", "a b", "a:", "a.", "~", "é", "-x",
                      "CON", "nul", "COM1", "LPT9", "a" * 97, None, 2]:
            with self.subTest(value=value), self.assertRaises(runs.RunManifestError):
                runs.validate_run_id(value)
        self.assertEqual(runs.validate_run_id("smoke_test-01"), "smoke_test-01")

    def test_default_run_directory(self):
        before = self.snapshot()
        self.assertEqual(self.paths.project_runs_dir, self.base / "home/codex/runs/stability-label-curation")
        self.build()
        self.assertEqual(self.snapshot(), before)
        target = self.create()
        self.assertEqual(target.parent, self.paths.project_runs_dir)

    def test_custom_runs_root(self):
        paths = resolve_paths({"CODEX_RUNS_ROOT": str(self.base / "custom-runs")},
                              home=self.base / "home", repository_root=self.repository)
        target = self.create(paths=paths)
        self.assertEqual(target.parent, self.base / "custom-runs/stability-label-curation")
        self.assertFalse(self.paths.project_runs_dir.exists())

    def test_valid_manifest_and_exact_directory_structure(self):
        target = self.create(seed=0, description="Infrastructure test")
        self.assertEqual({p.name for p in target.iterdir()}, {"manifest.json", *runs.RUN_SUBDIRECTORIES})
        document = runs.load_manifest(target.name, paths=self.paths)
        self.assertEqual(runs.validate_manifest(document), document)
        self.assertEqual(document["configuration"]["random_seed"], 0)
        self.assertEqual(document["description"], "Infrastructure test")
        self.assertEqual(document["external_repositories"], [])
        self.assertEqual(document["runtime_environment"]["gpu"], {"status": "not_collected"})
        self.assertTrue(document["reproducibility"]["canonical"])
        self.assertIn("not guaranteed", document["reproducibility"]["limitations"])

    def test_json_serialization(self):
        document = self.build()
        self.assertEqual(json.loads(json.dumps(document, allow_nan=False)), document)
        target = self.create()
        self.assertEqual(json.loads((target / "manifest.json").read_text()), runs.load_manifest(target.name, paths=self.paths))

    def test_utc_timestamp_and_id(self):
        before = datetime.now(timezone.utc)
        document = self.build()
        after = datetime.now(timezone.utc)
        self.assertTrue(document["created_at_utc"].endswith("Z"))
        timestamp = datetime.fromisoformat(document["created_at_utc"].replace("Z", "+00:00"))
        self.assertLessEqual(before, timestamp)
        self.assertLessEqual(timestamp, after)
        id_time = datetime.strptime(document["run_id"].split("-")[0], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        self.assertLess(abs((timestamp - id_time).total_seconds()), 2)

    def test_actual_git_commit_and_branch(self):
        document = self.build()
        self.assertEqual(document["git"]["commit_sha"], self.commit)
        self.assertEqual(document["git"]["branch"], "main")
        self.assertEqual(document["git"]["repository_name"], "checkout")
        self.assertTrue(document["git"]["working_tree_clean"])
        self.assertFalse(document["git"]["git_dirty"])
        self.assertEqual(document["git"]["working_tree_status"], [])

    def test_detached_head_is_explicit_null(self):
        self.git("checkout", "--detach", self.commit)
        self.assertIsNone(self.build()["git"]["branch"])

    def test_default_clean_enforcement_tracked_staged_and_untracked(self):
        for change in ("tracked", "staged", "untracked"):
            with self.subTest(change=change):
                if change == "untracked":
                    (self.repository / "new.txt").write_bytes(b"development")
                else:
                    self.source.write_bytes(b"modified registry")
                    if change == "staged":
                        self.git("add", "configs/data_sources.toml")
                with self.assertRaisesRegex(runs.RunManifestError, "dirty"):
                    self.create()
                self.assertFalse(self.paths.project_runs_dir.exists())
                # Restore only fixture files in this disposable temporary checkout.
                self.git("restore", "--staged", "configs/data_sources.toml")
                self.git("restore", "configs/data_sources.toml")

    def test_ignored_files_do_not_dirty_git(self):
        (self.repository / "ignored.txt").write_bytes(b"ignored fixture")
        self.assertFalse(self.build()["git"]["git_dirty"])

    def test_explicit_dirty_override(self):
        (self.repository / "development.txt").write_text("development", encoding="utf-8")
        target = self.create(allow_dirty=True)
        document = runs.load_manifest(target.name, paths=self.paths)
        self.assertTrue(document["git"]["git_dirty"])
        self.assertFalse(document["git"]["working_tree_clean"])
        self.assertIn("?? development.txt", document["git"]["working_tree_status"])
        self.assertEqual(document["reproducibility"]["status"], "dirty_development")
        self.assertFalse(document["reproducibility"]["canonical"])
        self.assertIn(runs.DIRTY_WARNING, document["reproducibility"]["warnings"])

    def test_sha256_actual_file_bytes_and_bounded_chunks(self):
        file = self.base / "bytes.bin"
        content = bytes(range(256)) * 13000
        file.write_bytes(content)
        self.assertEqual(runs.sha256_file(file), hashlib.sha256(content).hexdigest())
        file.write_bytes(b"")
        self.assertEqual(runs.sha256_file(file), hashlib.sha256(b"").hexdigest())
        with self.assertRaises((OSError, runs.RunManifestError)):
            runs.sha256_file(self.base)

    def test_no_fabricated_seed_config_or_inputs(self):
        document = self.build()
        self.assertEqual(document["data_provenance"]["input_artifacts"], [])
        self.assertIsNone(document["configuration"]["random_seed"])
        self.assertIsNone(document["configuration"]["file"])
        self.assertEqual(document["data_provenance"]["data_source_manifest"], {
            "path": runs.SOURCE_MANIFEST, "sha256": hashlib.sha256(self.source.read_bytes()).hexdigest()})

    def test_registry_hash_is_committed_even_when_dirty(self):
        original = self.source.read_bytes()
        self.source.write_bytes(b"Uncommitted development edit")
        document = self.build(allow_dirty=True)
        self.assertEqual(document["data_provenance"]["data_source_manifest"]["sha256"], hashlib.sha256(original).hexdigest())

    def test_explicit_configuration_and_input_files(self):
        self.paths.project_data_dir.mkdir(parents=True)
        input_file = self.paths.project_data_dir / "fixture.bin"
        input_file.write_bytes(b"explicit fixture\0\xff")
        first = self.create()
        output = first / "interim/fixture.bin"
        output.write_bytes(b"derived fixture")
        document = self.build(config=self.source, inputs=[input_file, output])
        self.assertEqual(document["configuration"]["file"]["sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(document["data_provenance"]["input_artifacts"], [
            {"path": str(p), "sha256": hashlib.sha256(p.read_bytes()).hexdigest()} for p in (input_file, output)])

    def test_input_boundaries_missing_files_and_symlink_escape(self):
        self.paths.project_data_dir.mkdir(parents=True)
        sibling = self.paths.data_root / "other-project"
        sibling.mkdir()
        outside = sibling / "sentinel.bin"
        outside.write_bytes(b"untouched")
        link = self.paths.project_data_dir / "escape.bin"
        link.symlink_to(outside)
        for file in (self.source, outside, link):
            with self.subTest(file=file), self.assertRaisesRegex(runs.RunManifestError, "outside authorized"):
                self.build(inputs=[file])
        with self.assertRaises(FileNotFoundError):
            self.build(inputs=[self.paths.project_data_dir / "missing"])
        with self.assertRaisesRegex(runs.RunManifestError, "outside authorized"):
            self.build(config=outside)
        self.assertEqual(outside.read_bytes(), b"untouched")
        self.assertFalse(self.paths.project_runs_dir.exists())

    def test_duplicate_run_never_overwritten(self):
        target = self.create(run_id="duplicate")
        before = self.snapshot(target)
        with self.assertRaisesRegex(runs.RunManifestError, "already exists"):
            self.create(run_id="duplicate")
        self.assertEqual(before, self.snapshot(target))

    def test_concurrent_same_id_at_most_one_success(self):
        def attempt(_):
            try:
                return self.create(run_id="concurrent")
            except runs.RunManifestError as error:
                return error
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(attempt, range(4)))
        self.assertEqual(sum(isinstance(result, Path) for result in results), 1)
        self.assertEqual(sum(isinstance(result, runs.RunManifestError) for result in results), 3)
        self.assertEqual(len(list(self.paths.project_runs_dir.iterdir())), 1)
        runs.load_manifest("concurrent", paths=self.paths)

    def test_run_symlink_escape_rejected(self):
        self.paths.project_runs_dir.mkdir(parents=True)
        outside = self.base / "unrelated"
        outside.mkdir()
        (self.paths.project_runs_dir / "escape").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(runs.RunManifestError):
            runs.lookup_run("escape", paths=self.paths)
        with self.assertRaises(runs.RunManifestError):
            runs.load_manifest("escape", paths=self.paths)
        with self.assertRaises(runs.RunManifestError):
            self.create(run_id="escape")
        self.assertEqual(list(outside.iterdir()), [])

    def test_project_runs_symlink_to_other_project_rejected(self):
        self.paths.runs_root.mkdir(parents=True)
        other = self.paths.runs_root / "other-project"
        other.mkdir()
        self.paths.project_runs_dir.symlink_to(other, target_is_directory=True)
        # Test both paths resolved before and after the symlink appeared.
        updated = resolve_paths({}, home=self.base / "home", repository_root=self.repository)
        for paths in (self.paths, updated):
            with self.assertRaises(runs.RunManifestError):
                self.create(paths=paths)
            with self.assertRaises(runs.RunManifestError):
                runs.list_runs(paths=paths)
        self.assertEqual(list(other.iterdir()), [])

    def test_runs_inside_repository_rejected(self):
        with self.assertRaises(ValueError):
            resolve_paths({"CODEX_RUNS_ROOT": str(self.repository / "local-runs")},
                          home=self.base / "home", repository_root=self.repository)

    def test_manifest_symlink_rejected(self):
        target = self.paths.project_runs_dir / "linked"
        target.mkdir(parents=True)
        outside = self.base / "outside.json"
        outside.write_text(json.dumps(self.build(run_id="linked")), encoding="utf-8")
        (target / "manifest.json").symlink_to(outside)
        with self.assertRaisesRegex(runs.RunManifestError, "Cannot read"):
            runs.load_manifest("linked", paths=self.paths)

    def test_input_parent_replaced_with_symlink_before_hash_is_rejected(self):
        parent = self.paths.project_data_dir / "fixture"
        parent.mkdir(parents=True)
        file = parent / "input.bin"
        file.write_bytes(b"authorized")
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "input.bin").write_bytes(b"unauthorized")
        real_hash = runs.sha256_file
        def replace_parent(path):
            parent.rename(parent.with_name("original"))
            parent.symlink_to(outside, target_is_directory=True)
            return real_hash(path)
        with patch.object(runs, "sha256_file", side_effect=replace_parent), self.assertRaises(OSError):
            self.build(inputs=[file])
        self.assertFalse(self.paths.project_runs_dir.exists())

    def test_git_change_during_capture_is_rejected(self):
        original = runs.capture_git_provenance
        captures = 0
        def change_after_first_capture(*args, **kwargs):
            nonlocal captures
            provenance = original(*args, **kwargs)
            captures += 1
            if captures == 1:
                (self.repository / "changed.txt").write_bytes(b"development")
            return provenance
        with patch.object(runs, "capture_git_provenance", side_effect=change_after_first_capture), \
                self.assertRaisesRegex(runs.RunManifestError, "Git state changed"):
            self.create(allow_dirty=True)
        self.assertFalse(self.paths.project_runs_dir.exists())

    def test_preservation_of_existing_runs_and_unrelated_projects(self):
        first = self.create()
        (first / "logs/sentinel.txt").write_bytes(b"retained existing run")
        other = self.paths.runs_root / "other-project"
        other.mkdir()
        (other / "sentinel.txt").write_bytes(b"unrelated project")
        before_first, before_other = self.snapshot(first), self.snapshot(other)
        self.create()
        self.assertEqual(before_first, self.snapshot(first))
        self.assertEqual(before_other, self.snapshot(other))
        self.assertFalse((self.repository / "runs").exists())

    def test_loading_lookup_listing_and_validation_are_read_only(self):
        target = self.create()
        before = self.snapshot()
        document = runs.load_manifest(target.name, paths=self.paths)
        runs.validate_manifest(document)
        self.assertEqual(runs.lookup_run(target.name, paths=self.paths), target)
        self.assertEqual(runs.list_runs(paths=self.paths)[0]["status"], "complete")
        self.assertEqual(before, self.snapshot())

    def test_missing_run_and_missing_root_are_read_only(self):
        before = self.snapshot()
        with self.assertRaisesRegex(runs.RunManifestError, "not found"):
            runs.load_manifest("missing", paths=self.paths)
        self.assertEqual(runs.list_runs(paths=self.paths), [])
        self.assertEqual(before, self.snapshot())

    def test_malformed_manifest_fields(self):
        original = self.build()
        mutations = [
            ("schema_version", True), ("schema_version", 2), ("created_at_utc", "2026-10-11T12:00:00+09:00"),
            ("created_at_utc", "2026-99-99T12:00:00Z"), ("created_at_utc", "2026-10-11T12:00:00+00:00"),
            ("project_name", "other-project"), ("run_kind", "../training"), ("description", 12),
            ("external_repositories", {}), ("runtime_environment", {}), ("run_id", "../escape"),
        ]
        for key, value in mutations:
            document = deepcopy(original)
            document[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(runs.RunManifestError):
                runs.validate_manifest(document)
        for key in original:
            document = deepcopy(original)
            del document[key]
            with self.subTest(missing=key), self.assertRaisesRegex(runs.RunManifestError, "fields"):
                runs.validate_manifest(document)
        document = deepcopy(original)
        document["unexpected"] = "field"
        with self.assertRaises(runs.RunManifestError):
            runs.validate_manifest(document)

    def test_malformed_nested_manifest_evidence(self):
        original = self.build()
        mutations = [("git", "commit_sha", "invented"), ("git", "git_dirty", True),
                     ("configuration", "random_seed", True), ("configuration", "argv", []),
                     ("configuration", "file", {"path": "relative", "sha256": "a" * 64}),
                     ("data_provenance", "input_artifacts", [{"path": "/file", "sha256": "fake"}]),
                     ("data_provenance", "input_artifacts", {}),
                     ("runtime_environment", "gpu", {"cuda_available": True}),
                     ("reproducibility", "canonical", False), ("reproducibility", "canonical", 1)]
        for section, key, value in mutations:
            document = deepcopy(original)
            document[section][key] = value
            with self.subTest(section=section, key=key), self.assertRaises(runs.RunManifestError):
                runs.validate_manifest(document)

    def test_invalid_json_and_directory_identity(self):
        target = self.create(run_id="invalid-json")
        file = target / "manifest.json"
        for content in ["{", "[]", '{"schema_version":1,"schema_version":1}', "\xff"]:
            file.write_text(content, encoding="utf-8")
            with self.subTest(content=content), self.assertRaises(runs.RunManifestError):
                runs.load_manifest(target.name, paths=self.paths)
        file.write_text(json.dumps(self.build(run_id="different")), encoding="utf-8")
        with self.assertRaisesRegex(runs.RunManifestError, "does not match"):
            runs.load_manifest(target.name, paths=self.paths)

    def test_failed_creation_stays_visibly_incomplete(self):
        original_mkdir = os.mkdir
        def fail_metrics(path, *args, **kwargs):
            if path == "metrics":
                raise OSError("Injected disk failure")
            return original_mkdir(path, *args, **kwargs)
        with patch.object(runs.os, "mkdir", side_effect=fail_metrics), self.assertRaisesRegex(OSError, "disk failure"):
            self.create(run_id="incomplete")
        target = self.paths.project_runs_dir / "incomplete"
        self.assertTrue((target / ".incomplete").exists())
        self.assertFalse((target / "manifest.json").exists())
        with self.assertRaisesRegex(runs.RunManifestError, "incomplete"):
            runs.load_manifest("incomplete", paths=self.paths)
        self.assertEqual(runs.list_runs(paths=self.paths)[0]["status"], "invalid_or_incomplete")
        with self.assertRaisesRegex(runs.RunManifestError, "already exists"):
            self.create(run_id="incomplete")

    def test_publication_failure_and_completion_marker(self):
        with patch.object(runs.os, "link", side_effect=OSError("Publication failed")), self.assertRaises(OSError):
            self.create(run_id="publication-failed")
        target = self.paths.project_runs_dir / "publication-failed"
        self.assertTrue((target / ".incomplete").exists())
        self.assertTrue((target / ".manifest.pending").exists())
        self.assertFalse((target / "manifest.json").exists())
        complete = self.create(run_id="marker-test")
        (complete / ".incomplete").write_bytes(b"Interrupted finalization")
        with self.assertRaisesRegex(runs.RunManifestError, "incomplete"):
            runs.load_manifest("marker-test", paths=self.paths)

    def test_missing_committed_registry_and_unborn_checkout_fail_before_writes(self):
        self.git("rm", "configs/data_sources.toml")
        self.git("commit", "-m", "Remove fixture registry")
        with self.assertRaisesRegex(runs.RunManifestError, "Git provenance failed"):
            self.create()
        self.assertFalse(self.paths.project_runs_dir.exists())
        unborn = self.base / "unborn"
        unborn.mkdir()
        result = subprocess.run(["git", "init", "-b", "main", str(unborn)], capture_output=True)
        self.assertEqual(result.returncode, 0)
        with self.assertRaises(runs.RunManifestError):
            runs.capture_git_provenance(unborn)

    def test_cli_create_show_list_validate_and_read_only(self):
        self.paths.project_data_dir.mkdir(parents=True)
        input_file = self.paths.project_data_dir / "cli-input.bin"
        input_file.write_bytes(b"CLI input fixture")
        status, out, err = self.cli(["runs", "create", "--kind", "infrastructure", "--seed", "0",
                                     "--description", "CLI fixture", "--run-id", "cli-test",
                                     "--config", str(self.source), "--input", str(input_file)])
        self.assertEqual((status, err), (0, ""))
        self.assertIn("Run created: cli-test", out)
        self.assertEqual(len(list(self.paths.project_runs_dir.iterdir())), 1)
        before = self.snapshot()
        status, out, err = self.cli(["runs", "show", "cli-test", "--json"])
        self.assertEqual((status, err), (0, ""))
        manifest = json.loads(out)
        self.assertEqual(manifest["configuration"]["random_seed"], 0)
        self.assertEqual(manifest["description"], "CLI fixture")
        self.assertIn("--run-id", manifest["configuration"]["argv"])
        self.assertEqual(manifest["configuration"]["file"]["sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(manifest["data_provenance"]["input_artifacts"], [{
            "path": str(input_file), "sha256": hashlib.sha256(input_file.read_bytes()).hexdigest()}])
        status, out, err = self.cli(["runs", "list", "--json"])
        self.assertEqual((status, err), (0, ""))
        self.assertEqual(json.loads(out)[0]["run_id"], "cli-test")
        status, out, err = self.cli(["runs", "validate", "cli-test"])
        self.assertEqual((status, err), (0, ""))
        self.assertIn("schema version 1", out)
        self.assertEqual(before, self.snapshot())
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_cli_dirty_failure_and_visible_override(self):
        (self.repository / "untracked.txt").write_bytes(b"dev")
        status, _, err = self.cli(["runs", "create", "--kind", "infrastructure"])
        self.assertEqual(status, 1)
        self.assertIn("--allow-dirty", err)
        self.assertFalse(self.paths.project_runs_dir.exists())
        status, _, err = self.cli(["runs", "create", "--kind", "infrastructure", "--allow-dirty"])
        self.assertEqual(status, 0)
        self.assertIn("WARNING: Noncanonical", err)

    def test_cli_errors_and_missing_read_commands(self):
        before = self.snapshot()
        for argv in (["runs", "show", "missing", "--json"], ["runs", "validate", "missing"],
                     ["runs", "create", "--kind", "infrastructure", "--run-id", "../escape"]):
            status, _, err = self.cli(argv)
            self.assertEqual(status, 1)
            self.assertIn("ERROR:", err)
        status, out, err = self.cli(["runs", "list", "--json"])
        self.assertEqual((status, json.loads(out), err), (0, [], ""))
        self.assertEqual(before, self.snapshot())

    def test_no_network_dependency(self):
        with patch.object(socket, "socket", side_effect=AssertionError("No network")), \
                patch.object(socket, "create_connection", side_effect=AssertionError("No network")), \
                patch.object(request, "urlopen", side_effect=AssertionError("No network")):
            target = self.create()
            runs.load_manifest(target.name, paths=self.paths)
            runs.list_runs(paths=self.paths)

    def test_import_without_directory_creation(self):
        before = self.snapshot()
        result = subprocess.run(
            [sys.executable, "-B", "-c", "from unittest.mock import patch; from pathlib import Path; "
             "guard = patch.object(Path, 'mkdir', side_effect=AssertionError('Unexpected write')); "
             "guard.start(); import stability_label_curation.run_manifest"],
            cwd=self.base, capture_output=True, text=True,
            env=dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1] / "src")),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(before, self.snapshot())

    def test_existing_paths_doctor_sources_regression(self):
        before = self.snapshot()
        status, out, err = self.cli(["paths", "--json"])
        self.assertEqual((status, json.loads(out), err), (0, self.paths.as_dict(), ""))
        self.assertEqual(self.cli(["doctor"])[0], 0)
        actual_registry = Path(__file__).resolve().parents[1] / runs.SOURCE_MANIFEST
        status, out, err = self.cli(["sources", "validate", "--manifest", str(actual_registry)])
        self.assertEqual((status, err), (0, ""))
        self.assertIn("7 sources validated", out)
        self.assertEqual(before, self.snapshot())


if __name__ == "__main__":
    unittest.main()
