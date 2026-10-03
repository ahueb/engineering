#!/usr/bin/env python3
"""Re-check `llm` grader verdicts from a `claude plugin eval` aggregate-result.json.

The eval judge answers PASS or FAIL in one word and records no reasons. For every failed `llm`
grader in the with-plugin arm (and, with --include-passes, every passing one), this script sends the
grader's criterion and the evidence the harness recorded to a judge that must give a reason per
criterion, and prints the verdicts so a person can review the disagreements. It never changes a
recorded score.

Usage: python3 scripts/eval_recheck.py AGGREGATE_JSON [--case GLOB] [--grader GLOB]
       [--include-passes] [--model MODEL] [--claude EXECUTABLE] [--dry-run]
Exit status: 0 after printing the report, 2 when the input cannot be read.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

DEFAULT_MODEL = "claude-sonnet-5-5"

PROMPT = """You are re-checking an eval judge's verdict. Apply the criterion below to the agent \
output. For each bullet in the criterion write one line `<n>. PASS|FAIL - <reason quoting the \
output>`; if the criterion has no bullets, write one such line. Finish with exactly one line \
`OVERALL: PASS` or `OVERALL: FAIL`. Be strict and literal; do not add requirements.

CRITERION:
{criteria}

AGENT OUTPUT ({focus}):
<<<
{evidence}
>>>"""

OVERALL_RE = re.compile(r"^OVERALL:\s*(PASS|FAIL)\s*$", re.MULTILINE)


def decode_evidence(raw):
    """Return evidence text; the harness stores some evidence as a JSON-encoded string."""
    if not isinstance(raw, str):
        return ""
    try:
        value = json.loads(raw)
    except ValueError:
        return raw
    return value if isinstance(value, str) else raw


def describe_focus(focus):
    if isinstance(focus, dict):
        return "file " + str(focus.get("path", ""))
    return focus or "last_message"


def llm_grader_records(aggregate, case_glob="*", grader_glob="*", include_passes=False):
    """Yield one record per `llm` grader result in the with-plugin arm of matching cases: the
    failures, plus the passes when include_passes is set."""
    for case in aggregate.get("cases", []):
        name = case.get("name", "")
        if not fnmatch.fnmatchcase(name, case_glob):
            continue
        definitions = {g.get("name"): g for g in case.get("graders", []) if g.get("type") == "llm"}
        for run_index, run in enumerate(case.get("arms", {}).get("with", [])):
            for grader in run.get("graders", []):
                definition = definitions.get(grader.get("name"))
                if definition is None or not fnmatch.fnmatchcase(grader.get("name") or "", grader_glob):
                    continue
                passed = bool(grader.get("passed"))
                if passed and not include_passes:
                    continue
                config = definition.get("config") or {}
                yield {
                    "case": name,
                    "run": run_index,
                    "grader": grader.get("name"),
                    "votes": grader.get("judgeVotes") or [],
                    "criteria": config.get("criteria") or definition.get("graderMarkdown") or "",
                    "focus": describe_focus(config.get("focus")),
                    "evidence": decode_evidence(grader.get("evidence", "")),
                    "harness": "PASS" if passed else "FAIL",
                }


def failed_llm_graders(aggregate, case_glob="*"):
    """Yield one record per failed `llm` grader (see llm_grader_records)."""
    return llm_grader_records(aggregate, case_glob)


def parse_overall(text):
    """Return PASS, FAIL, or UNPARSED from the judge's reply."""
    found = OVERALL_RE.findall(text or "")
    return found[-1] if found else "UNPARSED"


def run_judge(prompt, model, claude):
    """Send the prompt on stdin to `claude -p` with no tools; return its stdout.

    Runs in a new private temporary directory, so no repository's project settings reach the
    judge. When the call prints nothing, returns its exit status and stderr instead.
    """
    with tempfile.TemporaryDirectory(prefix="eval_recheck-") as cwd:
        proc = subprocess.run(
            [claude, "-p", "--model", model, "--tools", "", "--setting-sources", "project",
             "--strict-mcp-config", "--no-session-persistence"],
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=600,
            check=False,
            cwd=cwd,
        )
    if proc.stdout.strip():
        return proc.stdout
    return "judge printed nothing; exit {}: {}".format(proc.returncode, (proc.stderr or "").strip())


def votes_text(votes):
    return " ".join("PASS" if v else "FAIL" for v in votes) or "none recorded"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("aggregate")
    parser.add_argument("--case", default="*", help="case-name glob (default: all cases)")
    parser.add_argument("--grader", default="*", help="grader-name glob (default: all llm graders)")
    parser.add_argument("--include-passes", action="store_true",
                        help="also recheck the graders the harness passed, to find false passes")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--claude", default="claude", help="claude executable")
    parser.add_argument("--dry-run", action="store_true", help="list the selected llm graders only")
    args = parser.parse_args(argv)
    reconfigure = getattr(sys.stdout, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="backslashreplace")  # a cp1252 console must not abort the run mid-way
    try:
        with open(args.aggregate, encoding="utf-8") as f:
            aggregate = json.load(f)
    except (OSError, ValueError) as exc:
        print("eval_recheck: cannot read {}: {}".format(args.aggregate, exc), file=sys.stderr)
        return 2
    records = list(llm_grader_records(aggregate, args.case, args.grader, args.include_passes))
    if args.include_passes:
        print("{} llm grader(s) selected, passes included, in {}".format(len(records), args.aggregate))
    else:
        print("{} failed llm grader(s) in {}".format(len(records), args.aggregate))
    if args.dry_run or not records:
        for r in records:
            print("- {case} run {run} {grader}: harness {votes}".format(**dict(r, votes=votes_text(r["votes"]))))
        return 0
    claude = shutil.which(args.claude) or args.claude
    if os.path.dirname(claude):
        claude = os.path.abspath(claude)  # the judge runs in another directory
    disagreements = 0
    for r in records:
        try:
            reply = run_judge(PROMPT.format(**r), args.model, claude)
            verdict = parse_overall(reply)
        except (subprocess.TimeoutExpired, OSError) as exc:
            reply, verdict = "judge call failed: {}".format(exc), "ERROR"
        flag = " -> NEEDS REVIEW" if verdict != r["harness"] else ""
        disagreements += bool(flag)
        print("\n## {case} run {run} {grader}: harness {votes}; recheck {verdict}{flag}".format(
            **dict(r, votes=votes_text(r["votes"]), verdict=verdict, flag=flag)))
        print(reply.strip())
    print("\n{} of {} need review".format(disagreements, len(records)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
