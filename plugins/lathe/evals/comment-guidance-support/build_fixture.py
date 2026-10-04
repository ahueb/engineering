#!/usr/bin/env python3
"""Builds one comment-guidance fixture workspace from the trusted fixtures.json data.

    python3 build_fixture.py --case CASE_ID --workspace WORKSPACE

CASE_ID is the case directory name (e.g. behaviour-comment-cleanup). Standard library
only; no network access; the only commands executed are the case's own trusted
`capture_failure_log` command, run inside the freshly built workspace with hooks and
global/system git config disabled.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES_PATH = os.path.join(HERE, "fixtures.json")

GIT_ENV_OVERRIDES = {
    "GIT_CONFIG_GLOBAL": os.devnull,
    "GIT_CONFIG_SYSTEM": os.devnull,
    "GIT_CONFIG_NOSYSTEM": "1",
    "GIT_TERMINAL_PROMPT": "0",
}
# Inherited GIT_* variables (set, for example, inside a git hook) would redirect init/add/
# commit at the invoking repository or seed hooks from a template directory.
GIT_ENV_STRIPPED = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                    "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_TEMPLATE_DIR", "GIT_CONFIG",
                    "GIT_CONFIG_PARAMETERS", "GIT_NAMESPACE", "GIT_CEILING_DIRECTORIES")


def child_env():
    env = {k: v for k, v in os.environ.items() if k not in GIT_ENV_STRIPPED}
    env.update(GIT_ENV_OVERRIDES)
    return env


def fail(message, code=2):
    sys.stderr.write("build_fixture: {}\n".format(message))
    return code


def validate_dest(workspace, relpath):
    if os.path.isabs(relpath):
        raise ValueError("absolute path not allowed: {}".format(relpath))
    parts = relpath.replace("\\", "/").split("/")
    if ".." in parts or "" in parts[1:]:
        raise ValueError("path traversal not allowed: {}".format(relpath))
    dest = os.path.join(workspace, *parts)
    dest_real_parent = os.path.realpath(os.path.dirname(dest))
    workspace_real = os.path.realpath(workspace)
    if os.path.commonpath([dest_real_parent, workspace_real]) != workspace_real:
        raise ValueError("destination parent escapes workspace via symlink: {}".format(relpath))
    return dest


def write_files(workspace, files):
    for relpath, content in files.items():
        dest = validate_dest(workspace, relpath)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "w", encoding="utf-8", newline="") as f:
            f.write(content)


def run_git(workspace, args, env):
    subprocess.run(
        ["git", "-C", workspace] + args,
        check=True,
        capture_output=True,
        env=env,
    )


def build(case_id, workspace):
    with open(FIXTURES_PATH, "r", encoding="utf-8") as f:
        fixtures = json.load(f)

    cases = fixtures.get("cases", {})
    if case_id not in cases:
        raise SystemExit(fail("unknown case id: {}".format(case_id)))

    case_data = cases[case_id]
    os.makedirs(workspace, exist_ok=True)

    write_files(workspace, case_data.get("base_files", {}))

    env = child_env()

    run_git(workspace, ["-c", "core.hooksPath=" + os.devnull, "init", "-q", "--template="], env)
    run_git(workspace, ["add", "-A"], env)
    run_git(
        workspace,
        [
            "-c", "user.email=dev@example.com",
            "-c", "user.name=dev",
            "-c", "core.hooksPath=" + os.devnull,
            "commit", "-q", "-m", "comment-guidance fixture baseline: {}".format(case_id),
        ],
        env,
    )
    commit_sha = subprocess.run(
        ["git", "-C", workspace, "rev-parse", "HEAD"],
        check=True, capture_output=True, text=True, env=env,
    ).stdout.strip()

    git_dir = os.path.join(workspace, ".git")
    with open(os.path.join(git_dir, "comment_guidance_baseline"), "w", encoding="utf-8") as f:
        f.write(commit_sha + "\n")

    write_files(workspace, case_data.get("input_overrides", {}))

    capture = case_data.get("capture_failure_log")
    if capture:
        command = list(capture["command"])
        # The fixture names the interpreter generically; run it with the interpreter that is
        # building the fixture so hosts without a `python3` alias (Windows) still work.
        if command and command[0] in ("python3", "python"):
            command[0] = sys.executable
        output_path = validate_dest(workspace, capture["output_path"])
        result = subprocess.run(
            command,
            cwd=workspace,
            capture_output=True,
            text=True,
            env=env,
        )
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result.stdout)
            f.write(result.stderr)
            f.write("EXIT {}\n".format(result.returncode))

    return 0


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--workspace", required=True)
    args = parser.parse_args(argv)
    try:
        return build(args.case, args.workspace)
    except ValueError as exc:
        return fail(str(exc))
    except subprocess.CalledProcessError as exc:
        return fail("command failed: {} ({})".format(exc.cmd, exc.stderr))
    except OSError as exc:
        return fail("command could not run: {}".format(exc))


if __name__ == "__main__":
    sys.exit(main())
