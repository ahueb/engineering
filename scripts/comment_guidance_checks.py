"""Deterministic structure and artifact checks for the comment-guidance work.

Two subcommands:

    structure  --repo REPO [--report REPORT_JSON]
    artifacts  --case CASE_ID --fixtures FIXTURES_JSON --manifest MANIFEST_JSON
               --candidate RETAINED_WORKSPACE --report REPORT_JSON

Python >= 3.9, standard library only. See scripts/tests/test_comment_guidance_checks.py
for the behaviour this module is required to have.
"""

from __future__ import annotations

import argparse
import ast
import difflib
import fnmatch
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tokenize

SCHEMA = 1

SKILL_NAMES = {
    "browser-testing",
    "change-eval",
    "change-review",
    "checkpoint",
    "comment-cleanup",
    "deep-audit",
    "docs-check",
    "implementation-loop",
    "literature-review",
    "plan-execution",
    "production-readiness-review",
    "verification-loop",
}

AGENT_NAMES = {
    "architect",
    "auditor",
    "browser-tester",
    "bulk-implementer",
    "hard-repair",
    "mechanical-worker",
    "plan-auditor",
    "scout",
    "security-reviewer",
    "semantic-reviewer",
    "test-triage",
}

# Frozen frontmatter fields, copied verbatim from the baseline blobs at HEAD e158b1e6.
AGENT_FROZEN_FIELDS = {
    "architect": {"tools": "Read, Grep, Glob", "model": "opus", "effort": "medium"},
    "auditor": {"tools": "Read, Grep, Glob, Bash", "model": "fable", "effort": "xhigh"},
    "browser-tester": {
        "tools": "Read, Grep, Glob, mcp__plugin_playwright_playwright, mcp__playwright",
        "model": "sonnet",
        "effort": "medium",
    },
    "bulk-implementer": {"tools": "Read, Grep, Glob, Bash, Edit, Write", "model": "sonnet", "effort": "medium"},
    "hard-repair": {"tools": "Read, Grep, Glob, Bash, Edit, Write", "model": "opus", "effort": "high"},
    "mechanical-worker": {"tools": "Read, Grep, Glob, Bash, Edit, Write", "model": "sonnet", "effort": "low"},
    "plan-auditor": {"tools": "Read, Grep, Glob", "model": "opus", "effort": "high"},
    "scout": {"tools": "Read, Grep, Glob", "model": "haiku", "effort": None},
    "security-reviewer": {"tools": "Read, Grep, Glob", "model": "opus", "effort": "medium"},
    "semantic-reviewer": {"tools": "Read, Grep, Glob", "model": "opus", "effort": "medium"},
    "test-triage": {"tools": "Read, Grep, Glob", "model": "sonnet", "effort": "low"},
}

COMMENT_CLEANUP_FROZEN_FIELDS = {
    "name": "comment-cleanup",
    "context": "fork",
    "agent": "general-purpose",
    "model": "sonnet",
    "effort": "medium",
    "background": "false",
    "disallowed-tools": "Agent, Skill, Artifact",
}

CASE_DIRS = {
    "B01": "behaviour-comment-cleanup",
    "B02": "comment-guidance-review-only",
    "B03": "comment-guidance-implementation",
    "B04": "comment-guidance-plan",
    "B05": "comment-guidance-change-review",
    "B06": "comment-guidance-mechanical",
    "B07": "comment-guidance-repair",
    "B08": "comment-guidance-doc-plan",
}

CASE_TAGS = {
    "B01": {"behaviour", "behaviour-cleanup", "comment-guidance-write"},
    "B02": {"comment-guidance-read"},
    "B03": {"comment-guidance-write"},
    "B04": {"comment-guidance-write"},
    "B05": {"comment-guidance-read"},
    "B06": {"comment-guidance-write"},
    "B07": {"comment-guidance-write"},
    "B08": {"comment-guidance-read"},
}

SKILL_FIRED_BASELINE_SHA256 = "b10f153b0eaf22f01db29888e0948dc7d0bd0fa504f1a3d21a925c541e763ef2"

CASE_MODES = {
    "B01": "cleanup",
    "B02": "review",
    "B03": "implementation",
    "B04": "plan",
    "B05": "change_review",
    "B06": "mechanical",
    "B07": "repair",
    "B08": "doc_plan",
}

REVIEW_MODES = {"review", "change_review", "doc_plan"}

LEGACY_PHRASES = [
    "one concise sentence",
    "in one concise sentence",
    "Never move a comment's content",
    "that comment was a directive",
    "run past two sentences",
]

CANONICAL_REFERENCE_FORMS = [
    "[comment-guidance](references/comment-guidance.md)",
    "${CLAUDE_PLUGIN_ROOT}/skills/comment-cleanup/references/comment-guidance.md",
]


class HardError(Exception):
    """Raised for exit-2 conditions: invalid input, traversal, oversize, unsupported syntax."""

    def __init__(self, check_id, detail):
        super().__init__(detail)
        self.check_id = check_id
        self.detail = detail


# --------------------------------------------------------------------------
# Generic helpers
# --------------------------------------------------------------------------


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_file(path):
    with open(path, "rb") as f:
        return sha256_bytes(f.read())


def sha256_file_or_none(path):
    if path is None:
        return None
    try:
        return sha256_file(path)
    except OSError:
        return None


def load_json_file(path, check_id):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as exc:
        raise HardError(check_id, "could not parse {}: {}".format(path, exc))


def check(check_id, ok, detail, requires_review=False):
    if requires_review:
        status = "REQUIRES_REVIEW"
    else:
        status = "PASS" if ok else "FAIL"
    return {"id": check_id, "status": status, "detail": detail}


def build_report(subcommand, case, checks, hashes, diagnostics=None):
    statuses = [c["status"] for c in checks]
    if any(s == "ERROR" for s in statuses):
        overall = "ERROR"
    elif any(s == "FAIL" for s in statuses):
        overall = "FAIL"
    else:
        overall = "PASS"
    report = {
        "schema_version": SCHEMA,
        "subcommand": subcommand,
        "case": case,
        "artifact_status": overall,
        "semantic_status": "REQUIRES_REVIEW",
        "checks": checks,
        "hashes": hashes,
    }
    if diagnostics is not None:
        report["diagnostics"] = diagnostics
    return report


def write_report(report, report_path):
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, sort_keys=True)
        f.write("\n")


def exit_code_for(report):
    statuses = [c["status"] for c in report["checks"]]
    if any(s == "ERROR" for s in statuses):
        return 2
    if any(s == "FAIL" for s in statuses):
        return 1
    return 0


# --------------------------------------------------------------------------
# Frontmatter parsing (minimal, key: value only; good enough for these files)
# --------------------------------------------------------------------------


def parse_frontmatter(text):
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    block = text[4:end]
    body = text[end + 4 :]
    fields = {}
    for line in block.splitlines():
        if not line.strip() or line.strip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip()] = value.strip()
    return fields, body


# --------------------------------------------------------------------------
# Structure subcommand
# --------------------------------------------------------------------------


def structure_checks(repo):
    checks = []
    diagnostics = {}

    skills_dir = os.path.join(repo, "plugins", "engineering", "skills")
    agents_dir = os.path.join(repo, "plugins", "engineering", "agents")
    policy_path = os.path.join(repo, "plugins", "engineering", "context", "CLAUDE.md")
    comment_cleanup_skill = os.path.join(skills_dir, "comment-cleanup", "SKILL.md")
    references_dir = os.path.join(skills_dir, "comment-cleanup", "references")
    guidance_ref = os.path.join(references_dir, "comment-guidance.md")
    source_basis_ref = os.path.join(references_dir, "source-basis.md")
    prr_skill = os.path.join(skills_dir, "production-readiness-review", "SKILL.md")
    plan_auditor_agent = os.path.join(agents_dir, "plan-auditor.md")
    evals_dir = os.path.join(repo, "plugins", "engineering", "evals")

    # 1. skill set
    if os.path.isdir(skills_dir):
        actual_skills = {n for n in os.listdir(skills_dir) if os.path.isdir(os.path.join(skills_dir, n))}
    else:
        actual_skills = set()
    checks.append(
        check(
            "skill_set_matches",
            actual_skills == SKILL_NAMES,
            "expected {} found {}".format(sorted(SKILL_NAMES), sorted(actual_skills)),
        )
    )

    # 2. agent set
    if os.path.isdir(agents_dir):
        actual_agents = {os.path.splitext(n)[0] for n in os.listdir(agents_dir) if n.endswith(".md")}
    else:
        actual_agents = set()
    checks.append(
        check(
            "agent_set_matches",
            actual_agents == AGENT_NAMES,
            "expected {} found {}".format(sorted(AGENT_NAMES), sorted(actual_agents)),
        )
    )

    # 3/4/5. policy checks
    policy_text = None
    if os.path.isfile(policy_path):
        with open(policy_path, "r", encoding="utf-8") as f:
            policy_text = f.read()
    if policy_text is None:
        checks.append(check("policy_first_line", False, "{} missing".format(policy_path)))
        checks.append(check("policy_newline_count", False, "{} missing".format(policy_path)))
        checks.append(check("policy_no_forbidden_tokens", False, "{} missing".format(policy_path)))
    else:
        first_line = policy_text.splitlines()[0] if policy_text else ""
        checks.append(
            check(
                "policy_first_line",
                first_line == "# Agent operating policy",
                "first line: {!r}".format(first_line),
            )
        )
        newline_count = policy_text.count("\n")
        diagnostics["policy_newlines"] = newline_count
        diagnostics["policy_bytes"] = len(policy_text.encode("utf-8"))
        checks.append(
            check(
                "policy_newline_count",
                newline_count <= 120,
                "{} newlines (limit 120)".format(newline_count),
            )
        )
        forbidden = [tok for tok in ("${CLAUDE_PLUGIN_ROOT}", "@import", "references/comment-guidance.md") if tok in policy_text]
        checks.append(
            check(
                "policy_no_forbidden_tokens",
                not forbidden,
                "forbidden tokens present: {}".format(forbidden) if forbidden else "none present",
            )
        )

    # 6. reference files exist
    refs_exist = os.path.isfile(guidance_ref) and os.path.isfile(source_basis_ref)
    checks.append(
        check(
            "reference_files_exist",
            refs_exist,
            "comment-guidance.md exists={} source-basis.md exists={}".format(
                os.path.isfile(guidance_ref), os.path.isfile(source_basis_ref)
            ),
        )
    )

    # 7. canonical reference forms + resolving relative links inside comment-cleanup/SKILL.md
    bad_occurrences = []
    md_files = []
    for base in (skills_dir, agents_dir):
        for root, _dirs, files in os.walk(base):
            for name in files:
                if name.endswith(".md"):
                    md_files.append(os.path.join(root, name))
    for path in md_files:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        stripped_text = text
        for form in CANONICAL_REFERENCE_FORMS:
            stripped_text = stripped_text.replace(form, "")
        if "comment-guidance.md" in stripped_text:
            for m in re.finditer(r".{0,40}comment-guidance\.md", stripped_text):
                bad_occurrences.append("{}: ...{}".format(path, m.group(0)))
    unresolved_links = []
    if os.path.isfile(comment_cleanup_skill):
        with open(comment_cleanup_skill, "r", encoding="utf-8") as f:
            skill_text = f.read()
        for m in re.finditer(r"\]\((references/[^)\s]+)\)", skill_text):
            rel = m.group(1)
            if not os.path.isfile(os.path.join(skills_dir, "comment-cleanup", rel)):
                unresolved_links.append(rel)
    checks.append(
        check(
            "canonical_reference_forms",
            not bad_occurrences and not unresolved_links,
            "bad_occurrences={} unresolved_links={}".format(bad_occurrences, unresolved_links),
        )
    )

    # 8. legacy phrases absent
    legacy_found = []
    if os.path.isfile(comment_cleanup_skill):
        with open(comment_cleanup_skill, "r", encoding="utf-8") as f:
            body_text = f.read()
        for phrase in LEGACY_PHRASES:
            if phrase in body_text:
                legacy_found.append(phrase)
    checks.append(
        check(
            "legacy_phrases_absent",
            not legacy_found,
            "found: {}".format(legacy_found) if legacy_found else "none present",
        )
    )

    # 9. frozen frontmatter fields
    frozen_mismatches = []
    for agent_name, expected in AGENT_FROZEN_FIELDS.items():
        path = os.path.join(agents_dir, agent_name + ".md")
        if not os.path.isfile(path):
            frozen_mismatches.append("{}: missing file".format(agent_name))
            continue
        with open(path, "r", encoding="utf-8") as f:
            fields, _ = parse_frontmatter(f.read())
        for key, expected_value in expected.items():
            actual_value = fields.get(key)
            if expected_value is None:
                if key in fields:
                    frozen_mismatches.append("{}: unexpected {}={!r}".format(agent_name, key, actual_value))
            elif actual_value != expected_value:
                frozen_mismatches.append(
                    "{}: {}={!r} expected {!r}".format(agent_name, key, actual_value, expected_value)
                )
    if os.path.isfile(comment_cleanup_skill):
        with open(comment_cleanup_skill, "r", encoding="utf-8") as f:
            fields, _ = parse_frontmatter(f.read())
        for key, expected_value in COMMENT_CLEANUP_FROZEN_FIELDS.items():
            actual_value = fields.get(key)
            if actual_value != expected_value:
                frozen_mismatches.append(
                    "comment-cleanup: {}={!r} expected {!r}".format(key, actual_value, expected_value)
                )
    else:
        frozen_mismatches.append("comment-cleanup: SKILL.md missing")
    checks.append(
        check(
            "frontmatter_frozen_fields",
            not frozen_mismatches,
            "mismatches: {}".format(frozen_mismatches) if frozen_mismatches else "all frozen fields match",
        )
    )

    # 10. plan-auditor markers
    if os.path.isfile(plan_auditor_agent):
        with open(plan_auditor_agent, "r", encoding="utf-8") as f:
            pa_text = f.read()
        has_markers = "PLAN_COMPLETE" in pa_text and "PLAN ITEMS:" in pa_text
        checks.append(check("plan_auditor_markers", has_markers, "PLAN_COMPLETE and PLAN ITEMS: present={}".format(has_markers)))
    else:
        checks.append(check("plan_auditor_markers", False, "plan-auditor.md missing"))

    # 11. case dirs + tags + file layout
    case_issues = []
    for case_id, dirname in CASE_DIRS.items():
        case_dir = os.path.join(evals_dir, dirname)
        if not os.path.isdir(case_dir):
            case_issues.append("{}: {} missing".format(case_id, dirname))
            continue
        case_yaml = os.path.join(case_dir, "case.yaml")
        fixture_sh = os.path.join(case_dir, "fixture.sh")
        prompt_md = os.path.join(case_dir, "prompt.md")
        if case_id == "B01":
            required = ["case.yaml", "prompt.md", "fixture.sh"]
            for name in required:
                if not os.path.isfile(os.path.join(case_dir, name)):
                    case_issues.append("{}: missing {}".format(case_id, name))
            for grader in ("skill-fired.md", "directives-intact.md", "rubric.md"):
                gpath = os.path.join(case_dir, "graders", grader)
                if not os.path.isfile(gpath):
                    case_issues.append("{}: missing graders/{}".format(case_id, grader))
                elif grader == "skill-fired.md" and sha256_file(gpath) != SKILL_FIRED_BASELINE_SHA256:
                    case_issues.append("{}: graders/skill-fired.md changed from its baseline".format(case_id))
        else:
            if not os.path.isfile(case_yaml):
                case_issues.append("{}: missing case.yaml".format(case_id))
            if not os.path.isfile(fixture_sh):
                case_issues.append("{}: missing fixture.sh".format(case_id))
            if os.path.isfile(prompt_md):
                case_issues.append("{}: unexpected prompt.md".format(case_id))
        # prompt.md frontmatter overrides case.yaml, so tags are read from
        # prompt.md when it exists and from case.yaml otherwise.
        tag_source = prompt_md if os.path.isfile(prompt_md) else case_yaml
        if os.path.isfile(tag_source):
            with open(tag_source, "r", encoding="utf-8") as f:
                tag_text = f.read()
            tag_line = ""
            for line in tag_text.splitlines():
                if line.strip().startswith("tags:"):
                    tag_line = line
                    break
            for tag in CASE_TAGS[case_id]:
                if not re.search(r"[\[,\s]" + re.escape(tag) + r"[\],\s]", tag_line):
                    case_issues.append("{}: missing tag {}".format(case_id, tag))
    checks.append(
        check(
            "case_dirs_and_tags",
            not case_issues,
            "issues: {}".format(case_issues) if case_issues else "all eight cases present with expected layout/tags",
        )
    )

    # 12. fixture.sh calls build_fixture.py with its own CASE_ID
    fixture_case_issues = []
    for case_id, dirname in CASE_DIRS.items():
        fixture_sh = os.path.join(evals_dir, dirname, "fixture.sh")
        if not os.path.isfile(fixture_sh):
            continue
        with open(fixture_sh, "r", encoding="utf-8") as f:
            text = f.read()
        if "build_fixture.py" in text:
            if "--case {}".format(dirname) not in text:
                fixture_case_issues.append("{}: fixture.sh does not pass --case {}".format(case_id, dirname))
    checks.append(
        check(
            "fixture_sh_case_ids",
            not fixture_case_issues,
            "issues: {}".format(fixture_case_issues) if fixture_case_issues else "all fixture.sh scripts reference their own CASE_ID",
        )
    )

    # 13. fixtures.json / manifest.json parse and agree
    support_dir = os.path.join(evals_dir, "comment-guidance-support")
    fixtures_path = os.path.join(support_dir, "fixtures.json")
    manifest_path = os.path.join(support_dir, "manifest.json")
    agree_detail = ""
    agree_ok = False
    fixtures_data = None
    manifest_data = None
    try:
        fixtures_data = load_json_file(fixtures_path, "fixtures_manifest_parse")
        manifest_data = load_json_file(manifest_path, "fixtures_manifest_parse")
        fixture_cases = set(fixtures_data.get("cases", {}).keys())
        manifest_cases = set(manifest_data.get("cases", {}).keys())
        mismatches = []
        if fixture_cases != manifest_cases:
            mismatches.append("case sets differ: fixtures={} manifest={}".format(sorted(fixture_cases), sorted(manifest_cases)))
        for case_id in fixture_cases & manifest_cases:
            case_data = fixtures_data["cases"][case_id]
            all_files = set(case_data.get("base_files", {}).keys()) | set(case_data.get("input_overrides", {}).keys())
            declared = manifest_data["cases"][case_id]
            declared_paths = set()
            for aw in declared.get("allowed_writes", []):
                declared_paths.add(aw["path"])
            declared_paths |= set(declared.get("immutable_paths", []))
            for pd in declared.get("protected_directives", []):
                declared_paths.add(pd["path"])
            for sr in declared.get("structured_regions", []):
                declared_paths.add(sr["path"])
            for sf in declared.get("semantic_facts", []):
                declared_paths.add(sf["path"])
            # required_artifacts may name files the builder/agent produces at run time
            # (e.g. a captured failure log) rather than static fixture content.
            declared_paths -= set(declared.get("required_artifacts", []))
            missing_from_base = declared_paths - all_files
            if missing_from_base:
                mismatches.append("{}: manifest paths not in base_files: {}".format(case_id, sorted(missing_from_base)))
        agree_ok = not mismatches
        agree_detail = "; ".join(mismatches) if mismatches else "fixtures.json and manifest.json agree"
    except HardError as exc:
        raise exc
    checks.append(check("fixtures_manifest_parse_and_agree", agree_ok, agree_detail))

    # 13b. every grader that reads a workspace file names a path the fixture, the manifest's
    # required/allowed artifacts, or the prompt's mandated output can actually produce.
    target_issues = []
    try:
        for case_id, dirname in CASE_DIRS.items():
            if dirname not in (fixtures_data.get("cases", {}) if fixtures_data else {}):
                continue
            case_data = fixtures_data["cases"][dirname]
            declared = manifest_data["cases"].get(dirname, {})
            producible = set(case_data.get("base_files", {})) | set(case_data.get("input_overrides", {}))
            producible |= set(declared.get("required_artifacts", []))
            patterns = declared.get("allowed_tool_artifacts", [])
            grader_texts = []
            case_dir = os.path.join(evals_dir, dirname)
            for name in ("case.yaml",):
                fp = os.path.join(case_dir, name)
                if os.path.isfile(fp):
                    with open(fp, "r", encoding="utf-8") as f:
                        grader_texts.append(f.read())
            gdir = os.path.join(case_dir, "graders")
            if os.path.isdir(gdir):
                for name in sorted(os.listdir(gdir)):
                    with open(os.path.join(gdir, name), "r", encoding="utf-8") as f:
                        grader_texts.append(f.read())
            for text in grader_texts:
                for m in re.finditer(r"source:\s*file\s*\n\s*path:\s*([^\s]+)", text):
                    target = m.group(1).strip("'\"")
                    if target not in producible and not is_allowed_artifact(target, patterns):
                        target_issues.append("{}: grader reads {} which no fixture, required artifact, or allowed artifact produces".format(case_id, target))
    except (KeyError, TypeError, NameError) as exc:
        target_issues.append("cross-check could not run: {}".format(exc))
    checks.append(
        check(
            "grader_file_targets_producible",
            not target_issues,
            "; ".join(target_issues) if target_issues else "every file-target grader names a producible path",
        )
    )

    # 14. no tracked new file under docs/plans/ or evals/results/
    tracked_issue = None
    if os.path.isdir(os.path.join(repo, ".git")):
        try:
            out = subprocess.run(
                ["git", "-C", repo, "ls-files"],
                capture_output=True, text=True, check=True,
            ).stdout
            offenders = [
                line for line in out.splitlines()
                if line.startswith("docs/plans/") or "/evals/results/" in line or line.startswith("evals/results/")
            ]
            tracked_issue = offenders
        except (OSError, subprocess.CalledProcessError) as exc:
            tracked_issue = "git ls-files failed: {}".format(exc)
    checks.append(
        check(
            "no_ignored_new_tracked_files",
            not tracked_issue,
            "offenders: {}".format(tracked_issue) if tracked_issue else "none present",
        )
    )

    # 15. prr wrong sentence absent
    if os.path.isfile(prr_skill):
        with open(prr_skill, "r", encoding="utf-8") as f:
            prr_text = f.read()
        has_wrong = "`browser-tester` has Bash" in prr_text
        checks.append(check("prr_wrong_sentence_absent", not has_wrong, "wrong sentence present={}".format(has_wrong)))
    else:
        checks.append(check("prr_wrong_sentence_absent", False, "{} missing".format(prr_skill)))

    hashes = {
        "checker": sha256_file(os.path.abspath(__file__)),
        "fixtures": sha256_file_or_none(fixtures_path),
        "manifest": sha256_file_or_none(manifest_path),
    }
    return checks, hashes, diagnostics


def run_structure(args):
    repo = args.repo
    if not os.path.isdir(repo):
        checks = [{"id": "repo_exists", "status": "ERROR", "detail": "{} is not a directory".format(repo)}]
        report = build_report("structure", None, checks, {"checker": sha256_file(os.path.abspath(__file__)), "fixtures": None, "manifest": None})
        if args.report:
            write_report(report, args.report)
        print("STRUCTURE ERROR")
        return 2

    try:
        checks, hashes, diagnostics = structure_checks(repo)
    except HardError as exc:
        checks = [{"id": exc.check_id, "status": "ERROR", "detail": exc.detail}]
        report = build_report("structure", None, checks, {"checker": sha256_file(os.path.abspath(__file__)), "fixtures": None, "manifest": None})
        if args.report:
            write_report(report, args.report)
        print("STRUCTURE ERROR")
        return 2

    report = build_report("structure", None, checks, hashes, diagnostics)
    if args.report:
        write_report(report, args.report)
    print("STRUCTURE {}".format(report["artifact_status"]))
    return exit_code_for(report)


# --------------------------------------------------------------------------
# Artifact subcommand: building the trusted expected tree
# --------------------------------------------------------------------------


def validate_relpath(relpath, check_id="path_traversal"):
    if os.path.isabs(relpath) or ".." in relpath.replace("\\", "/").split("/"):
        raise HardError(check_id, "unsafe relative path: {}".format(relpath))
    return relpath


def build_expected_tree(case_data):
    tree = {}
    for relpath, content in case_data.get("base_files", {}).items():
        validate_relpath(relpath)
        tree[relpath] = content.encode("utf-8")
    for relpath, content in case_data.get("input_overrides", {}).items():
        validate_relpath(relpath)
        tree[relpath] = content.encode("utf-8")
    return tree


def is_allowed_artifact(relpath, patterns):
    parts = relpath.split("/")
    for pat in patterns:
        if pat.endswith("/"):
            dirname = pat.rstrip("/")
            if dirname in parts[:-1]:
                return True
        else:
            if fnmatch.fnmatch(os.path.basename(relpath), pat) or fnmatch.fnmatch(relpath, pat):
                return True
    return False


MAX_CANDIDATE_FILES = 5000


def enumerate_candidate_files(candidate_root, max_file_bytes, include_git=False):
    """Walk the candidate without following links. Returns (files, symlinks, oversized,
    special). Anything that is not a regular file or directory is reported as special so the
    caller can fail closed before any read (a FIFO would otherwise block the checker)."""
    files = {}
    symlinks = []
    oversized = []
    special = []
    count = 0
    for root, dirs, filenames in os.walk(candidate_root, followlinks=False):
        rel_root = os.path.relpath(root, candidate_root)
        if rel_root == "." and not include_git:
            dirs[:] = [d for d in dirs if d != ".git"]
        keep_dirs = []
        for d in dirs:
            full = os.path.join(root, d)
            if os.path.islink(full):
                symlinks.append(os.path.relpath(full, candidate_root).replace(os.sep, "/"))
            else:
                keep_dirs.append(d)
        dirs[:] = keep_dirs
        for name in filenames:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, candidate_root).replace(os.sep, "/")
            st = os.lstat(full)
            if stat.S_ISLNK(st.st_mode):
                symlinks.append(rel)
                continue
            if not stat.S_ISREG(st.st_mode):
                special.append(rel)
                continue
            count += 1
            if count > MAX_CANDIDATE_FILES:
                raise HardError("too_many_files", "candidate has more than {} files".format(MAX_CANDIDATE_FILES))
            if st.st_size > max_file_bytes:
                oversized.append(rel)
                continue
            files[rel] = full
    return files, symlinks, oversized, special


# --------------------------------------------------------------------------
# Region-preservation checks
# --------------------------------------------------------------------------


def line_ending_style(data):
    crlf = data.count(b"\r\n")
    lf_total = data.count(b"\n")
    bare_lf = lf_total - crlf
    return crlf, bare_lf


def line_endings_changed(orig, cand):
    """True when the candidate introduces a line-ending style the original did not use.
    A pure-LF original must stay free of CRLF and a pure-CRLF original free of bare LF, so a
    partial conversion (mixed endings) is rejected, not just a whole-file flip."""
    o_crlf, o_bare = line_ending_style(orig)
    c_crlf, c_bare = line_ending_style(cand)
    if o_crlf and not o_bare and c_bare:
        return True
    if o_bare and not o_crlf and c_crlf:
        return True
    if not o_crlf and not o_bare and (c_crlf or c_bare):
        return True
    # The bytes after the last newline are invisible to a line diff.
    if orig.endswith(b"\n") != cand.endswith(b"\n"):
        return True
    return False


def python_docstring_positions(source_text):
    """Return set of (lineno, col_offset) of AST-recognised docstring string constants."""
    positions = set()
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return None
    doc_nodes = [tree] + [n for n in ast.walk(tree) if isinstance(n, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))]
    for node in doc_nodes:
        body = getattr(node, "body", None)
        if not body:
            continue
        first = body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            positions.add((first.value.lineno, first.value.col_offset))
    return positions


def is_comment_only_line(line):
    return line.strip().startswith("#")


def python_docstring_spans(source_text):
    """Return {lineno: True} for every line covered by an AST-recognised docstring, or None
    on a syntax error."""
    positions = python_docstring_positions(source_text)
    if positions is None:
        return None
    lines = set()
    tree = ast.parse(source_text)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if (node.lineno, node.col_offset) in positions:
                end = getattr(node, "end_lineno", node.lineno)
                for ln in range(node.lineno, end + 1):
                    lines.add(ln)
    return lines


def python_comment_start_cols(text):
    """Column of the unquoted '#' comment on each line, via tokenize so a '#' inside a
    string literal is not mistaken for a comment. Returns None when tokenizing fails."""
    cols = {}
    try:
        readline = iter(text.splitlines(keepends=True)).__next__
        for tok in tokenize.generate_tokens(readline):
            if tok.type == tokenize.COMMENT:
                cols[tok.start[0]] = tok.start[1]
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return None
    return cols


def python_region_check(orig_bytes, cand_bytes):
    """Return (ok, detail) for regions=comments_and_docstrings on a Python file.

    Two independent layers: (1) the AST with every docstring statement removed must be
    identical, so executable tokens, ordinary string literals, and block structure cannot
    change; (2) a line diff in which every deleted, inserted, or replaced line must be a
    comment-only line, a docstring line, a blank line adjacent to such a line, or a code line
    whose non-comment prefix is unchanged. Layer 2 is what catches whitespace and
    indentation edits that the AST does not see."""
    if line_endings_changed(orig_bytes, cand_bytes):
        return False, "line_endings_changed"
    try:
        orig_text = orig_bytes.decode("utf-8")
        cand_text = cand_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        return False, "decode_error: {}".format(exc)

    orig_doc_lines = python_docstring_spans(orig_text)
    cand_doc_lines = python_docstring_spans(cand_text)
    if orig_doc_lines is None or cand_doc_lines is None:
        return False, "python_syntax_error"

    def stripped_dump(text):
        tree = ast.parse(text)
        for node in ast.walk(tree):
            body = getattr(node, "body", None)
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and body:
                first = body[0]
                if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
                    if len(body) == 1:
                        node.body = [ast.Pass()]
                    else:
                        node.body = body[1:]
        return ast.dump(tree, annotate_fields=True, include_attributes=False)

    if stripped_dump(orig_text) != stripped_dump(cand_text):
        return False, "ast_structure_or_literal_changed"

    orig_lines = orig_text.splitlines()
    cand_lines = cand_text.splitlines()
    orig_cols = python_comment_start_cols(orig_text)
    cand_cols = python_comment_start_cols(cand_text)
    if orig_cols is None or cand_cols is None:
        return False, "python_tokenize_error"

    def orig_editable(i):
        return is_comment_only_line(orig_lines[i]) or (i + 1) in orig_doc_lines

    def cand_editable(j):
        return is_comment_only_line(cand_lines[j]) or (j + 1) in cand_doc_lines

    def blank_adjacent(lines, editable, k, lo, hi):
        """A blank line may go only when a neighbour inside the same diff block is editable."""
        if lines[k].strip() != "":
            return False
        for n in (k - 1, k + 1):
            if lo <= n < hi and editable(n):
                return True
        return False

    sm = difflib.SequenceMatcher(a=orig_lines, b=cand_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag == "delete":
            for i in range(i1, i2):
                if not (orig_editable(i) or blank_adjacent(orig_lines, orig_editable, i, i1, i2)):
                    return False, "unauthorized_line_deletion:{}".format(i + 1)
        elif tag == "insert":
            for j in range(j1, j2):
                if not (cand_editable(j) or blank_adjacent(cand_lines, cand_editable, j, j1, j2)):
                    return False, "unauthorized_line_insertion:{}".format(j + 1)
        else:  # replace
            # Code lines carrying a trailing comment may change only after the comment start.
            for idx in range(max(i2 - i1, j2 - j1)):
                i = i1 + idx
                j = j1 + idx
                has_orig = i < i2
                has_cand = j < j2
                if has_orig and (orig_editable(i) or blank_adjacent(orig_lines, orig_editable, i, i1, i2)):
                    if has_cand and not (cand_editable(j) or blank_adjacent(cand_lines, cand_editable, j, j1, j2)):
                        return False, "unauthorized_line_replacement:{}".format(i + 1)
                    continue
                if not has_orig:
                    if not (cand_editable(j) or blank_adjacent(cand_lines, cand_editable, j, j1, j2)):
                        return False, "unauthorized_line_insertion:{}".format(j + 1)
                    continue
                lineno = i + 1
                if lineno in orig_cols and has_cand:
                    prefix = orig_lines[i][: orig_cols[lineno]]
                    cand_line = cand_lines[j]
                    if cand_line.startswith(prefix):
                        # the candidate's remainder must itself be a comment or nothing
                        rest = cand_line[len(prefix):]
                        if rest.strip() == "" or ((j + 1) in cand_cols and cand_cols[j + 1] <= len(prefix)):
                            continue
                        if rest.lstrip().startswith("#"):
                            continue
                        return False, "code_suffix_changed:{}".format(lineno)
                    if cand_line == prefix.rstrip():
                        continue
                    return False, "code_prefix_changed:{}".format(lineno)
                return False, "unauthorized_line_replacement:{}".format(lineno)
    return True, "comments_and_docstrings preserved"


COMMENT_LEADER = {".go": "//", ".js": "//"}


def line_scan_region_check(orig_bytes, cand_bytes, leader):
    """Bounded line scanner for Go/JS. Whole-line '//' comments, '/* ... */' block lines,
    and the text after a trailing '//' outside a string literal are editable; every other
    byte of every line must be unchanged. Inserted lines must be comment lines or blank lines
    adjacent to a comment line. There is no AST backstop for these languages, so the diff
    walk is strict on both the original and the candidate side."""
    if line_endings_changed(orig_bytes, cand_bytes):
        return False, "line_endings_changed"
    try:
        orig_text = orig_bytes.decode("utf-8")
        cand_text = cand_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        return False, "decode_error: {}".format(exc)

    def classify(text):
        lines = text.splitlines()
        in_block = False
        code_prefix = {}
        comment_only = set()
        for idx, line in enumerate(lines):
            lineno = idx + 1
            if in_block:
                comment_only.add(lineno)
                if "*/" in line:
                    in_block = False
                    if line.split("*/", 1)[1].strip():
                        comment_only.discard(lineno)
                        code_prefix.pop(lineno, None)
                continue
            stripped = line.strip()
            if stripped.startswith("/*"):
                if "*/" not in line:
                    in_block = True
                    comment_only.add(lineno)
                    continue
                if line.split("*/", 1)[1].strip() == "":
                    comment_only.add(lineno)
                    continue
                # code after a one-line block comment: treat the whole line as code
            if stripped.startswith(leader):
                comment_only.add(lineno)
                continue
            in_str = None
            i = 0
            found = -1
            while i < len(line):
                c = line[i]
                if in_str:
                    if c == "\\":
                        i += 2
                        continue
                    if c == in_str:
                        in_str = None
                elif c in ("'", '"', "`"):
                    in_str = c
                elif line[i : i + len(leader)] == leader:
                    found = i
                    break
                i += 1
            if found >= 0:
                code_prefix[lineno] = line[:found]
        return lines, comment_only, code_prefix

    if "`" in orig_text or "`" in cand_text:
        # A backtick template literal can span lines and hide '//' or '/*' inside a string;
        # the per-line scanner cannot classify it, so the file is unsupported (fail closed).
        return False, "unsupported_template_literal"

    orig_lines, orig_comment, orig_prefix = classify(orig_text)
    cand_lines, cand_comment, cand_prefix = classify(cand_text)

    def orig_editable(i):
        return (i + 1) in orig_comment

    def cand_editable(j):
        return (j + 1) in cand_comment

    def blank_adjacent(lines, editable, k, lo, hi):
        if lines[k].strip() != "":
            return False
        for n in (k - 1, k + 1):
            if lo <= n < hi and editable(n):
                return True
        return False

    sm = difflib.SequenceMatcher(a=orig_lines, b=cand_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            # An unchanged line must keep its classification: opening a block comment above
            # live code (or deleting a closing "*/") would otherwise turn code into comment
            # without that line ever appearing in a non-equal opcode.
            for off in range(i2 - i1):
                if orig_editable(i1 + off) != cand_editable(j1 + off):
                    return False, "comment_scope_changed:{}".format(i1 + off + 1)
            continue
        if tag == "delete":
            for i in range(i1, i2):
                if not (orig_editable(i) or blank_adjacent(orig_lines, orig_editable, i, i1, i2)):
                    return False, "unauthorized_line_deletion:{}".format(i + 1)
        elif tag == "insert":
            for j in range(j1, j2):
                if not (cand_editable(j) or blank_adjacent(cand_lines, cand_editable, j, j1, j2)):
                    return False, "unauthorized_line_insertion:{}".format(j + 1)
        else:
            for idx in range(max(i2 - i1, j2 - j1)):
                i = i1 + idx
                j = j1 + idx
                has_orig = i < i2
                has_cand = j < j2
                if has_orig and (orig_editable(i) or blank_adjacent(orig_lines, orig_editable, i, i1, i2)):
                    if has_cand and not (cand_editable(j) or blank_adjacent(cand_lines, cand_editable, j, j1, j2)):
                        return False, "unauthorized_line_replacement:{}".format(i + 1)
                    continue
                if not has_orig:
                    if not (cand_editable(j) or blank_adjacent(cand_lines, cand_editable, j, j1, j2)):
                        return False, "unauthorized_line_insertion:{}".format(j + 1)
                    continue
                lineno = i + 1
                if lineno in orig_prefix and has_cand:
                    prefix = orig_prefix[lineno]
                    cand_line = cand_lines[j]
                    if cand_line == prefix.rstrip():
                        continue
                    if cand_line.startswith(prefix) and (j + 1) in cand_prefix and cand_prefix[j + 1] == prefix:
                        continue
                    return False, "code_prefix_changed:{}".format(lineno)
                return False, "unauthorized_line_replacement:{}".format(lineno)
    return True, "comments_and_docstrings preserved"


def region_check(relpath, orig_bytes, cand_bytes):
    ext = os.path.splitext(relpath)[1]
    if ext == ".py":
        return python_region_check(orig_bytes, cand_bytes)
    if ext in COMMENT_LEADER:
        return line_scan_region_check(orig_bytes, cand_bytes, COMMENT_LEADER[ext])
    raise HardError("unsupported_region_syntax", "no comments_and_docstrings support for extension {}".format(ext))


# --------------------------------------------------------------------------
# Directive / structured-region / git-metadata checks
# --------------------------------------------------------------------------


def check_protected_directives(candidate_files, directives):
    results = []
    for spec in directives:
        path = spec["path"]
        text_needle = spec["text"]
        attached_to = spec.get("attached_to")
        group = spec.get("group", [])
        full = candidate_files.get(path)
        detail_id = "directive:{}:{}".format(path, text_needle[:30])
        if full is None:
            results.append(check(detail_id, False, "{} missing from candidate".format(path)))
            continue
        with open(full, "rb") as f:
            raw = f.read()
        try:
            lines = raw.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            results.append(check(detail_id, False, "{} is not valid UTF-8: {}".format(path, exc)))
            continue
        occurrences = [i for i, line in enumerate(lines) if line == text_needle]
        if not occurrences:
            results.append(check(detail_id, False, "directive text not found byte-identical in {}".format(path)))
            continue
        if len(occurrences) != 1:
            results.append(check(detail_id, False, "directive appears {} times; expected exactly once".format(len(occurrences))))
            continue
        idx = occurrences[0]
        ok = True
        detail_parts = []
        if attached_to is not None:
            j = idx + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            if j >= len(lines) or lines[j] != attached_to:
                ok = False
                detail_parts.append("attached_to mismatch")
        if group:
            if text_needle in group:
                offset = group.index(text_needle)
                start = idx - offset
                if start < 0 or lines[start : start + len(group)] != group:
                    ok = False
                    detail_parts.append("group sequence mismatch")
            else:
                ok = False
                detail_parts.append("directive text not part of its declared group")
        results.append(check(detail_id, ok, "; ".join(detail_parts) if detail_parts else "directive preserved"))
    return results


def check_structured_regions(candidate_files, expected_tree, regions):
    results = []
    for spec in regions:
        path = spec["path"]
        start_marker = spec["start_marker"]
        end_marker = spec["end_marker"]
        detail_id = "structured_region:{}".format(path)
        expected = expected_tree.get(path)
        full = candidate_files.get(path)
        if expected is None or full is None:
            results.append(check(detail_id, False, "{} missing".format(path)))
            continue
        with open(full, "rb") as f:
            cand_bytes = f.read()

        def extract(data):
            s = data.find(start_marker.encode("utf-8"))
            e = data.find(end_marker.encode("utf-8"))
            if s == -1 or e == -1 or e < s:
                return None
            return data[s : e + len(end_marker.encode("utf-8"))]

        exp_region = extract(expected)
        cand_region = extract(cand_bytes)
        if exp_region is None:
            results.append(check(detail_id, False, "markers not found in trusted fixture"))
            continue
        results.append(
            check(detail_id, exp_region == cand_region, "byte-identical" if exp_region == cand_region else "structured region changed")
        )
    return results


GIT_SCRUBBED_ENV_KEYS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                         "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_TEMPLATE_DIR", "GIT_CONFIG",
                         "GIT_CONFIG_PARAMETERS", "GIT_NAMESPACE", "GIT_CEILING_DIRECTORIES")
SUSPICIOUS_CONFIG_TOKENS = ("[alias", "hooksPath", "fsmonitor", "sshCommand", "[include", "[includeIf",
                            "[credential", "[url ", "pager", "editor", "askPass", "[core]\n\tprotocol")


def git_blob_sha1(data):
    h = hashlib.sha1()
    h.update(b"blob " + str(len(data)).encode("ascii") + b"\0" + data)
    return h.hexdigest()


def scrubbed_git_env():
    env = {k: v for k, v in os.environ.items() if k not in GIT_SCRUBBED_ENV_KEYS}
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_SYSTEM"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def check_git_metadata(candidate_root, case_fixture):
    """The oracle is the trusted fixture, not anything in the workspace: HEAD's tree must
    list exactly the base_files with their content-derived blob ids, the repository must
    have exactly one ref, no active hooks, and no config entry that can redirect or execute
    anything. A missing or non-directory .git is a failure because the builder created one."""
    git_dir = os.path.join(candidate_root, ".git")
    if os.path.islink(git_dir) or not os.path.isdir(git_dir):
        return check("git_metadata_changed", False, ".git is missing, a symlink, or not a directory")
    _files, symlinks, _oversized, special = enumerate_candidate_files(git_dir, 64 * 1024 * 1024)
    if symlinks or special:
        return check("git_metadata_changed", False, "symlinks or special files under .git: {}".format(symlinks + special))
    hooks_dir = os.path.join(git_dir, "hooks")
    if os.path.isdir(hooks_dir):
        active = [n for n in os.listdir(hooks_dir) if not n.endswith(".sample")]
        if active:
            return check("git_metadata_changed", False, "unexpected hooks: {}".format(active))
    config_path = os.path.join(git_dir, "config")
    if os.path.isfile(config_path):
        with open(config_path, "rb") as f:
            config_text = f.read().decode("utf-8", "replace")
        hits = [t for t in SUSPICIOUS_CONFIG_TOKENS if t in config_text]
        if hits:
            return check("git_metadata_changed", False, "suspicious .git/config entries: {}".format(hits))
    env = scrubbed_git_env()
    try:
        refs = subprocess.run(
            ["git", "-C", candidate_root, "--no-optional-locks", "for-each-ref", "--format=%(refname) %(objectname)"],
            capture_output=True, text=True, check=True, env=env,
        ).stdout.split()
        head = subprocess.run(
            ["git", "-C", candidate_root, "--no-optional-locks", "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True, env=env,
        ).stdout.strip()
        tree = subprocess.run(
            ["git", "-C", candidate_root, "--no-optional-locks", "ls-tree", "-r", "-z", "HEAD"],
            capture_output=True, text=True, check=True, env=env,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        return check("git_metadata_changed", False, "git query failed: {}".format(exc))
    if len(refs) != 2 or refs[1] != head:
        return check("git_metadata_changed", False, "expected exactly one ref at HEAD, found {}".format(refs))
    baseline_path = os.path.join(git_dir, "comment_guidance_baseline")
    if not os.path.isfile(baseline_path):
        return check("git_metadata_changed", False, "builder's .git/comment_guidance_baseline is missing")
    with open(baseline_path, "rb") as f:
        recorded = f.read().decode("ascii", "replace").strip()
    if head != recorded:
        return check("git_metadata_changed", False, "HEAD {} != builder baseline {}".format(head, recorded))
    try:
        parents = subprocess.run(
            ["git", "-C", candidate_root, "--no-optional-locks", "rev-list", "--parents", "-n", "1", "HEAD"],
            capture_output=True, text=True, check=True, env=env,
        ).stdout.split()
    except (OSError, subprocess.CalledProcessError) as exc:
        return check("git_metadata_changed", False, "git query failed: {}".format(exc))
    if len(parents) != 1:
        return check("git_metadata_changed", False, "HEAD is not the builder's root commit")
    expected = {}
    for relpath, content in case_fixture.get("base_files", {}).items():
        expected[relpath] = git_blob_sha1(content.encode("utf-8"))
    actual = {}
    for entry in tree.split("\0"):
        if not entry:
            continue
        meta, _tab, name = entry.partition("\t")
        parts = meta.split()
        if len(parts) != 3 or parts[1] != "blob":
            return check("git_metadata_changed", False, "non-blob entry in HEAD tree: {}".format(entry))
        actual[name] = parts[2]
    if actual != expected:
        diff = sorted(set(actual.items()) ^ set(expected.items()))
        return check("git_metadata_changed", False, "HEAD tree differs from trusted base_files: {}".format(diff[:6]))
    return check("git_metadata_changed", True, "HEAD tree matches trusted base_files; one ref; no hooks")


# --------------------------------------------------------------------------
# Artifact subcommand driver
# --------------------------------------------------------------------------


def run_artifacts_inner(case_id, fixtures_path, manifest_path, candidate_root):
    checks = []
    fixtures_data = load_json_file(fixtures_path, "invalid_input")
    manifest_data = load_json_file(manifest_path, "invalid_input")

    if case_id not in fixtures_data.get("cases", {}) or case_id not in manifest_data.get("cases", {}):
        raise HardError("unknown_case", "{} not registered in fixtures/manifest".format(case_id))

    case_fixture = fixtures_data["cases"][case_id]
    case_manifest = manifest_data["cases"][case_id]
    mode = case_manifest.get("mode", case_fixture.get("mode"))
    max_file_bytes = manifest_data.get("cases", {})[case_id].get("max_file_bytes", 262144)
    allowed_tool_artifacts = case_manifest.get("allowed_tool_artifacts", [])

    if not os.path.isdir(candidate_root):
        raise HardError("missing_workspace", "{} is not a directory".format(candidate_root))

    manifest_declared_paths = set()
    for aw in case_manifest.get("allowed_writes", []):
        manifest_declared_paths.add(aw["path"])
    manifest_declared_paths |= set(case_manifest.get("immutable_paths", []))
    for pd in case_manifest.get("protected_directives", []):
        manifest_declared_paths.add(pd["path"])
    for sr in case_manifest.get("structured_regions", []):
        manifest_declared_paths.add(sr["path"])
    for sf in case_manifest.get("semantic_facts", []):
        manifest_declared_paths.add(sf["path"])
    manifest_declared_paths |= set(case_manifest.get("authorized_code_changes", []))
    manifest_declared_paths |= set(case_manifest.get("required_artifacts", []))
    for relpath in manifest_declared_paths:
        validate_relpath(relpath, "manifest_path_traversal")

    expected_tree = build_expected_tree(case_fixture)
    candidate_files, symlinks, oversized, special = enumerate_candidate_files(candidate_root, max_file_bytes)

    if symlinks:
        raise HardError("symlink_present", "symlinks found in candidate: {}".format(symlinks))
    if special:
        raise HardError("special_file_present", "non-regular files found in candidate: {}".format(special))
    if oversized:
        raise HardError("oversized_file", "files exceeding {} bytes: {}".format(max_file_bytes, oversized))

    # unexpected / missing files
    expected_paths = set(expected_tree.keys())
    candidate_paths = set(candidate_files.keys())
    required_paths = set(case_manifest.get("required_artifacts", []))
    unexpected = sorted(
        p for p in (candidate_paths - expected_paths - required_paths)
        if not is_allowed_artifact(p, allowed_tool_artifacts)
    )
    missing = sorted(expected_paths - candidate_paths)
    checks.append(check("no_unexpected_files", not unexpected, "unexpected: {}".format(unexpected) if unexpected else "none"))
    checks.append(check("no_missing_files", not missing, "missing: {}".format(missing) if missing else "none"))

    # review modes forbid every write
    if mode in REVIEW_MODES:
        changed = []
        for relpath in sorted(expected_paths & candidate_paths):
            with open(candidate_files[relpath], "rb") as f:
                cand_bytes = f.read()
            if cand_bytes != expected_tree[relpath]:
                changed.append(relpath)
        checks.append(
            check(
                "review_mode_forbids_writes",
                not changed and not unexpected,
                "changed files in review mode: {}; unexpected files: {}".format(changed, unexpected) if (changed or unexpected) else "no writes",
            )
        )
    else:
        allowed_writes = {aw["path"]: aw["regions"] for aw in case_manifest.get("allowed_writes", [])}
        immutable_paths = set(case_manifest.get("immutable_paths", []))

        for relpath in sorted(expected_paths & candidate_paths):
            with open(candidate_files[relpath], "rb") as f:
                cand_bytes = f.read()
            exp_bytes = expected_tree[relpath]
            if relpath in immutable_paths:
                ok = cand_bytes == exp_bytes
                checks.append(check("immutable:{}".format(relpath), ok, "byte-identical" if ok else "immutable file changed"))
                continue
            regions = allowed_writes.get(relpath)
            if regions is None:
                ok = cand_bytes == exp_bytes
                checks.append(check("unlisted_immutable:{}".format(relpath), ok, "byte-identical" if ok else "changed without an allowed_writes entry"))
            elif regions == "none":
                ok = cand_bytes == exp_bytes
                checks.append(check("region_none:{}".format(relpath), ok, "byte-identical" if ok else "changed a regions=none file"))
            elif regions == "any":
                checks.append(check("region_any:{}".format(relpath), True, "unrestricted authorized-change file: {}".format(relpath)))
            elif regions == "comments_and_docstrings":
                if cand_bytes == exp_bytes:
                    checks.append(check("region_comments_and_docstrings:{}".format(relpath), True, "unchanged"))
                else:
                    ok, detail = region_check(relpath, exp_bytes, cand_bytes)
                    checks.append(check("region_comments_and_docstrings:{}".format(relpath), ok, detail))
            else:
                raise HardError("unsupported_region_syntax", "unknown regions value {} for {}".format(regions, relpath))

    # protected directives
    checks.extend(check_protected_directives(candidate_files, case_manifest.get("protected_directives", [])))

    # structured regions
    checks.extend(check_structured_regions(candidate_files, expected_tree, case_manifest.get("structured_regions", [])))

    # git metadata
    checks.append(check_git_metadata(candidate_root, case_fixture))

    # required artifacts present (e.g. new tests for implementation/repair modes)
    required = case_manifest.get("required_artifacts", [])
    missing_required = [p for p in required if p not in candidate_paths]
    if required:
        checks.append(
            check("required_artifacts_present", not missing_required, "missing: {}".format(missing_required) if missing_required else "all present")
        )

    # semantic facts -> REQUIRES_REVIEW
    for fact in case_manifest.get("semantic_facts", []):
        checks.append(
            {
                "id": "semantic_fact:{}".format(fact["id"]),
                "status": "REQUIRES_REVIEW",
                "detail": "{} ({}): {}".format(fact["id"], fact["path"], fact["fact"]),
            }
        )

    hashes = {
        "checker": sha256_file(os.path.abspath(__file__)),
        "fixtures": sha256_file(fixtures_path),
        "manifest": sha256_file(manifest_path),
    }
    return checks, hashes


def report_inside_candidate(report_path, candidate):
    if not os.path.isdir(candidate):
        return False
    candidate_real = os.path.realpath(candidate)
    report_real = os.path.realpath(report_path)
    return report_real == candidate_real or report_real.startswith(candidate_real + os.sep)


def run_artifacts(args):
    if report_inside_candidate(args.report, args.candidate):
        sys.stderr.write("--report must not be inside the candidate workspace\n")
        return 2

    try:
        checks, hashes = run_artifacts_inner(args.case, args.fixtures, args.manifest, args.candidate)
    except HardError as exc:
        checks = [{"id": exc.check_id, "status": "ERROR", "detail": exc.detail}]
        hashes = {
            "checker": sha256_file(os.path.abspath(__file__)),
            "fixtures": sha256_file_or_none(args.fixtures if os.path.isfile(args.fixtures) else None),
            "manifest": sha256_file_or_none(args.manifest if os.path.isfile(args.manifest) else None),
        }
        report = build_report("artifacts", args.case, checks, hashes)
        if args.report:
            write_report(report, args.report)
        print("ARTIFACTS ERROR case={}".format(args.case))
        return 2

    report = build_report("artifacts", args.case, checks, hashes)
    if args.report:
        write_report(report, args.report)
    print("ARTIFACTS {} case={}".format(report["artifact_status"], args.case))
    return exit_code_for(report)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def build_parser():
    parser = argparse.ArgumentParser(prog="comment_guidance_checks.py")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_structure = sub.add_parser("structure")
    p_structure.add_argument("--repo", required=True)
    p_structure.add_argument("--report")

    p_artifacts = sub.add_parser("artifacts")
    p_artifacts.add_argument("--case", required=True)
    p_artifacts.add_argument("--fixtures", required=True)
    p_artifacts.add_argument("--manifest", required=True)
    p_artifacts.add_argument("--candidate", required=True)
    p_artifacts.add_argument("--report", required=True)

    return parser


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.subcommand == "structure":
        return run_structure(args)
    if args.subcommand == "artifacts":
        return run_artifacts(args)
    parser.error("unknown subcommand")
    return 2


if __name__ == "__main__":
    sys.exit(main())
