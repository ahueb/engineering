from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
