import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts import comment_guidance_checks as cgc  # noqa: E402

SUPPORT_DIR = REPO_ROOT / "plugins" / "engineering" / "evals" / "comment-guidance-support"
FIXTURES_PATH = SUPPORT_DIR / "fixtures.json"
MANIFEST_PATH = SUPPORT_DIR / "manifest.json"
BUILD_FIXTURE = SUPPORT_DIR / "build_fixture.py"
CHECKER = REPO_ROOT / "scripts" / "comment_guidance_checks.py"


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)

    def tearDown(self):
        self._td.cleanup()


def build_case(root, case_id):
    workspace = root / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [sys.executable, str(BUILD_FIXTURE), "--case", case_id, "--workspace", str(workspace)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, "build_fixture failed: {}\n{}".format(result.stdout, result.stderr)
    return workspace


def run_artifacts_cli(case_id, candidate, report_path):
    result = subprocess.run(
        [
            sys.executable, str(CHECKER), "artifacts",
            "--case", case_id,
            "--fixtures", str(FIXTURES_PATH),
            "--manifest", str(MANIFEST_PATH),
            "--candidate", str(candidate),
            "--report", str(report_path),
        ],
        capture_output=True, text=True,
    )
    return result


def run_artifacts_inproc(case_id, candidate, report_path):
    rc = cgc.main(
        [
            "artifacts",
            "--case", case_id,
            "--fixtures", str(FIXTURES_PATH),
            "--manifest", str(MANIFEST_PATH),
            "--candidate", str(candidate),
            "--report", str(report_path),
        ]
    )
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    return rc, report


def rd(path):
    """Read text without newline translation (Windows would otherwise turn LF into CRLF on
    the write-back and trip the line-ending check)."""
    with open(path, "r", encoding="utf-8", newline="") as f:
        return f.read()


def rmtree_force(path):
    """shutil.rmtree that also removes read-only entries: git writes .git/objects/** read-only,
    which makes a plain rmtree fail on Windows with PermissionError."""
    def _onerror(func, target, _exc):
        os.chmod(target, 0o700)
        func(target)
    shutil.rmtree(path, onerror=_onerror)


def wr(path, text):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(text)


def fail_checks(report):
    return [c for c in report["checks"] if c["status"] == "FAIL"]


def error_checks(report):
    return [c for c in report["checks"] if c["status"] == "ERROR"]


# --------------------------------------------------------------------------
# Mutation-table coverage, case behaviour-comment-cleanup
# --------------------------------------------------------------------------


class ArtifactMutationTests(TempDirCase):
    CASE = "behaviour-comment-cleanup"

    def build(self):
        return build_case(self.root, self.CASE)

    def check(self, workspace):
        report_path = self.root / "report.json"
        return run_artifacts_inproc(self.CASE, workspace, report_path)

    def test_unchanged_fixture_passes(self):
        workspace = self.build()
        rc, report = self.check(workspace)
        self.assertEqual(rc, 0)
        self.assertEqual(report["artifact_status"], "PASS")
        self.assertEqual(report["semantic_status"], "REQUIRES_REVIEW")

    def test_authorized_redundant_comment_removal_passes(self):
        workspace = self.build()
        path = workspace / "src" / "py" / "contracts.py"
        lines = rd(path).splitlines(keepends=True)
        lines = [l for l in lines if l.strip() != "# increment i"]
        wr(path, "".join(lines))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 0, fail_checks(report) + error_checks(report))

    def test_equivalent_multiline_prose_rewrite_passes_structurally(self):
        workspace = self.build()
        path = workspace / "src" / "py" / "help_cli.py"
        # help_cli.py is immutable in the manifest; rewrite an unrelated, non-immutable
        # multi-line docstring elsewhere instead: contracts.py's module docstring.
        contracts = workspace / "src" / "py" / "contracts.py"
        text = rd(contracts)
        old_doc_start = '"""Contract for select_window.'
        self.assertIn(old_doc_start, text)
        new_first_line = '"""Contract for select_window (rephrased, same facts).'
        text = text.replace(old_doc_start, new_first_line, 1)
        wr(contracts, text)
        rc, report = self.check(workspace)
        self.assertEqual(rc, 0, fail_checks(report) + error_checks(report))

    def test_changed_constant_fails(self):
        workspace = self.build()
        path = workspace / "src" / "py" / "contracts.py"
        wr(path, rd(path).replace("NS_PER_US = 1000", "NS_PER_US = 2000"))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(fail_checks(report))

    def test_changed_ordinary_string_literal_fails(self):
        workspace = self.build()
        path = workspace / "src" / "py" / "contracts.py"
        wr(path, rd(path).replace('"# not a comment"', '"not a comment at all"'))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(fail_checks(report))

    def test_directive_moved_to_different_statement_fails(self):
        workspace = self.build()
        path = workspace / "src" / "py" / "app.py"
        text = rd(path)
        text = text.replace(
            "def load_config(path):  # noqa: E501\n    # TODO",
            "def load_config(path):\n    # noqa: E501\n    # TODO",
        )
        wr(path, text)
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(fail_checks(report))

    def test_go_build_directive_group_separator_changed_fails(self):
        workspace = self.build()
        path = workspace / "src" / "go" / "build_linux.go"
        text = rd(path)
        text = text.replace(
            "//go:build linux\n// +build linux\n\npackage pkg",
            "//go:build linux\n\n// +build linux\npackage pkg",
        )
        wr(path, text)
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(fail_checks(report))

    def test_legacy_go_build_line_removed_fails(self):
        workspace = self.build()
        path = workspace / "src" / "go" / "build_linux.go"
        lines = rd(path).splitlines(keepends=True)
        lines = [l for l in lines if l.strip() != "// +build linux"]
        wr(path, "".join(lines))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(fail_checks(report))

    def test_generated_file_edit_fails(self):
        workspace = self.build()
        path = workspace / "src" / "gen" / "schema.py"
        wr(path, rd(path) + "\n# extra\n")
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(fail_checks(report))

    def test_vendor_file_edit_fails(self):
        workspace = self.build()
        path = workspace / "src" / "vendor" / "third_party.py"
        wr(path, rd(path) + "\n# extra\n")
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(fail_checks(report))

    def test_license_file_edit_fails(self):
        workspace = self.build()
        path = workspace / "LICENSE.fixture"
        wr(path, rd(path) + "\nEXTRA\n")
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(fail_checks(report))

    def test_structured_help_block_changed_fails(self):
        workspace = self.build()
        path = workspace / "src" / "py" / "help_cli.py"
        wr(path, rd(path).replace("usage: help_cli.py [--help]", "usage: help_cli.py [-h]"))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(fail_checks(report))

    def test_doctest_changed_fails(self):
        workspace = self.build()
        path = workspace / "src" / "py" / "contracts.py"
        wr(path, rd(path).replace(">>> clamp_ns(15)\n    9", ">>> clamp_ns(15)\n    8"))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(fail_checks(report))

    def test_checker_overwritten_in_workspace_flagged_unexpected(self):
        workspace = self.build()
        (workspace / "scripts").mkdir(parents=True, exist_ok=True)
        shutil.copy(CHECKER, workspace / "scripts" / "comment_guidance_checks.py")
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(fail_checks(report))

    def test_success_marker_without_valid_artifacts_cannot_pass(self):
        workspace = self.build()
        wr(workspace / "SUCCESS", "DONE\n")
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(fail_checks(report))

    def test_crlf_to_lf_change_fails(self):
        workspace = self.build()
        path = workspace / "src" / "web" / "bundle.config.js"
        data = path.read_bytes().replace(b"\r\n", b"\n")
        path.write_bytes(data)
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["status"] == "FAIL" and "line_endings_changed" in c["detail"] for c in report["checks"]))

    def test_symlink_in_candidate_exits_2(self):
        workspace = self.build()
        target = self.root / "outside.txt"
        wr(target, "secret\n")
        try:
            (workspace / "evil_link").symlink_to(target)
        except OSError:
            self.skipTest("symlinks unsupported on this filesystem")
        rc, report = self.check(workspace)
        self.assertEqual(rc, 2)
        self.assertTrue(error_checks(report))

    def test_manifest_traversal_path_exits_2(self):
        workspace = self.build()
        bad_manifest = self.root / "manifest_traversal.json"
        data = json.loads(rd(MANIFEST_PATH))
        data["cases"][self.CASE]["immutable_paths"].append("../escape.txt")
        wr(bad_manifest, json.dumps(data))
        report_path = self.root / "report.json"
        rc = cgc.main(
            [
                "artifacts", "--case", self.CASE,
                "--fixtures", str(FIXTURES_PATH),
                "--manifest", str(bad_manifest),
                "--candidate", str(workspace),
                "--report", str(report_path),
            ]
        )
        self.assertEqual(rc, 2)

    def test_missing_workspace_exits_2(self):
        report_path = self.root / "report.json"
        rc = cgc.main(
            [
                "artifacts", "--case", self.CASE,
                "--fixtures", str(FIXTURES_PATH),
                "--manifest", str(MANIFEST_PATH),
                "--candidate", str(self.root / "does-not-exist"),
                "--report", str(report_path),
            ]
        )
        self.assertEqual(rc, 2)

    def test_unknown_case_id_exits_2(self):
        workspace = self.build()
        report_path = self.root / "report.json"
        rc = cgc.main(
            [
                "artifacts", "--case", "not-a-real-case",
                "--fixtures", str(FIXTURES_PATH),
                "--manifest", str(MANIFEST_PATH),
                "--candidate", str(workspace),
                "--report", str(report_path),
            ]
        )
        self.assertEqual(rc, 2)

    def test_oversized_file_exits_2(self):
        workspace = self.build()
        report_path = self.root / "report.json"
        big_manifest = self.root / "manifest_small_limit.json"
        data = json.loads(rd(MANIFEST_PATH))
        data["cases"][self.CASE]["max_file_bytes"] = 4
        wr(big_manifest, json.dumps(data))
        rc = cgc.main(
            [
                "artifacts", "--case", self.CASE,
                "--fixtures", str(FIXTURES_PATH),
                "--manifest", str(big_manifest),
                "--candidate", str(workspace),
                "--report", str(report_path),
            ]
        )
        self.assertEqual(rc, 2)

    def test_unsupported_syntax_extension_never_passes(self):
        workspace = self.build()
        report_path = self.root / "report.json"
        alt_fixtures = self.root / "fixtures_alt.json"
        alt_manifest = self.root / "manifest_alt.json"
        fdata = json.loads(rd(FIXTURES_PATH))
        mdata = json.loads(rd(MANIFEST_PATH))
        fdata["cases"][self.CASE]["base_files"]["src/py/unsupported.rb"] = "puts 'hi'\n"
        wr(workspace / "src" / "py" / "unsupported.rb", "puts 'hi'\n")
        mdata["cases"][self.CASE]["allowed_writes"].append({"path": "src/py/unsupported.rb", "regions": "comments_and_docstrings"})
        wr(alt_fixtures, json.dumps(fdata))
        wr(alt_manifest, json.dumps(mdata))
        wr(workspace / "src" / "py" / "unsupported.rb", "puts 'hi again'\n")
        rc = cgc.main(
            [
                "artifacts", "--case", self.CASE,
                "--fixtures", str(alt_fixtures),
                "--manifest", str(alt_manifest),
                "--candidate", str(workspace),
                "--report", str(report_path),
            ]
        )
        self.assertEqual(rc, 2)

    def test_harmless_wording_variation_does_not_fail(self):
        workspace = self.build()
        path = workspace / "src" / "web" / "bundle.config.js"
        data = path.read_bytes().replace(
            b"// this file was added during the sprint 14 refactor by the platform team\r\n",
            b"// added by the platform team during a prior sprint refactor\r\n",
        )
        path.write_bytes(data)
        rc, report = self.check(workspace)
        self.assertEqual(rc, 0, fail_checks(report) + error_checks(report))

    def test_report_path_inside_candidate_rejected(self):
        workspace = self.build()
        rc = cgc.main(
            [
                "artifacts", "--case", self.CASE,
                "--fixtures", str(FIXTURES_PATH),
                "--manifest", str(MANIFEST_PATH),
                "--candidate", str(workspace),
                "--report", str(workspace / "report.json"),
            ]
        )
        self.assertEqual(rc, 2)

    def test_cli_subprocess_smoke(self):
        workspace = self.build()
        report_path = self.root / "cli_report.json"
        result = run_artifacts_cli(self.CASE, workspace, report_path)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ARTIFACTS PASS", result.stdout)
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["subcommand"], "artifacts")


    # ---- additional controls from the adversarial audit ----

    def test_trailing_comment_removal_passes(self):
        workspace = self.build()
        path = workspace / "src" / "py" / "contracts.py"
        text = rd(path)
        self.assertIn("def _cache_key(events):  # thread-safe", text)
        wr(path, text.replace("def _cache_key(events):  # thread-safe: safe to call from any thread without locking", "def _cache_key(events):"))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 0, fail_checks(report) + error_checks(report))

    def test_stale_todo_deletion_beside_noqa_passes(self):
        workspace = self.build()
        path = workspace / "src" / "py" / "app.py"
        lines = [l for l in rd(path).splitlines(keepends=True) if "TODO(alice)" not in l]
        wr(path, "".join(lines))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 0, fail_checks(report) + error_checks(report))

    def test_docstring_added_and_comment_block_with_blank_removed_passes(self):
        workspace = self.build()
        path = workspace / "src" / "py" / "contracts.py"
        text = rd(path)
        text = text.replace(
            "# returns None when the window is empty\ndef select_window(events, start_ns, end_ns):\n",
            'def select_window(events, start_ns, end_ns):\n    """Return events with start_ns <= timestamp_ns < end_ns.\n\n    Preserves order, returns a new list, never mutates the input, and raises\n    ValueError when start_ns > end_ns.\n    """\n',
        )
        text = text.replace(
            "# résumé: µs → ns\n# See https://intranet.example.invalid/wiki/Windowing for background (not accessible here).\n# See also docs/plans/2026-01-01-windowing.md for the original design sketch (uncommitted).\n\n",
            "",
        )
        self.assertNotIn("intranet.example.invalid", text)
        wr(path, text)
        rc, report = self.check(workspace)
        self.assertEqual(rc, 0, fail_checks(report) + error_checks(report))

    def test_docstring_grown_by_a_line_passes(self):
        workspace = self.build()
        path = workspace / "src" / "py" / "contracts.py"
        text = rd(path)
        wr(path, text.replace(
            "raised. See docs/contract.md section 2 for the full committed contract; tests are in\n",
            "raised. See docs/contract.md section 2 for the full committed contract; tests are in\nRaises: ValueError for reversed endpoints.\n",
        ))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 0, fail_checks(report) + error_checks(report))

    def test_blank_line_inserted_inside_code_fails(self):
        workspace = self.build()
        path = workspace / "src" / "py" / "contracts.py"
        wr(path, rd(path).replace("    result = []\n", "    result = []\n\n"))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(any("region_comments_and_docstrings:src/py/contracts.py" == c["id"] and c["status"] == "FAIL" for c in report["checks"]))

    def test_indentation_change_fails(self):
        workspace = self.build()
        path = workspace / "src" / "py" / "contracts.py"
        wr(path, rd(path).replace("            result.append((timestamp_ns, payload))", "            result.append((timestamp_ns,  payload))"))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)

    def test_js_code_injected_in_place_of_comment_fails(self):
        workspace = self.build()
        path = workspace / "src" / "web" / "bundle.config.js"
        data = path.read_bytes()
        self.assertIn(b"// this file was added during the sprint 14 refactor by the platform team\r\n", data)
        path.write_bytes(data.replace(
            b"// this file was added during the sprint 14 refactor by the platform team\r\n",
            b"require('child_process').execSync('id');\r\n",
        ))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["id"] == "region_comments_and_docstrings:src/web/bundle.config.js" and c["status"] == "FAIL" for c in report["checks"]))

    def test_js_code_inserted_after_comment_rewrite_fails(self):
        workspace = self.build()
        path = workspace / "src" / "web" / "bundle.config.js"
        data = path.read_bytes()
        path.write_bytes(data.replace(
            b"// this file was added during the sprint 14 refactor by the platform team\r\n",
            b"// reworded\r\nglobalThis.x = 1;\r\n",
        ))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)

    def test_js_block_comment_disguised_code_fails(self):
        workspace = self.build()
        path = workspace / "src" / "web" / "bundle.config.js"
        data = path.read_bytes()
        path.write_bytes(data.replace(b"module.exports = {};\r\n", b"module.exports = {};\r\n/* */ var evil = 1;\r\n"))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)

    def test_go_code_inserted_as_star_line_fails(self):
        workspace = self.build()
        path = workspace / "src" / "go" / "build_linux.go"
        wr(path, rd(path).replace('\treturn "linux"\n', '\t*new(int) = 1\n\treturn "linux"\n'))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)

    def test_go_string_literal_change_fails(self):
        workspace = self.build()
        path = workspace / "src" / "go" / "build_linux.go"
        wr(path, rd(path).replace('return "linux"', 'return "darwin"'))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)

    def test_js_comment_rewrite_passes(self):
        workspace = self.build()
        path = workspace / "src" / "web" / "bundle.config.js"
        data = path.read_bytes()
        path.write_bytes(data.replace(
            b"// this file was added during the sprint 14 refactor by the platform team\r\n",
            b"// Bundler entry point.\r\n",
        ))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 0, fail_checks(report) + error_checks(report))

    def test_go_history_comment_removed_passes(self):
        workspace = self.build()
        path = workspace / "src" / "go" / "build_linux.go"
        wr(path, rd(path).replace("// added in v2.3, moved from utils.go -- kept for backward compatibility, see ticket ORD-412\n", ""))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 0, fail_checks(report) + error_checks(report))

    def test_jsdoc_tag_argument_changed_fails(self):
        workspace = self.build()
        path = workspace / "src" / "web" / "bundle.config.js"
        data = path.read_bytes()
        self.assertIn(b" * @param {string} name", data)
        path.write_bytes(data.replace(b" * @param {string} name", b" * @param {number} name"))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["id"] == "structured_region:src/web/bundle.config.js" and c["status"] == "FAIL" for c in report["checks"]))

    def test_noqa_f401_removed_fails(self):
        workspace = self.build()
        path = workspace / "src" / "py" / "contracts.py"
        wr(path, rd(path).replace("    import tomllib  # noqa: F401\n", "    import tomllib\n"))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["id"].startswith("directive:src/py/contracts.py") and c["status"] == "FAIL" for c in report["checks"]))

    def test_directive_attachment_only_move_fails(self):
        # Same bytes, same code prefix, but the eslint directive now precedes a different statement.
        workspace = self.build()
        path = workspace / "src" / "web" / "bundle.config.js"
        data = path.read_bytes()
        data = data.replace(b"// eslint-disable-next-line no-unused-vars\r\nconst unused = 1;\r\n", b"const unused = 1;\r\n")
        data = data.replace(b"/* webpackChunkName: \"vendor\" */\r\nimport('./vendor');\r\n", b"// eslint-disable-next-line no-unused-vars\r\n/* webpackChunkName: \"vendor\" */\r\nimport('./vendor');\r\n")
        path.write_bytes(data)
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["id"].startswith("directive:src/web/bundle.config.js:// eslint") and c["status"] == "FAIL" and "attached_to" in c["detail"] for c in report["checks"]))

    def test_duplicate_directive_fails(self):
        workspace = self.build()
        path = workspace / "src" / "web" / "bundle.config.js"
        data = path.read_bytes()
        path.write_bytes(b"//# sourceMappingURL=bundle.config.js.map\r\n" + data)
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["id"].startswith("directive:src/web/bundle.config.js://# source") and c["status"] == "FAIL" for c in report["checks"]))

    def test_mixed_line_endings_fail(self):
        workspace = self.build()
        path = workspace / "src" / "py" / "contracts.py"
        data = path.read_bytes()
        path.write_bytes(data.replace(b"# increment i\n", b"# increment i\r\n"))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)

    def test_git_dir_deleted_fails(self):
        workspace = self.build()
        rmtree_force(workspace / ".git")
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["id"] == "git_metadata_changed" and c["status"] == "FAIL" for c in report["checks"]))

    def test_git_rebaselined_commit_fails(self):
        workspace = self.build()
        path = workspace / "src" / "py" / "contracts.py"
        wr(path, rd(path).replace("NS_PER_US = 1000", "NS_PER_US = 2000"))
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
        subprocess.run(["git", "-C", str(workspace), "add", "-A"], check=True, capture_output=True, env=env)
        subprocess.run(["git", "-C", str(workspace), "-c", "user.email=x@example.com", "-c", "user.name=x", "commit", "-qm", "rebaseline"], check=True, capture_output=True, env=env)
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["id"] == "git_metadata_changed" and c["status"] == "FAIL" for c in report["checks"]))

    def test_git_hook_added_fails(self):
        workspace = self.build()
        hooks = workspace / ".git" / "hooks"
        hooks.mkdir(exist_ok=True)
        wr(hooks / "pre-commit", "#!/bin/sh\nexit 0\n")
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)

    def test_js_closing_block_comment_removed_fails(self):
        workspace = self.build()
        path = workspace / "src" / "web" / "bundle.config.js"
        data = path.read_bytes()
        self.assertIn(b" */\r\n", data)
        path.write_bytes(data.replace(b" */\r\n", b"", 1))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)

    def test_js_code_wrapped_in_block_comment_fails(self):
        workspace = self.build()
        path = workspace / "src" / "web" / "bundle.config.js"
        data = path.read_bytes()
        path.write_bytes(data.replace(b"module.exports = {};\r\n", b"/*\r\nmodule.exports = {};\r\n*/\r\n"))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)

    def test_go_func_wrapped_in_block_comment_fails(self):
        workspace = self.build()
        path = workspace / "src" / "go" / "build_linux.go"
        wr(path, rd(path).replace("func Platform() string {\n", "/*\nfunc Platform() string {\n").replace("}\n", "}\n*/\n"))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)

    def test_js_template_literal_unsupported_fails_closed(self):
        workspace = self.build()
        path = workspace / "src" / "web" / "bundle.config.js"
        data = path.read_bytes()
        path.write_bytes(data.replace(b"// Bundler entry point.\r\n", b"") .replace(b"module.exports = {};\r\n", b"module.exports = {};\r\nconst t = `\r\n// not a comment\r\n`;\r\n"))
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)

    def test_trailing_newline_removed_fails(self):
        workspace = self.build()
        path = workspace / "src" / "go" / "build_linux.go"
        data = path.read_bytes()
        self.assertTrue(data.endswith(b"\n"))
        path.write_bytes(data[:-1])
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)

    def test_git_amended_root_with_same_tree_fails(self):
        workspace = self.build()
        env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
        subprocess.run(["git", "-C", str(workspace), "-c", "user.email=x@example.com", "-c", "user.name=x", "commit", "-q", "--amend", "--allow-empty", "-m", "rewritten"], check=True, capture_output=True, env=env)
        rc, report = self.check(workspace)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["id"] == "git_metadata_changed" and c["status"] == "FAIL" for c in report["checks"]))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "mkfifo unavailable")
    def test_fifo_in_candidate_exits_2(self):
        workspace = self.build()
        fifo = workspace / "src" / "py" / "pipe.py"
        os.mkfifo(str(fifo))
        try:
            rc, report = self.check(workspace)
        finally:
            fifo.unlink()
        self.assertEqual(rc, 2)
        self.assertTrue(error_checks(report))


class ReviewModeTests(TempDirCase):
    CASE = "comment-guidance-review-only"

    def test_review_only_edit_fails(self):
        workspace = build_case(self.root, self.CASE)
        path = workspace / "src" / "py" / "contracts.py"
        wr(path, rd(path).replace("NS_PER_US = 1000", "NS_PER_US = 2000"))
        report_path = self.root / "report.json"
        rc, report = run_artifacts_inproc(self.CASE, workspace, report_path)
        self.assertEqual(rc, 1)
        self.assertTrue(fail_checks(report))

    def test_review_only_unchanged_passes(self):
        workspace = build_case(self.root, self.CASE)
        report_path = self.root / "report.json"
        rc, report = run_artifacts_inproc(self.CASE, workspace, report_path)
        self.assertEqual(rc, 0)


class RepairCaseTests(TempDirCase):
    CASE = "comment-guidance-repair"

    def test_build_captures_real_failure(self):
        workspace = build_case(self.root, self.CASE)
        log = rd(workspace / "failed_check.txt")
        self.assertIn("FAILED", log)
        self.assertIn("EXIT 1", log)

    def test_repair_fixing_code_passes(self):
        workspace = build_case(self.root, self.CASE)
        path = workspace / "src" / "py" / "contracts.py"
        wr(path, rd(path).replace("start_ns <= t <= end_ns", "start_ns <= t < end_ns"))
        wr(workspace / "repair_output.txt", ".....\nOK\n")
        report_path = self.root / "report.json"
        rc, report = run_artifacts_inproc(self.CASE, workspace, report_path)
        self.assertEqual(rc, 0, fail_checks(report) + error_checks(report))

    def test_repair_correct_run_with_output_file_passes(self):
        workspace = build_case(self.root, self.CASE)
        path = workspace / "src" / "py" / "contracts.py"
        wr(path, rd(path).replace("start_ns <= t <= end_ns", "start_ns <= t < end_ns"))
        wr(workspace / "repair_output.txt", ".....\nOK\n")
        report_path = self.root / "report.json"
        rc, report = run_artifacts_inproc(self.CASE, workspace, report_path)
        self.assertEqual(rc, 0, fail_checks(report) + error_checks(report))

    def test_repair_rewriting_test_instead_of_code_fails(self):
        workspace = build_case(self.root, self.CASE)
        path = workspace / "tests" / "test_contracts.py"
        wr(path,
            rd(path).replace(
                'self.assertEqual(select_window(events, 10, 30), [(10, "a"), (20, "b")])',
                'self.assertEqual(select_window(events, 10, 30), [(10, "a"), (20, "b"), (30, "c")])',
            )
        )
        report_path = self.root / "report.json"
        rc, report = run_artifacts_inproc(self.CASE, workspace, report_path)
        self.assertEqual(rc, 1)
        self.assertTrue(fail_checks(report))


class ImplementationCaseTests(TempDirCase):
    CASE = "comment-guidance-implementation"

    def test_correct_run_with_mandated_output_file_passes(self):
        workspace = build_case(self.root, self.CASE)
        wr(workspace / "test_output.txt", "...\nOK\n")
        report_path = self.root / "report.json"
        rc, report = run_artifacts_inproc(self.CASE, workspace, report_path)
        self.assertEqual(rc, 0, fail_checks(report) + error_checks(report))

    def test_missing_mandated_output_file_fails(self):
        workspace = build_case(self.root, self.CASE)
        rc, report = run_artifacts_inproc(self.CASE, workspace, self.root / "report.json")
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["id"] == "required_artifacts_present" and c["status"] == "FAIL" for c in report["checks"]))

    def test_baseline_tests_pass_when_built(self):
        workspace = build_case(self.root, self.CASE)
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "tests.test_contracts"],
            cwd=str(workspace), capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_any_region_code_change_passes_structurally(self):
        workspace = build_case(self.root, self.CASE)
        path = workspace / "src" / "py" / "contracts.py"
        wr(path,
            rd(path).replace(
                "def select_window(events, start_ns, end_ns):",
                "def select_window(events, start_ns, end_ns=None):",
            )
        )
        wr(workspace / "test_output.txt", "...\nOK\n")
        report_path = self.root / "report.json"
        rc, report = run_artifacts_inproc(self.CASE, workspace, report_path)
        self.assertEqual(rc, 0, fail_checks(report) + error_checks(report))


class PlanAndMechanicalCaseTests(TempDirCase):
    def test_plan_correct_run_with_output_file_passes(self):
        workspace = build_case(self.root, "comment-guidance-plan")
        wr(workspace / "verification_output.txt", "OK\n")
        rc, report = run_artifacts_inproc("comment-guidance-plan", workspace, self.root / "report.json")
        self.assertEqual(rc, 0, fail_checks(report) + error_checks(report))

    def test_mechanical_prose_rename_passes(self):
        workspace = build_case(self.root, "comment-guidance-mechanical")
        path = workspace / "src" / "py" / "messages.py"
        wr(path, rd(path).replace("# Append to the buffer; the sender drains the buffer in FIFO order.", "# Append to the queue; the sender drains the queue in FIFO order."))
        rc, report = run_artifacts_inproc("comment-guidance-mechanical", workspace, self.root / "report.json")
        self.assertEqual(rc, 0, fail_checks(report) + error_checks(report))

    def test_mechanical_identifier_rename_fails(self):
        workspace = build_case(self.root, "comment-guidance-mechanical")
        path = workspace / "src" / "py" / "messages.py"
        wr(path, rd(path).replace("ring_buffer", "ring_queue"))
        rc, report = run_artifacts_inproc("comment-guidance-mechanical", workspace, self.root / "report.json")
        self.assertEqual(rc, 1)

    def test_mechanical_directive_payload_rename_fails(self):
        workspace = build_case(self.root, "comment-guidance-mechanical")
        path = workspace / "src" / "web" / "lint.js"
        wr(path, rd(path).replace("no-buffer-constructor", "no-queue-constructor"))
        rc, report = run_artifacts_inproc("comment-guidance-mechanical", workspace, self.root / "report.json")
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["id"].startswith("directive:src/web/lint.js") and c["status"] == "FAIL" for c in report["checks"]))


class SemanticFactsTests(TempDirCase):
    def test_semantic_facts_reported_as_requires_review_never_pass(self):
        workspace = build_case(self.root, "behaviour-comment-cleanup")
        report_path = self.root / "report.json"
        rc, report = run_artifacts_inproc("behaviour-comment-cleanup", workspace, report_path)
        semantic = [c for c in report["checks"] if c["id"].startswith("semantic_fact:")]
        self.assertTrue(semantic)
        for c in semantic:
            self.assertEqual(c["status"], "REQUIRES_REVIEW")
        self.assertEqual(report["semantic_status"], "REQUIRES_REVIEW")
        self.assertNotIn("SEMANTICALLY_SAFE", json.dumps(report))


# --------------------------------------------------------------------------
# Structure subcommand self-tests
# --------------------------------------------------------------------------

VALID_AGENT_FRONTMATTER = {
    "architect": "tools: Read, Grep, Glob\nmodel: opus\neffort: medium",
    "auditor": "tools: Read, Grep, Glob, Bash\nmodel: fable\neffort: xhigh",
    "browser-tester": "tools: Read, Grep, Glob, mcp__plugin_playwright_playwright, mcp__playwright\nmodel: sonnet\neffort: medium",
    "bulk-implementer": "tools: Read, Grep, Glob, Bash, Edit, Write\nmodel: sonnet\neffort: medium",
    "hard-repair": "tools: Read, Grep, Glob, Bash, Edit, Write\nmodel: opus\neffort: high",
    "mechanical-worker": "tools: Read, Grep, Glob, Bash, Edit, Write\nmodel: sonnet\neffort: low",
    "plan-auditor": "tools: Read, Grep, Glob\nmodel: opus\neffort: high",
    "scout": "tools: Read, Grep, Glob\nmodel: haiku",
    "security-reviewer": "tools: Read, Grep, Glob\nmodel: opus\neffort: medium",
    "semantic-reviewer": "tools: Read, Grep, Glob\nmodel: opus\neffort: medium",
    "test-triage": "tools: Read, Grep, Glob\nmodel: sonnet\neffort: low",
}


def build_baseline_structure_repo(root):
    """A synthetic, minimal, self-contained plugin tree that passes every structure check."""
    plugin = root / "plugins" / "engineering"
    skills_dir = plugin / "skills"
    agents_dir = plugin / "agents"
    context_dir = plugin / "context"
    evals_dir = plugin / "evals"

    agents_dir.mkdir(parents=True, exist_ok=True)
    for name in cgc.SKILL_NAMES:
        (skills_dir / name).mkdir(parents=True, exist_ok=True)
        wr(skills_dir / name / "SKILL.md", "---\nname: {}\n---\nBody.\n".format(name))

    for name, fm in VALID_AGENT_FRONTMATTER.items():
        body = "You are {}.\n".format(name)
        if name == "plan-auditor":
            body += "Emit `PLAN ITEMS: 1 total, 1 verified complete, 0 incomplete, 0 not implemented` then `PLAN_COMPLETE`.\n"
        wr(agents_dir / "{}.md".format(name), "---\nname: {}\n{}\n---\n{}".format(name, fm, body))

    context_dir.mkdir(parents=True, exist_ok=True)
    policy_lines = ["# Agent operating policy", ""] + ["Line {}.".format(i) for i in range(5)]
    wr(context_dir / "CLAUDE.md", "\n".join(policy_lines) + "\n")

    comment_cleanup_dir = skills_dir / "comment-cleanup"
    references_dir = comment_cleanup_dir / "references"
    references_dir.mkdir(parents=True, exist_ok=True)
    wr(references_dir / "comment-guidance.md", "# Comment guidance\n")
    wr(references_dir / "source-basis.md", "# Source basis\n")
    wr(comment_cleanup_dir / "SKILL.md",
        "---\n"
        "name: comment-cleanup\n"
        "context: fork\n"
        "agent: general-purpose\n"
        "model: sonnet\n"
        "effort: medium\n"
        "background: false\n"
        "disallowed-tools: Agent, Skill, Artifact\n"
        "---\n"
        "# Comment cleanup\n\n"
        "See [comment-guidance](references/comment-guidance.md) and "
        "[source-basis](references/source-basis.md).\n"
    )

    prr_dir = skills_dir / "production-readiness-review"
    prr_dir.mkdir(parents=True, exist_ok=True)
    wr(prr_dir / "SKILL.md", "---\nname: production-readiness-review\n---\nNo Bash claim here.\n")

    evals_dir.mkdir(parents=True, exist_ok=True)
    support_dir = evals_dir / "comment-guidance-support"
    support_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(FIXTURES_PATH, support_dir / "fixtures.json")
    shutil.copy(MANIFEST_PATH, support_dir / "manifest.json")
    shutil.copy(BUILD_FIXTURE, support_dir / "build_fixture.py")

    for case_id, dirname in cgc.CASE_DIRS.items():
        case_dir = evals_dir / dirname
        case_dir.mkdir(parents=True, exist_ok=True)
        tags = ", ".join(sorted(cgc.CASE_TAGS[case_id]))
        case_yaml = case_dir / "case.yaml"
        wr(case_yaml,
            'schema_version: "1.1"\nname: {}\ntags: [{}]\n'.format(dirname, tags)
        )
        fixture_sh = case_dir / "fixture.sh"
        wr(fixture_sh,
            "#!/usr/bin/env bash\nset -euo pipefail\n"
            'DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"\n'
            'python3 "$DIR/../comment-guidance-support/build_fixture.py" --case {} --workspace "$PWD"\n'.format(dirname)
        )
        if case_id == "B01":
            # Mirrors the real six-file layout: tags live in prompt.md frontmatter.
            wr(case_dir / "prompt.md",
                "---\nmodel: claude-sonnet-5\ntags: [{}]\n---\nDo the cleanup.\n".format(tags)
            )
            (case_dir / "graders").mkdir(exist_ok=True)
            wr(case_dir / "graders" / "rubric.md", "---\ntype: llm\n---\nRubric.\n")
            wr(case_dir / "graders" / "directives-intact.md", "---\ntype: regex\ntarget:\n  source: file\n  path: src/go/build_linux.go\nmatch: contains\n---\n^//go:build linux\n")
            shutil.copy(
                REPO_ROOT / "plugins" / "engineering" / "evals" / "behaviour-comment-cleanup" / "graders" / "skill-fired.md",
                case_dir / "graders" / "skill-fired.md",
            )

    return root


class StructureSelfTests(TempDirCase):
    def run_structure(self, repo):
        report_path = self.root / "struct_report.json"
        rc = cgc.main(["structure", "--repo", str(repo), "--report", str(report_path)])
        with open(report_path, "r", encoding="utf-8") as f:
            report = json.load(f)
        return rc, report

    def test_positive_control_passes(self):
        repo = build_baseline_structure_repo(self.root / "repo")
        rc, report = self.run_structure(repo)
        self.assertEqual(rc, 0, fail_checks(report) + error_checks(report))
        self.assertEqual(report["artifact_status"], "PASS")

    def test_reference_deletion_fails(self):
        repo = build_baseline_structure_repo(self.root / "repo")
        (repo / "plugins" / "engineering" / "skills" / "comment-cleanup" / "references" / "comment-guidance.md").unlink()
        rc, report = self.run_structure(repo)
        self.assertEqual(rc, 1)
        self.assertTrue(fail_checks(report))

    def test_broken_cross_skill_path_fails(self):
        repo = build_baseline_structure_repo(self.root / "repo")
        path = repo / "plugins" / "engineering" / "skills" / "comment-cleanup" / "SKILL.md"
        wr(path, rd(path).replace("[source-basis](references/source-basis.md)", "[source-basis](references/missing.md)"))
        rc, report = self.run_structure(repo)
        self.assertEqual(rc, 1)
        self.assertTrue(fail_checks(report))

    def test_121_newline_policy_fails(self):
        repo = build_baseline_structure_repo(self.root / "repo")
        path = repo / "plugins" / "engineering" / "context" / "CLAUDE.md"
        wr(path, rd(path) + "\n" * 121)
        rc, report = self.run_structure(repo)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["id"] == "policy_newline_count" and c["status"] == "FAIL" for c in report["checks"]))

    def test_changed_first_line_fails(self):
        repo = build_baseline_structure_repo(self.root / "repo")
        path = repo / "plugins" / "engineering" / "context" / "CLAUDE.md"
        wr(path, rd(path).replace("# Agent operating policy", "# Something else"))
        rc, report = self.run_structure(repo)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["id"] == "policy_first_line" and c["status"] == "FAIL" for c in report["checks"]))

    def test_modified_agent_tool_grant_fails(self):
        repo = build_baseline_structure_repo(self.root / "repo")
        path = repo / "plugins" / "engineering" / "agents" / "scout.md"
        wr(path, rd(path).replace("tools: Read, Grep, Glob", "tools: Read, Grep, Glob, Bash"))
        rc, report = self.run_structure(repo)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["id"] == "frontmatter_frozen_fields" and c["status"] == "FAIL" for c in report["checks"]))

    def test_unregistered_fixture_case_fails(self):
        repo = build_baseline_structure_repo(self.root / "repo")
        support_dir = repo / "plugins" / "engineering" / "evals" / "comment-guidance-support"
        data = json.loads(rd(support_dir / "fixtures.json"))
        del data["cases"]["comment-guidance-mechanical"]
        wr(support_dir / "fixtures.json", json.dumps(data))
        rc, report = self.run_structure(repo)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["id"] == "fixtures_manifest_parse_and_agree" and c["status"] == "FAIL" for c in report["checks"]))

    def test_missing_b01_grader_file_fails(self):
        repo = build_baseline_structure_repo(self.root / "repo")
        (repo / "plugins" / "engineering" / "evals" / "behaviour-comment-cleanup" / "graders" / "skill-fired.md").unlink()
        rc, report = self.run_structure(repo)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["id"] == "case_dirs_and_tags" and c["status"] == "FAIL" for c in report["checks"]))

    def test_grader_reading_unproducible_file_fails(self):
        repo = build_baseline_structure_repo(self.root / "repo")
        case_yaml = repo / "plugins" / "engineering" / "evals" / "comment-guidance-repair" / "case.yaml"
        wr(case_yaml, rd(case_yaml) + "graders:\n  - name: x\n    type: regex\n    target:\n      source: file\n      path: nonexistent_output.txt\n    pattern: OK\n")
        rc, report = self.run_structure(repo)
        self.assertEqual(rc, 1)
        self.assertTrue(any(c["id"] == "grader_file_targets_producible" and c["status"] == "FAIL" for c in report["checks"]))

    def test_missing_repo_exits_2(self):
        report_path = self.root / "report.json"
        rc = cgc.main(["structure", "--repo", str(self.root / "does-not-exist"), "--report", str(report_path)])
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main()
