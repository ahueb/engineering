from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parents[1]
PROBE = SKILL_ROOT / "scripts" / "repo_probe.py"


def run_probe(root: Path) -> dict:
    proc = subprocess.run(
        [sys.executable, str(PROBE), str(root)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=20,
    )
    if proc.returncode != 0:
        raise AssertionError(f"probe failed: rc={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}")
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
            report = json.loads(proc.stdout)
            self.assertTrue(report["scan"]["capped"])
            self.assertEqual(2, report["scan"]["file_count"])
            self.assertTrue(any("incomplete" in x.lower() for x in report["limitations"]))


if __name__ == "__main__":
    unittest.main()
