from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SKILL_ROOT = Path(__file__).resolve().parents[1]
PROBE = SKILL_ROOT / "scripts" / "repo_probe.py"


def run_probe_raw(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(PROBE), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=20,
    )


def run_probe(root: Path, *extra_args: str) -> dict:
    proc = run_probe_raw([str(root), *extra_args])
    if proc.returncode != 0:
        raise AssertionError(f"probe failed: rc={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    if proc.stderr != "":
        raise AssertionError(f"expected empty stderr on success, got: {proc.stderr!r}")
    return json.loads(proc.stdout)


class RepoProbeTests(unittest.TestCase):
    def test_discovers_expected_signals_without_emitting_contents(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / ".github" / "workflows").mkdir(parents=True)
            (root / "tests").mkdir()
            (root / "ops").mkdir()
            (root / "migrations").mkdir()
            (root / "deploy" / "k8s").mkdir(parents=True)
            (root / "src").mkdir()

            (root / "package.json").write_text('{"scripts":{"test":"node test.js"}}', encoding="utf-8")
            (root / "package-lock.json").write_text('{}', encoding="utf-8")
            (root / ".github" / "workflows" / "ci.yml").write_text("name: ci\n", encoding="utf-8")
            (root / "tests" / "service.test.ts").write_text("// semantic test\n", encoding="utf-8")
            (root / "ops" / "runbook.md").write_text("Restore drill and rollback procedure. RTO 30m.\n", encoding="utf-8")
            (root / "migrations" / "001_init.sql").write_text("create table x(id int);\n", encoding="utf-8")
            (root / "deploy" / "k8s" / "deployment.yaml").write_text("kind: Deployment\n", encoding="utf-8")
            (root / "src" / "telemetry.ts").write_text("// OpenTelemetry tracing\n", encoding="utf-8")
            secret_value = "SUPER_SECRET_DO_NOT_EMIT_9f2d1"
            (root / ".env").write_text(f"API_TOKEN={secret_value}\n", encoding="utf-8")

            report = run_probe(root)
            encoded = json.dumps(report)

            self.assertIn("package.json", report["signals"]["manifests"])
            self.assertIn("package-lock.json", report["signals"]["lockfiles"])
            self.assertIn(".github/workflows/ci.yml", report["signals"]["ci"])
            self.assertIn("tests/service.test.ts", report["signals"]["tests"])
            self.assertIn("ops/runbook.md", report["signals"]["runbooks_ops"])
            self.assertIn("migrations/001_init.sql", report["signals"]["migrations"])
            self.assertIn("deploy/k8s/deployment.yaml", report["signals"]["orchestration"])
            self.assertIn("src/telemetry.ts", report["content_signal_files"]["observability"])
            self.assertIn("ops/runbook.md", report["content_signal_files"]["backup_restore"])
            self.assertNotIn(secret_value, encoded)
            self.assertNotIn("API_TOKEN=", encoded)
            self.assertNotIn(".env", encoded)

    @unittest.skipUnless(shutil.which("git"), "git unavailable")
    def test_reports_candidate_identity_and_dirty_state_without_file_contents(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.invalid"], check=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Probe Test"], check=True)
            (root / "README.md").write_text("hello\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True)
            subprocess.run(["git", "-C", str(root), "commit", "-q", "-m", "init"], check=True)

            clean = run_probe(root)
            self.assertTrue(clean["git"]["is_repo"])
            self.assertFalse(clean["git"]["dirty"])
            self.assertEqual("collected", clean["git"]["status"])
            self.assertIsNone(clean["git"]["status_skip_reason"])
            self.assertEqual(40, len(clean["git"]["head"]))

            (root / "README.md").write_text("changed\n", encoding="utf-8")
            dirty = run_probe(root)
            self.assertTrue(dirty["git"]["dirty"])
            self.assertGreaterEqual(dirty["git"]["status_entry_count"], 1)
            self.assertNotIn("changed", json.dumps(dirty))

    def test_file_cap_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for i in range(5):
                (root / f"f{i}.txt").write_text("x", encoding="utf-8")
            proc = subprocess.run(
                [sys.executable, str(PROBE), str(root), "--max-files", "2"],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=20,
            )
            self.assertEqual(0, proc.returncode, proc.stderr)
            self.assertEqual("", proc.stderr)
            report = json.loads(proc.stdout)
            self.assertTrue(report["scan"]["capped"])
            self.assertEqual(2, report["scan"]["file_count"])
            self.assertTrue(any("incomplete" in x.lower() for x in report["limitations"]))

    def test_nonexistent_path_exits_2_with_empty_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            missing = Path(td) / "does-not-exist"
            proc = run_probe_raw([str(missing)])
            self.assertEqual(2, proc.returncode)
            self.assertEqual("", proc.stdout)

    def test_file_argument_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            file_path = Path(td) / "not-a-dir.txt"
            file_path.write_text("x", encoding="utf-8")
            proc = run_probe_raw([str(file_path)])
            self.assertEqual(2, proc.returncode)
            self.assertEqual("", proc.stdout)

    def test_max_files_zero_exits_2(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            proc = run_probe_raw([str(td), "--max-files", "0"])
            self.assertEqual(2, proc.returncode)
            self.assertEqual("", proc.stdout)

    def test_symlink_loop_and_broken_symlink_are_handled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "loop").mkdir()
            try:
                (root / "loop" / "self").symlink_to(root / "loop", target_is_directory=True)
                (root / "broken").symlink_to(root / "does-not-exist-target")
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"symlinks unsupported: {exc}")
            (root / "real.txt").write_text("hello\n", encoding="utf-8")

            report = run_probe(root)
            self.assertEqual(1, report["scan"]["file_count"])  # only real.txt; symlinks are never followed
            self.assertNotIn("loop/", json.dumps(report))
            self.assertNotIn("broken", json.dumps(report))

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "running as root bypasses permission checks")
    def test_permission_denied_subdirectory_produces_warning(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            blocked = root / "blocked"
            blocked.mkdir()
            (blocked / "secretish.txt").write_text("x", encoding="utf-8")
            (root / "visible.txt").write_text("x", encoding="utf-8")
            try:
                blocked.chmod(0o000)
                report = run_probe(root)
            finally:
                blocked.chmod(0o755)

            self.assertIsInstance(report, dict)
            self.assertTrue(report["warnings"], "expected a warning for the unreadable subdirectory")
            encoded = json.dumps(report["warnings"])
            self.assertNotIn(str(root), encoded)
            for warning in report["warnings"]:
                self.assertIsInstance(warning, dict)
                self.assertIn("path", warning)
                self.assertIn("error", warning)
                self.assertFalse(Path(warning["path"]).is_absolute())

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "running as root bypasses permission checks")
    def test_unreadable_root_exits_3(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "locked"
            root.mkdir()
            try:
                root.chmod(0o000)
                proc = run_probe_raw([str(root)])
            finally:
                root.chmod(0o755)

            self.assertEqual(3, proc.returncode)
            self.assertEqual("", proc.stdout)
            self.assertNotEqual("", proc.stderr)

    def test_non_utf8_filename_is_handled(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bad_name = b"bad-\xff\xfe-name.txt"
            try:
                fd = os.open(
                    os.path.join(os.fsencode(str(root)), bad_name),
                    os.O_CREAT | os.O_WRONLY,
                    0o644,
                )
                os.close(fd)
            except OSError as exc:
                self.skipTest(f"filesystem rejects non-UTF-8 names: {exc}")

            report = run_probe(root)
            self.assertIsInstance(report, dict)

    def test_submodule_gitlink_file_not_counted(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "lib").mkdir()
            (root / "lib" / ".git").write_text("gitdir: ../.git/modules/lib\n", encoding="utf-8")
            (root / "lib" / "code.py").write_text("print('hi')\n", encoding="utf-8")

            report = run_probe(root)
            self.assertEqual(1, report["scan"]["file_count"])

    def test_secret_fixture_names_and_contents_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            env_secret = "ENV_SENTINEL_7a1c9"
            key_secret = "RSA_SENTINEL_3e8b2"
            pem_secret = "PEM_SENTINEL_5d4f1"
            (root / ".env").write_text(f"TOKEN={env_secret}\n", encoding="utf-8")
            (root / "id_rsa").write_text(f"-----BEGIN {key_secret}-----\n", encoding="utf-8")
            (root / "server.pem").write_text(f"-----BEGIN {pem_secret}-----\n", encoding="utf-8")

            proc = run_probe_raw([str(root)])
            self.assertEqual(0, proc.returncode)
            self.assertEqual("", proc.stderr)
            report = json.loads(proc.stdout)
            self.assertIsInstance(report, dict)

            self.assertNotIn(env_secret, proc.stdout)
            self.assertNotIn(key_secret, proc.stdout)
            self.assertNotIn(pem_secret, proc.stdout)
            self.assertNotIn(".env", proc.stdout)
            self.assertNotIn("id_rsa", proc.stdout)

    def test_max_seconds_zero_exhausts_time_budget(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "a.txt").write_text("x", encoding="utf-8")
            report = run_probe(root, "--max-seconds", "0")
            self.assertTrue(report["scan"]["time_budget_exhausted"])

    def test_signed_release_matches_attestations_and_negative_budgets_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wf = root / ".github" / "workflows"
            wf.mkdir(parents=True)
            (wf / "release.yml").write_text("permissions:\n  attestations: write\n", encoding="utf-8")
            report = run_probe(root)
            self.assertIn("signed_release", report["content_signal_files"])
            self.assertIn("ci_permissions", report["content_signal_files"])
            for flag in ("--max-seconds", "--max-text-bytes"):
                proc = run_probe_raw([str(root), flag, "-1"])
                self.assertEqual(2, proc.returncode)
                self.assertEqual("", proc.stdout)

    def test_per_file_cap_is_reported_even_under_a_large_total_budget(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "huge.md").write_bytes(b"rollback " * (1_000_000 // 8 + 1))  # above the per-file cap MAX_TEXT_BYTES
            (root / "small.md").write_text("rollback\n", encoding="utf-8")
            report = run_probe(root)
            self.assertEqual(1, report["scan"]["text_files_skipped_oversize"])
            self.assertFalse(report["scan"]["text_budget_exhausted"])
            self.assertTrue(any("not content-scanned" in l for l in report["limitations"]))

    def test_text_budget_stops_content_scanning_but_not_classification(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "big.md").write_text("rollback " * 2000, encoding="utf-8")
            for i in range(5):
                (root / f"small{i}.md").write_text("rollback\n", encoding="utf-8")
            # Budget of 30 bytes: big.md (oversized) is skipped without ending the scan; the
            # 9-byte small files are scanned until the budget is consumed (3 fit), then scanning stops.
            report = run_probe(root, "--max-text-bytes", "30")
            self.assertEqual(1, report["scan"]["text_files_skipped_oversize"])
            self.assertTrue(report["scan"]["text_budget_exhausted"])
            self.assertEqual(3, report["scan"]["text_files_scanned_for_signal_presence"])
            self.assertEqual(6, report["scan"]["files_classified"])

    def test_scan_root_stays_inside_requested_subdirectory(self) -> None:
        if not shutil.which("git"):
            self.skipTest("git not available")
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "outside.md").write_text("runbook\n", encoding="utf-8")
            sub = root / "svc"
            sub.mkdir()
            (sub / "inside.md").write_text("runbook\n", encoding="utf-8")
            report = run_probe(sub)
            self.assertEqual(str(sub.resolve()), report["root"])
            self.assertEqual(1, report["scan"]["file_count"])
            self.assertNotIn("outside.md", json.dumps(report))
            self.assertTrue(any("inside repository" in x for x in report["limitations"]))

    def test_signal_path_cap_truncation_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for i in range(30):
                (root / f"f{i}.test.js").write_text("// test\n", encoding="utf-8")

            report = run_probe(root)
            self.assertEqual(25, len(report["signals"]["tests"]))
            self.assertIn("tests", report["truncated_signals"])

    def test_sensitivity_is_relative_to_scan_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "credentials" / "repo"
            repo.mkdir(parents=True)
            (repo / "package.json").write_text("{}\n", encoding="utf-8")
            (repo / "secrets" / "x").mkdir(parents=True)
            (repo / "secrets" / "x" / "package.json").write_text("{}\n", encoding="utf-8")
            report = run_probe(repo)
            self.assertIn("manifests", report["signals"])
            self.assertEqual(["package.json"], report["signals"]["manifests"])


def _git(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True)


HARDENED_STATUS = ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "status", "--porcelain"]
NO_LOCKS_ENV = {**os.environ, "GIT_OPTIONAL_LOCKS": "0"}


def _make_repo(root: Path, attributes: str = "f.txt filter=x\n") -> None:
    root.mkdir(parents=True)
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Probe Test")
    (root / ".gitattributes").write_text(attributes, encoding="utf-8")
    (root / "f.txt").write_text("a\n", encoding="utf-8")
    _git(root, "add", ".")
    # The driver is defined only after this commit, so committing never runs it.
    _git(root, "commit", "-q", "-m", "init")


def _stat_dirty(path: Path) -> None:
    """Change the content (never back to the committed "a") but not the size, and move the
    mtime, so git must hash the file to compare it."""
    path.write_text("c\n" if path.read_text(encoding="utf-8") == "b\n" else "b\n", encoding="utf-8")
    t = path.stat().st_mtime + 5
    os.utime(path, (t, t))


def _touch_cmd(marker: Path) -> str:
    return "touch {}; cat".format(shlex.quote(str(marker)))


@unittest.skipUnless(os.name == "posix" and shutil.which("git"), "filter-driver probes need git and a POSIX shell")
class FilterDriverTests(unittest.TestCase):
    """Each test first proves the vector fires under plain hardened `git status` (the control),
    then proves the probe does not run it."""

    def assert_blocked(self, root: Path, dirty_file: Path, marker: Path) -> dict:
        _stat_dirty(dirty_file)
        subprocess.run(HARDENED_STATUS, cwd=str(root), env=NO_LOCKS_ENV, capture_output=True)
        self.assertTrue(marker.exists(), "control: the vector did not fire under plain git status")
        marker.unlink()
        _stat_dirty(dirty_file)
        report = run_probe(root)
        self.assertFalse(marker.exists(), "the probe ran a repository-defined filter")
        return report

    def test_clean_filter_is_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root, marker = Path(td) / "r", Path(td) / "marker"
            _make_repo(root)
            _git(root, "config", "filter.x.clean", _touch_cmd(marker))
            report = self.assert_blocked(root, root / "f.txt", marker)
            self.assertEqual("collected", report["git"]["status"])
            self.assertTrue(report["git"]["dirty"])

    def test_process_filter_is_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root, marker = Path(td) / "r", Path(td) / "marker"
            _make_repo(root)
            _git(root, "config", "filter.x.process", "sh -c 'touch {}; exit 1'".format(shlex.quote(str(marker))))
            self.assert_blocked(root, root / "f.txt", marker)

    def test_required_filter_is_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root, marker = Path(td) / "r", Path(td) / "marker"
            _make_repo(root)
            _git(root, "config", "filter.x.clean", _touch_cmd(marker))
            _git(root, "config", "filter.x.required", "true")
            report = self.assert_blocked(root, root / "f.txt", marker)
            self.assertEqual("collected", report["git"]["status"])

    def test_include_path_filter_is_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root, marker = Path(td) / "r", Path(td) / "marker"
            _make_repo(root)
            (root / ".git" / "extra.cfg").write_text(
                '[filter "x"]\n\tclean = "{}"\n'.format(_touch_cmd(marker)), encoding="utf-8")
            _git(root, "config", "include.path", "extra.cfg")
            self.assert_blocked(root, root / "f.txt", marker)

    def test_worktree_scope_filter_is_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root, marker = Path(td) / "r", Path(td) / "marker"
            _make_repo(root)
            _git(root, "config", "core.repositoryformatversion", "1")
            _git(root, "config", "extensions.worktreeConfig", "true")
            _git(root, "config", "--worktree", "filter.x.clean", _touch_cmd(marker))
            self.assert_blocked(root, root / "f.txt", marker)

    def test_worktree_config_is_read_whatever_an_include_says(self) -> None:
        # git takes extensions.worktreeConfig from .git/config alone, so an included file that sets
        # it to false must not stop the probe from reading config.worktree.
        with tempfile.TemporaryDirectory() as td:
            root, marker = Path(td) / "r", Path(td) / "marker"
            _make_repo(root)
            _git(root, "config", "core.repositoryformatversion", "1")
            _git(root, "config", "extensions.worktreeConfig", "true")
            _git(root, "config", "--worktree", "filter.x.clean", _touch_cmd(marker))
            (root / ".git" / "extra.cfg").write_text("[extensions]\n\tworktreeConfig = false\n", encoding="utf-8")
            _git(root, "config", "include.path", "extra.cfg")
            report = self.assert_blocked(root, root / "f.txt", marker)
            self.assertEqual("collected", report["git"]["status"])

    def test_linked_worktree_config_filter_is_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root, linked, marker = Path(td) / "r", Path(td) / "w", Path(td) / "marker"
            _make_repo(root)
            _git(root, "config", "core.repositoryformatversion", "1")
            _git(root, "config", "extensions.worktreeConfig", "true")
            _git(root, "worktree", "add", "-q", str(linked))
            _git(linked, "config", "--worktree", "filter.x.clean", _touch_cmd(marker))
            report = self.assert_blocked(linked, linked / "f.txt", marker)
            self.assertEqual("collected", report["git"]["status"])

    def test_submodule_filter_is_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            sub, root, marker = Path(td) / "sub", Path(td) / "r", Path(td) / "marker"
            _make_repo(sub, "f.txt filter=y\n")
            _make_repo(root, "g.txt -text\n")
            _git(root, "-c", "protocol.file.allow=always", "submodule", "-q", "add", str(sub), "sub")
            _git(root, "commit", "-q", "-m", "add submodule")
            _git(root / "sub", "config", "filter.y.clean", _touch_cmd(marker))
            self.assert_blocked(root, root / "sub" / "f.txt", marker)

    def test_linked_worktree_without_extension_collects_status(self) -> None:
        # Without extensions.worktreeConfig, `git config --worktree` exits 128 once a linked
        # worktree exists; the probe must still collect status, from either worktree.
        with tempfile.TemporaryDirectory() as td:
            root, linked, marker = Path(td) / "r", Path(td) / "w", Path(td) / "marker"
            _make_repo(root)
            _git(root, "worktree", "add", "-q", str(linked))
            _git(root, "config", "filter.x.clean", _touch_cmd(marker))
            report = self.assert_blocked(root, root / "f.txt", marker)
            self.assertEqual("collected", report["git"]["status"])
            report = self.assert_blocked(linked, linked / "f.txt", marker)
            self.assertEqual("collected", report["git"]["status"])

    def test_submodule_commit_drift_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            sub, root, marker = Path(td) / "sub", Path(td) / "r", Path(td) / "marker"
            _make_repo(sub, "f.txt filter=y\n")
            _make_repo(root, "g.txt -text\n")
            _git(root, "-c", "protocol.file.allow=always", "submodule", "-q", "add", str(sub), "sub")
            _git(root, "commit", "-q", "-m", "add submodule")
            (root / "sub" / "f.txt").write_text("b\n", encoding="utf-8")
            _git(root / "sub", "-c", "user.email=test@example.invalid", "-c", "user.name=Probe Test",
                 "commit", "-q", "-am", "move the submodule to another commit")
            _git(root / "sub", "config", "filter.y.clean", _touch_cmd(marker))
            _stat_dirty(root / "sub" / "f.txt")
            report = run_probe(root)
            self.assertFalse(marker.exists(), "the probe ran a submodule's filter")
            self.assertEqual("collected", report["git"]["status"])
            self.assertTrue(report["git"]["dirty"])

    def test_racily_clean_entry_does_not_run_filter(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root, marker = Path(td) / "r", Path(td) / "marker"
            _make_repo(root)
            _git(root, "config", "filter.x.clean", _touch_cmd(marker))
            # Rewrite the index, then change the file at the same size: whether git sees the entry
            # as stat-dirty or as racily clean, it must hash the file.
            subprocess.run(["git", "-c", "filter.x.clean=cat", "update-index", "--really-refresh"],
                           cwd=str(root), capture_output=True)
            (root / "f.txt").write_text("b\n", encoding="utf-8")
            subprocess.run(HARDENED_STATUS, cwd=str(root), env=NO_LOCKS_ENV, capture_output=True)
            self.assertTrue(marker.exists(), "control: the racy entry did not trigger the filter")
            marker.unlink()
            subprocess.run(["git", "-c", "filter.x.clean=cat", "update-index", "--really-refresh"],
                           cwd=str(root), capture_output=True)
            (root / "f.txt").write_text("a\n", encoding="utf-8")
            run_probe(root)
            self.assertFalse(marker.exists(), "the probe ran a repository-defined filter")

    def test_driver_name_with_dots_and_capitals_is_neutralised(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root, marker = Path(td) / "r", Path(td) / "marker"
            _make_repo(root, "f.txt filter=My.Driver\n")
            _git(root, "config", "filter.My.Driver.clean", _touch_cmd(marker))
            report = self.assert_blocked(root, root / "f.txt", marker)
            self.assertEqual("collected", report["git"]["status"])

    def test_unneutralisable_driver_name_skips_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root, marker = Path(td) / "r", Path(td) / "marker"
            _make_repo(root, "f.txt filter=a=b\n")
            with open(root / ".git" / "config", "a", encoding="utf-8") as f:
                f.write('[filter "a=b"]\n\tclean = "{}"\n'.format(_touch_cmd(marker)))
            report = self.assert_blocked(root, root / "f.txt", marker)
            git = report["git"]
            self.assertEqual("not collected", git["status"])
            self.assertIn("a=b", git["status_skip_reason"])
            self.assertIsNone(git["dirty"])
            self.assertIsNone(git["status_entry_count"])
            self.assertIsNone(git["status_code_counts"])

    def test_conditional_include_resolved_like_git_status(self) -> None:
        # A hasconfig: condition in .git/config can match a remote URL that only config.worktree
        # defines; git status sees both files, so the probe must resolve it the same way.
        with tempfile.TemporaryDirectory() as td:
            root, marker = Path(td) / "r", Path(td) / "marker"
            _make_repo(root, "f.txt filter=evil\n")
            _git(root, "config", "core.repositoryformatversion", "1")
            _git(root, "config", "extensions.worktreeConfig", "true")
            (root / ".git" / "drv.cfg").write_text(
                '[filter "evil"]\n\tclean = "{}"\n'.format(_touch_cmd(marker)), encoding="utf-8")
            with open(root / ".git" / "config", "a", encoding="utf-8") as f:
                f.write('[includeIf "hasconfig:remote.*.url:https://example.invalid/*"]\n\tpath = drv.cfg\n')
            _git(root, "config", "--worktree", "remote.r.url", "https://example.invalid/r")
            report = self.assert_blocked(root, root / "f.txt", marker)
            self.assertEqual("collected", report["git"]["status"])

    def test_driver_name_with_a_line_separator_character_is_neutralised(self) -> None:
        # Python's str.splitlines() also breaks on \x1c; git prints the name on one line.
        with tempfile.TemporaryDirectory() as td:
            root, marker = Path(td) / "r", Path(td) / "marker"
            _make_repo(root, "f.txt filter=p.q\x1cfilter.r\n")
            with open(root / ".git" / "config", "a", encoding="utf-8") as f:
                f.write('[filter "p.q\x1cfilter.r"]\n\tclean = "{}"\n'.format(_touch_cmd(marker)))
            report = self.assert_blocked(root, root / "f.txt", marker)
            self.assertEqual("collected", report["git"]["status"])

    def test_partial_clone_lazy_fetch_is_not_run(self) -> None:
        # A missing object in a partial clone makes git status fetch it through the promisor
        # remote, whose transport the repository configures (here remote.<name>.uploadpack).
        with tempfile.TemporaryDirectory() as td:
            root, marker = Path(td) / "r", Path(td) / "marker"
            _make_repo(root, "g.txt -text\n")
            _git(root, "config", "core.repositoryformatversion", "1")
            _git(root, "config", "extensions.partialClone", "origin")
            _git(root, "config", "remote.origin.url", ".")
            _git(root, "config", "remote.origin.promisor", "true")
            _git(root, "config", "remote.origin.uploadpack", "touch {}; git-upload-pack".format(shlex.quote(str(marker))))
            tree = _git(root, "rev-parse", "HEAD^{tree}").stdout.strip()
            (root / ".git" / "objects" / tree[:2] / tree[2:]).unlink()
            subprocess.run(HARDENED_STATUS, cwd=str(root), env=NO_LOCKS_ENV, capture_output=True)
            self.assertTrue(marker.exists(), "control: the lazy fetch did not run")
            marker.unlink()
            report = run_probe(root)
            self.assertFalse(marker.exists(), "the probe let git status fetch through the repository's remote")
            self.assertEqual("not collected", report["git"]["status"])
            self.assertIn("partial clone", report["git"]["status_skip_reason"])

    def test_unstaged_change_on_the_first_status_line_keeps_its_code(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "r"
            _make_repo(root, "g.txt -text\n")
            (root / "f.txt").write_text("changed\n", encoding="utf-8")
            report = run_probe(root)
            self.assertEqual({" M": 1}, report["git"]["status_code_counts"])

    def test_unborn_head_is_reported_as_none(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "r"
            root.mkdir()
            _git(root, "init", "-q")
            report = run_probe(root)
            self.assertIsNone(report["git"]["head"])

    def test_user_level_filter_driver_still_applies(self) -> None:
        # Drivers from the user's own global config (for example git-lfs) are trusted and stay
        # in effect, so status keeps comparing cleaned content.
        with tempfile.TemporaryDirectory() as td:
            root, global_config = Path(td) / "r", Path(td) / "gitconfig"
            _make_repo(root, "f.txt filter=g\n")
            global_config.write_text('[filter "g"]\n\tclean = sed s/b/a/\n', encoding="utf-8")
            (root / "f.txt").write_text("b\n", encoding="utf-8")
            with mock.patch.dict(os.environ, {"GIT_CONFIG_GLOBAL": str(global_config)}):
                report = run_probe(root)
            self.assertEqual("collected", report["git"]["status"])
            self.assertFalse(report["git"]["dirty"])

    def test_bare_promisor_key_skips_status(self) -> None:
        # git reads a bare `promisor` line (no value) as true.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "r"
            _make_repo(root, "g.txt -text\n")
            with open(root / ".git" / "config", "a", encoding="utf-8") as f:
                f.write('[remote "origin"]\n\turl = .\n\tpromisor\n')
            report = run_probe(root)
            self.assertEqual("not collected", report["git"]["status"])
            self.assertIn("partial clone", report["git"]["status_skip_reason"])

    def test_assume_unchanged_entry_is_not_reported_clean(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "r"
            _make_repo(root, "g.txt -text\n")
            _git(root, "update-index", "--assume-unchanged", "f.txt")
            (root / "f.txt").write_text("changed\n", encoding="utf-8")
            report = run_probe(root)
            self.assertEqual("not collected", report["git"]["status"])
            self.assertIn("assume-unchanged", report["git"]["status_skip_reason"])
            self.assertIsNone(report["git"]["dirty"])

    def test_replace_ref_does_not_hide_changes(self) -> None:
        # A refs/replace entry for HEAD would make status compare against another commit's tree.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "r"
            _make_repo(root, "g.txt -text\n")
            head = _git(root, "rev-parse", "HEAD").stdout.strip()
            (root / "f.txt").write_text("changed\n", encoding="utf-8")
            _git(root, "add", "f.txt")
            tree = _git(root, "write-tree").stdout.strip()
            fake = _git(root, "commit-tree", tree, "-m", "replacement").stdout.strip()
            _git(root, "replace", head, fake)
            report = run_probe(root)
            self.assertEqual(head, report["git"]["head"])
            self.assertTrue(report["git"]["dirty"])

    def test_work_tree_elsewhere_is_not_reported(self) -> None:
        # core.worktree can point git at another directory; its status says nothing about the scan root.
        with tempfile.TemporaryDirectory() as td:
            root, other = Path(td) / "r", Path(td) / "other"
            _make_repo(root, "g.txt -text\n")
            _make_repo(other, "g.txt -text\n")
            (root / "f.txt").write_text("changed\n", encoding="utf-8")
            _git(root, "config", "core.worktree", str(other))
            report = run_probe(root)
            self.assertNotEqual("collected", report["git"].get("status"))

    def test_failed_status_is_reported_not_collected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "r"
            _make_repo(root, "g.txt -text\n")
            (root / ".git" / "index").write_bytes(b"not an index")
            report = run_probe(root)
            self.assertEqual("not collected", report["git"]["status"])
            self.assertRegex(report["git"]["status_skip_reason"], r"git (ls-files|status) failed")
            self.assertIsNone(report["git"]["dirty"])


if __name__ == "__main__":
    unittest.main()
