from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from scripts import eval_recheck as er  # noqa: E402


def llm_def(name, criteria, focus="last_message"):
    return {"name": name, "type": "llm", "weight": 1, "graderMarkdown": json.dumps(criteria),
            "config": {"criteria": criteria, "focus": focus}}


AGGREGATE = {
    "cases": [
        {
            "name": "behaviour-prr-6",
            "graders": [
                {"name": "verdict", "type": "regex", "weight": 1, "config": {"pattern": "x"}},
                llm_def("rubric", "- Names the shared database."),
                llm_def("rubric-5", "- Rates architecture claims at E1/E2."),
            ],
            "arms": {"with": [
                {"graders": [
                    {"name": "verdict", "passed": False, "explanation": "pattern not found"},
                    {"name": "rubric", "passed": True, "judgeVotes": [True, True, True], "evidence": "r"},
                    {"name": "rubric-5", "passed": False, "judgeVotes": [False, False, True],
                     "evidence": json.dumps("Report: résumé µs → ns, E2 only")},
                ]},
            ]},
        },
        {
            "name": "comment-guidance-repair",
            "graders": [llm_def("rubric", "- Docstring says end is exclusive.",
                                {"source": "file", "path": "src/py/contracts.py"})],
            "arms": {"with": [
                {"graders": [{"name": "rubric", "passed": False, "judgeVotes": [False, False, False],
                              "evidence": '"""Contract: end_ns exclusive."""'}]},
            ]},
        },
    ]
}


class DecodeEvidenceTests(unittest.TestCase):
    def test_json_encoded_string_is_decoded(self):
        self.assertEqual(er.decode_evidence(json.dumps("µs → ns")), "µs → ns")

    def test_raw_text_starting_with_quotes_is_kept(self):
        raw = '"""Contract: end_ns exclusive."""'
        self.assertEqual(er.decode_evidence(raw), raw)

    def test_non_string_evidence_becomes_empty(self):
        self.assertEqual(er.decode_evidence(None), "")


class SelectionTests(unittest.TestCase):
    def test_only_failed_llm_graders_are_selected(self):
        records = list(er.failed_llm_graders(AGGREGATE))
        self.assertEqual([(r["case"], r["grader"]) for r in records],
                         [("behaviour-prr-6", "rubric-5"), ("comment-guidance-repair", "rubric")])

    def test_record_carries_criteria_focus_votes_and_decoded_evidence(self):
        first, second = list(er.failed_llm_graders(AGGREGATE))
        self.assertEqual(first["criteria"], "- Rates architecture claims at E1/E2.")
        self.assertEqual(first["votes"], [False, False, True])
        self.assertEqual(first["evidence"], "Report: résumé µs → ns, E2 only")
        self.assertEqual(second["focus"], "file src/py/contracts.py")

    def test_case_glob_filters(self):
        records = list(er.failed_llm_graders(AGGREGATE, "comment-guidance-*"))
        self.assertEqual([r["case"] for r in records], ["comment-guidance-repair"])

    def test_include_passes_selects_passing_llm_graders_too(self):
        records = list(er.llm_grader_records(AGGREGATE, include_passes=True))
        self.assertEqual([(r["case"], r["grader"], r["harness"]) for r in records],
                         [("behaviour-prr-6", "rubric", "PASS"), ("behaviour-prr-6", "rubric-5", "FAIL"),
                          ("comment-guidance-repair", "rubric", "FAIL")])

    def test_grader_glob_filters(self):
        records = list(er.llm_grader_records(AGGREGATE, grader_glob="rubric-5", include_passes=True))
        self.assertEqual([r["grader"] for r in records], ["rubric-5"])


class ParseOverallTests(unittest.TestCase):
    def test_last_overall_line_wins(self):
        self.assertEqual(er.parse_overall("1. FAIL - x\nOVERALL: FAIL\nCorrection\nOVERALL: PASS"), "PASS")

    def test_missing_overall_is_unparsed(self):
        self.assertEqual(er.parse_overall("1. PASS - fine"), "UNPARSED")


class MainTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "aggregate-result.json"
        self.path.write_text(json.dumps(AGGREGATE), encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, args):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = er.main(args)
        return code, out.getvalue(), err.getvalue()

    def test_dry_run_lists_without_calling_the_judge(self):
        with mock.patch.object(er.subprocess, "run") as run:
            code, out, _ = self.run_main([str(self.path), "--dry-run"])
        run.assert_not_called()
        self.assertEqual(code, 0)
        self.assertIn("2 failed llm grader(s)", out)
        self.assertIn("behaviour-prr-6 run 0 rubric-5: harness FAIL FAIL PASS", out)

    def test_disagreement_is_flagged_and_prompt_goes_on_stdin(self):
        replies = [subprocess.CompletedProcess([], 0, "1. PASS - E2 only\nOVERALL: PASS\n", ""),
                   subprocess.CompletedProcess([], 0, "1. FAIL - says inclusive\nOVERALL: FAIL\n", "")]
        with mock.patch.object(er.subprocess, "run", side_effect=replies) as run:
            code, out, _ = self.run_main([str(self.path), "--claude", "claude"])
        self.assertEqual(code, 0)
        self.assertIn("behaviour-prr-6 run 0 rubric-5: harness FAIL FAIL PASS; recheck PASS -> NEEDS REVIEW", out)
        self.assertIn("comment-guidance-repair run 0 rubric: harness FAIL FAIL FAIL; recheck FAIL\n", out)
        self.assertIn("1 of 2 need review", out)
        first_call = run.call_args_list[0]
        self.assertIn("Report: résumé µs → ns, E2 only", first_call.kwargs["input"])
        self.assertEqual(first_call.kwargs["encoding"], "utf-8")
        self.assertNotIn(first_call.kwargs["input"], first_call.args[0])

    def test_unparsed_reply_needs_review(self):
        reply = subprocess.CompletedProcess([], 0, "no verdict here", "")
        with mock.patch.object(er.subprocess, "run", return_value=reply):
            _, out, _ = self.run_main([str(self.path), "--case", "comment-guidance-*"])
        self.assertIn("recheck UNPARSED -> NEEDS REVIEW", out)

    def test_judge_runs_outside_the_repository(self):
        reply = subprocess.CompletedProcess([], 0, "OVERALL: FAIL", "")
        with mock.patch.object(er.subprocess, "run", return_value=reply) as run:
            self.run_main([str(self.path), "--case", "comment-guidance-*"])
        cwd = run.call_args.kwargs["cwd"]
        self.assertEqual(os.path.dirname(cwd), er.tempfile.gettempdir())
        self.assertTrue(os.path.basename(cwd).startswith("eval_recheck-"))

    def test_relative_claude_path_is_made_absolute(self):
        reply = subprocess.CompletedProcess([], 0, "OVERALL: FAIL", "")
        with mock.patch.object(er.shutil, "which", return_value=os.path.join("bin", "claude")), \
                mock.patch.object(er.subprocess, "run", return_value=reply) as run:
            self.run_main([str(self.path), "--case", "comment-guidance-*", "--claude", "bin/claude"])
        self.assertEqual(run.call_args.args[0][0], os.path.abspath(os.path.join("bin", "claude")))

    def test_silent_judge_reports_exit_status_and_stderr(self):
        reply = subprocess.CompletedProcess([], 1, "", "not logged in\n")
        with mock.patch.object(er.subprocess, "run", return_value=reply):
            code, out, _ = self.run_main([str(self.path), "--case", "comment-guidance-*"])
        self.assertEqual(code, 0)
        self.assertIn("recheck UNPARSED -> NEEDS REVIEW", out)
        self.assertIn("judge printed nothing; exit 1: not logged in", out)

    def test_failed_judge_call_needs_review_and_the_run_continues(self):
        effects = [subprocess.TimeoutExpired(["claude"], 600), FileNotFoundError("claude")]
        with mock.patch.object(er.subprocess, "run", side_effect=effects):
            code, out, _ = self.run_main([str(self.path), "--claude", "claude"])
        self.assertEqual(code, 0)
        self.assertIn("behaviour-prr-6 run 0 rubric-5: harness FAIL FAIL PASS; recheck ERROR -> NEEDS REVIEW", out)
        self.assertIn("comment-guidance-repair run 0 rubric: harness FAIL FAIL FAIL; recheck ERROR -> NEEDS REVIEW", out)
        self.assertIn("2 of 2 need review", out)

    def test_dry_run_with_passes_lists_them(self):
        with mock.patch.object(er.subprocess, "run") as run:
            code, out, _ = self.run_main([str(self.path), "--dry-run", "--include-passes"])
        run.assert_not_called()
        self.assertEqual(code, 0)
        self.assertIn("3 llm grader(s) selected, passes included", out)
        self.assertIn("behaviour-prr-6 run 0 rubric: harness PASS PASS PASS", out)

    def test_recheck_failing_a_harness_pass_needs_review(self):
        reply = subprocess.CompletedProcess([], 0, "1. FAIL - not named\nOVERALL: FAIL\n", "")
        with mock.patch.object(er.subprocess, "run", return_value=reply) as run:
            code, out, _ = self.run_main([str(self.path), "--include-passes", "--grader", "rubric",
                                          "--case", "behaviour-prr-6", "--claude", "claude"])
        self.assertEqual(code, 0)
        self.assertIn("behaviour-prr-6 run 0 rubric: harness PASS PASS PASS; recheck FAIL -> NEEDS REVIEW", out)
        self.assertIn("1 of 1 need review", out)
        self.assertIn("re-checking an eval judge's PASS verdict", run.call_args.kwargs["input"])

    def test_grader_glob_matching_nothing_selects_zero(self):
        with mock.patch.object(er.subprocess, "run") as run:
            code, out, _ = self.run_main([str(self.path), "--grader", "nope", "--include-passes"])
        run.assert_not_called()
        self.assertEqual(code, 0)
        self.assertIn("0 llm grader(s) selected, passes included", out)

    def test_unreadable_aggregate_exits_2(self):
        bad = Path(self.tmp.name) / "bad.json"
        bad.write_text("{not json", encoding="utf-8")
        code, _, err = self.run_main([str(bad)])
        self.assertEqual(code, 2)
        self.assertIn("cannot read", err)


if __name__ == "__main__":
    unittest.main()
