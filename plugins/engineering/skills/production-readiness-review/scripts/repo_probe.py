#!/usr/bin/env python3
"""Read-only repository discovery for the production-readiness-review skill.

The probe intentionally emits only metadata and relative paths. It never emits
file contents, environment-variable values, credential material, or network data.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Iterable

SCHEMA_VERSION = "2.0"
DEFAULT_MAX_FILES = 50000
MAX_TEXT_BYTES = 1_000_000
MAX_PATHS_PER_SIGNAL = 80
MAX_CONTENT_PATHS_PER_SIGNAL = 30
DEFAULT_MAX_SECONDS = 20.0
DEFAULT_MAX_TEXT_BUDGET_BYTES = 200_000_000

EXCLUDED_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules",
    "vendor", "target", "dist", "build", "out", ".next", ".nuxt",
    ".cache", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "coverage", ".coverage", "tmp", "temp", ".terraform", ".gradle",
    ".idea", ".vscode", ".tox", ".nox", ".pnpm-store", ".yarn",
    ".aws", ".ssh", "secrets", "secret", "credentials",
}

SENSITIVE_BASENAME_RE = re.compile(
    r"^(?:\.env(?:\..*)?|id_(?:rsa|dsa|ecdsa|ed25519)|credentials(?:\..*)?|"
    r".*\.(?:pem|key|p12|pfx|jks|keystore))$",
    re.IGNORECASE,
)

TEXT_SUFFIXES = {
    ".md", ".rst", ".txt", ".yaml", ".yml", ".json", ".toml", ".ini",
    ".cfg", ".conf", ".xml", ".properties", ".gradle", ".sh", ".bash",
    ".zsh", ".ps1", ".py", ".js", ".jsx", ".ts", ".tsx", ".mjs",
    ".cjs", ".rs", ".go", ".java", ".kt", ".kts", ".cs", ".rb",
    ".php", ".tf", ".hcl", ".sql", ".proto", ".graphql", ".gql",
}

CONTENT_PATTERNS = {
    "rollback_or_reversion": re.compile(r"\b(?:rollback|roll\s*back|revert(?:ion)?)\b", re.I),
    "backup_restore": re.compile(r"\b(?:backup|restore|recovery)\b", re.I),
    "rto_rpo": re.compile(r"\b(?:RTO|RPO|recovery time objective|recovery point objective)\b", re.I),
    "slo_sli": re.compile(r"\b(?:SLO|SLI|service level objective|service level indicator)\b", re.I),
    "oncall_incident": re.compile(r"\b(?:on[- ]?call|incident response|pager|escalation)\b", re.I),
    "runbook_playbook": re.compile(r"\b(?:runbook|playbook|operational procedure)\b", re.I),
    "load_performance": re.compile(r"\b(?:load test|stress test|soak test|k6|locust|jmeter|wrk|vegeta)\b", re.I),
    "progressive_delivery": re.compile(r"\b(?:canary|blue[- ]green|progressive delivery|feature flag|kill switch)\b", re.I),
    "observability": re.compile(r"\b(?:opentelemetry|otel|prometheus|grafana|datadog|new relic|sentry|tracing)\b", re.I),
    "threat_security": re.compile(r"\b(?:threat model|abuse case|penetration test|pentest|codeql|semgrep|trivy|snyk)\b", re.I),
    "supply_chain": re.compile(r"\b(?:SBOM|software bill of materials|SLSA|provenance|attestation|cosign|sigstore)\b", re.I),
    "accessibility": re.compile(r"\b(?:WCAG|accessibility|axe-core|pa11y)\b", re.I),
    "ai_ml_eval": re.compile(r"\b(?:model card|eval(?:uation)? set|drift|prompt injection|MLflow|model registry)\b", re.I),
    "data_quality": re.compile(r"\b(?:data lineage|data contract|reconciliation|backfill|schema migration|freshness)\b", re.I),
    "signed_release": re.compile(r"\b(?:cosign|sigstore|attest\w*|gpg --sign)\b", re.I),
}

CI_PERMISSIONS_RE = re.compile(r"^\s*permissions:", re.M)

DEPENDENCY_AUTOMATION_NAMES = {
    "dependabot.yml", "dependabot.yaml", "renovate.json", "renovate.json5",
    ".renovaterc", ".renovaterc.json",
}

MANIFEST_NAMES = {
    "package.json", "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
    "Pipfile", "Cargo.toml", "go.mod", "pom.xml", "build.gradle", "build.gradle.kts",
    "settings.gradle", "settings.gradle.kts", "composer.json", "Gemfile", "mix.exs",
    "deno.json", "deno.jsonc", "bunfig.toml", "Makefile", "CMakeLists.txt",
}
LOCKFILE_NAMES = {
    "package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb",
    "bun.lock", "uv.lock", "poetry.lock", "Pipfile.lock", "Cargo.lock", "go.sum",
    "composer.lock", "Gemfile.lock", "mix.lock",
}
CI_NAMES = {
    ".gitlab-ci.yml", ".gitlab-ci.yaml", "Jenkinsfile", "azure-pipelines.yml",
    "azure-pipelines.yaml", "bitbucket-pipelines.yml", "bitbucket-pipelines.yaml",
    "appveyor.yml", "appveyor.yaml", "buildkite.yml", "buildkite.yaml",
}


def safe_run(args: list[str], cwd: Path, timeout: float = 5.0) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"},
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)


# Config-driven execution points are neutralised so a hostile .git/config in a cloned repo
# cannot run commands through the probe (core.fsmonitor, hooks).
GIT_HARDENING = ["-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null"]


def git_info(start: Path) -> tuple[Path, dict]:
    """Return (toplevel, metadata). The toplevel is reported, not scanned: the scan root is
    always the path the caller supplied."""
    if not shutil.which("git"):
        return start, {"available": False, "is_repo": False}

    code, out, _ = safe_run(["git", *GIT_HARDENING, "-C", str(start), "rev-parse", "--show-toplevel"], start)
    if code != 0 or not out:
        return start, {"available": True, "is_repo": False}

    root = Path(out).resolve()
    _, head, _ = safe_run(["git", *GIT_HARDENING, "rev-parse", "HEAD"], root)
    _, branch, _ = safe_run(["git", *GIT_HARDENING, "branch", "--show-current"], root)
    status_code, status, _ = safe_run(["git", *GIT_HARDENING, "status", "--porcelain=v1", "--untracked-files=normal"], root)

    counts: collections.Counter[str] = collections.Counter()
    dirty = False
    if status_code == 0:
        for line in status.splitlines():
            if len(line) >= 2:
                code2 = line[:2]
                counts[code2] += 1
                dirty = True

    return root, {
        "available": True,
        "is_repo": True,
        "toplevel": str(root),
        "head": head or None,
        "branch": branch or None,
        "dirty": dirty,
        "status_entry_count": sum(counts.values()),
        "status_code_counts": dict(sorted(counts.items())),
    }


def relpath(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def is_sensitive(path: Path, root: Path | None = None) -> bool:
    """Sensitivity is judged on the path relative to the scan root, so a repository that
    happens to live under a directory named e.g. `credentials` is not blanked out."""
    if SENSITIVE_BASENAME_RE.match(path.name):
        return True
    parts = path.parts
    if root is not None:
        try:
            parts = path.relative_to(root).parts
        except ValueError:
            pass
    lowered = {part.lower() for part in parts}
    return bool(lowered & {".aws", ".ssh", "secrets", "secret", "credentials"})


def looks_like_test(rel: str, name: str) -> bool:
    parts = {p.lower() for p in Path(rel).parts[:-1]}
    lower = name.lower()
    return (
        bool(parts & {"test", "tests", "spec", "specs", "e2e", "integration", "integration-tests"})
        or lower.startswith("test_")
        or re.search(r"(?:_test|\.test|\.spec)\.[^.]+$", lower) is not None
    )


def classify_path(rel: str) -> set[str]:
    p = Path(rel)
    name = p.name
    lower = rel.lower()
    nlower = name.lower()
    dir_parts = {part.lower() for part in p.parts[:-1]}
    categories: set[str] = set()

    if name in MANIFEST_NAMES or nlower.startswith("requirements") and nlower.endswith(".txt"):
        categories.add("manifests")
    if name in LOCKFILE_NAMES:
        categories.add("lockfiles")
    if name in CI_NAMES or lower.startswith(".github/workflows/") or lower == ".circleci/config.yml" or lower == ".circleci/config.yaml":
        categories.add("ci")
    if looks_like_test(rel, name):
        categories.add("tests")
    if nlower in {"security.md", "dependabot.yml", "dependabot.yaml", "renovate.json", "renovate.json5"} or any(k in lower for k in ("codeql", "semgrep", "trivy", "snyk", "dependabot", "renovate")):
        categories.add("security")
    if nlower in {"dockerfile", "containerfile"} or nlower.startswith("docker-compose") or nlower.startswith("compose."):
        categories.add("containers")
    if dir_parts & {"k8s", "kubernetes", "helm", "kustomize", "kustomization"} or nlower in {"chart.yaml", "kustomization.yaml"}:
        categories.add("orchestration")
    if p.suffix.lower() in {".tf", ".hcl"} or any(k in lower for k in ("terraform", "pulumi", "cloudformation", "ansible", "bicep", "serverless")):
        categories.add("infrastructure")
    if dir_parts & {"migration", "migrations", "alembic", "flyway", "liquibase"} or re.match(r"^v\d+.*\.sql$", nlower):
        categories.add("migrations")
    if any(k in lower for k in ("prometheus", "grafana", "opentelemetry", "otel", "alertmanager", "datadog", "newrelic", "new-relic", "sentry")):
        categories.add("observability")
    if dir_parts & {"ops", "operations", "runbook", "runbooks", "playbook", "playbooks", "incidents"} or any(k in lower for k in ("runbook", "playbook", "oncall", "on-call", "incident", "postmortem", "disaster-recovery", "disaster_recovery", "restore", "backup")):
        categories.add("runbooks_ops")
    if any(k in lower for k in ("changelog", "release", "rollout", "rollback", "deploy", "deployment")):
        categories.add("release")
    if any(k in lower for k in ("openapi", "swagger", ".proto", "graphql", "schema.gql")):
        categories.add("api_contracts")
    if nlower.startswith("readme") or lower.startswith("docs/") or "/docs/" in lower:
        categories.add("docs")
    if nlower.startswith("license") or nlower.startswith("copying") or nlower.startswith("notice"):
        categories.add("licenses")
    if any(k in lower for k in ("wcag", "accessibility", "axe", "pa11y", "lighthouse")):
        categories.add("accessibility")
    if any(k in lower for k in ("mlflow", "model-card", "model_card", "model-eval", "model_eval", "prompt", "langchain", "llamaindex")):
        categories.add("ai_ml")
    if any(k in lower for k in ("dbt", "lineage", "data-contract", "data_contract", "airflow", "dagster", "prefect")):
        categories.add("data")

    return categories


def should_scan_text(path: Path, root: Path | None = None) -> bool:
    if is_sensitive(path, root) or path.is_symlink():
        return False
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"Dockerfile", "Containerfile", "Makefile", "Jenkinsfile"}:
        return False
    try:
        return path.stat().st_size <= MAX_TEXT_BYTES
    except OSError:
        return False


def iter_files(root: Path, max_files: int, deadline: float) -> tuple[list[Path], bool, bool, list[str]]:
    files: list[Path] = []
    warnings: list[str] = []
    capped = False
    time_exhausted = False

    def onerror(exc: OSError) -> None:
        warnings.append(f"scan error: {exc.filename or '<unknown>'}: {exc.strerror or exc}")

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False, onerror=onerror):
        if time.monotonic() >= deadline:
            time_exhausted = True
            return files, capped, time_exhausted, warnings
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in EXCLUDED_DIRS and d != ".git" and not (Path(dirpath) / d).is_symlink()
        )
        for filename in sorted(filenames):
            if filename == ".git":
                # Skip submodule gitlink files so submodules are not counted.
                continue
            path = Path(dirpath) / filename
            if path.is_symlink():
                continue
            files.append(path)
            if len(files) >= max_files:
                capped = True
                return files, capped, time_exhausted, warnings
            if time.monotonic() >= deadline:
                time_exhausted = True
                return files, capped, time_exhausted, warnings
    return files, capped, time_exhausted, warnings


def add_limited(bucket: dict[str, list[str]], key: str, value: str, limit: int) -> None:
    values = bucket.setdefault(key, [])
    if len(values) < limit and value not in values:
        values.append(value)


def build_report(start: Path, max_files: int, max_seconds: float, max_text_bytes: int) -> dict:
    toplevel, git = git_info(start)
    root = start  # scan only what the caller asked for, never the enclosing repository
    start_time = time.monotonic()  # the budget covers the scan, not the git metadata calls
    deadline = start_time + max_seconds
    files, capped, time_budget_exhausted, scan_warnings = iter_files(root, max_files, deadline)

    suffix_counts: collections.Counter[str] = collections.Counter()
    signals: dict[str, list[str]] = {}
    content_signals: dict[str, list[str]] = {}
    text_scanned = 0
    unreadable_text = 0
    text_bytes_total = 0
    text_budget_exhausted = False
    text_files_skipped_oversize = 0
    files_classified = 0

    for path in files:
        if not time_budget_exhausted and time.monotonic() >= deadline:
            time_budget_exhausted = True
        if time_budget_exhausted:
            break
        files_classified += 1

        rel = relpath(path, root)
        suffix = path.suffix.lower() or "<none>"
        suffix_counts[suffix] += 1
        lower = rel.lower()
        nlower = path.name.lower()

        if not is_sensitive(path, root):
            for category in classify_path(rel):
                add_limited(signals, category, rel, MAX_PATHS_PER_SIGNAL)
            if nlower == "security.md" or lower.endswith(".well-known/security.txt"):
                add_limited(content_signals, "vuln_reporting", rel, MAX_CONTENT_PATHS_PER_SIGNAL)
            if nlower in DEPENDENCY_AUTOMATION_NAMES:
                add_limited(content_signals, "dependency_automation", rel, MAX_CONTENT_PATHS_PER_SIGNAL)

        if text_budget_exhausted or not should_scan_text(path, root):
            continue

        try:
            size = path.stat().st_size
        except OSError:
            size = 0
        if size > max_text_bytes:
            text_files_skipped_oversize += 1  # one oversized file does not end scanning for the rest
            continue
        if text_bytes_total + size > max_text_bytes:
            text_budget_exhausted = True  # budget genuinely consumed; content scanning stops, classification continues
            continue

        try:
            data = path.read_bytes()
            text = data.decode("utf-8", errors="ignore")
            text_scanned += 1
            text_bytes_total += size
        except OSError:
            unreadable_text += 1
            continue

        for category, pattern in CONTENT_PATTERNS.items():
            if pattern.search(text):
                add_limited(content_signals, category, rel, MAX_CONTENT_PATHS_PER_SIGNAL)
        if lower.startswith(".github/workflows/") and CI_PERMISSIONS_RE.search(text):
            add_limited(content_signals, "ci_permissions", rel, MAX_CONTENT_PATHS_PER_SIGNAL)

    for values in signals.values():
        values.sort()
    for values in content_signals.values():
        values.sort()

    elapsed_seconds = round(time.monotonic() - start_time, 3)

    limitations = [
        "Discovery signals are heuristics and are not readiness evidence until files are inspected and claims are corroborated.",
        "The probe does not contact external systems, inspect production configuration, or execute builds/tests.",
        "The probe does not emit file contents, environment-variable values, or credential material.",
        "Common vendor/build/cache directories are excluded to reduce noise.",
    ]
    if capped:
        limitations.append(f"File scan stopped at max_files={max_files}; results are incomplete.")
    if unreadable_text:
        limitations.append(f"{unreadable_text} candidate text files could not be read.")
    if scan_warnings:
        limitations.append("Some directories/files could not be scanned; see warnings.")
    if time_budget_exhausted:
        limitations.append(
            f"Scan stopped after max_seconds={max_seconds}; only {files_classified} of {len(files)} enumerated files were classified."
        )
    if git.get("is_repo") and toplevel != root:
        limitations.append(f"Scan root {root} is inside repository {toplevel}; files outside the scan root were not inspected.")
    if text_files_skipped_oversize:
        limitations.append(f"{text_files_skipped_oversize} text files larger than max_text_bytes={max_text_bytes} were not content-scanned.")
    if text_budget_exhausted:
        limitations.append(f"Text content scanning stopped at max_text_bytes={max_text_bytes}; content signals are incomplete.")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "root": str(root),
        "git": git,
        "scan": {
            "file_count": len(files),
            "files_classified": files_classified,
            "capped": capped,
            "max_files": max_files,
            "text_files_scanned_for_signal_presence": text_scanned,
            "suffix_counts": dict(suffix_counts.most_common(40)),
            "max_seconds": max_seconds,
            "elapsed_seconds": elapsed_seconds,
            "time_budget_exhausted": time_budget_exhausted,
            "max_text_bytes": max_text_bytes,
            "text_budget_exhausted": text_budget_exhausted,
            "text_files_skipped_oversize": text_files_skipped_oversize,
        },
        "signals": dict(sorted(signals.items())),
        "content_signal_files": dict(sorted(content_signals.items())),
        "warnings": scan_warnings[:20],
        "limitations": limitations,
    }


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Emit read-only repository discovery metadata as JSON for production-readiness review."
    )
    parser.add_argument("root", nargs="?", default=".", help="Repository path or a path inside it (default: current directory).")
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES, help=f"Maximum files to enumerate (default: {DEFAULT_MAX_FILES}).")
    parser.add_argument("--max-seconds", type=float, default=DEFAULT_MAX_SECONDS, help=f"Maximum wall-clock seconds to spend scanning (default: {DEFAULT_MAX_SECONDS}).")
    parser.add_argument("--max-text-bytes", type=int, default=DEFAULT_MAX_TEXT_BUDGET_BYTES, help=f"Maximum total bytes of text content to scan for signals (default: {DEFAULT_MAX_TEXT_BUDGET_BYTES}).")
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.max_files < 1:
        print("error: --max-files must be >= 1", file=sys.stderr)
        return 2
    if args.max_seconds < 0 or args.max_text_bytes < 0:
        print("error: --max-seconds and --max-text-bytes must be >= 0", file=sys.stderr)
        return 2

    start = Path(args.root).expanduser()
    try:
        start = start.resolve(strict=True)
    except OSError as exc:
        print(f"error: cannot resolve root: {exc}", file=sys.stderr)
        return 2
    if not start.is_dir():
        print(f"error: root is not a directory: {start}", file=sys.stderr)
        return 2

    try:
        os.listdir(start)
    except OSError as exc:
        print(f"error: cannot list root: {exc}", file=sys.stderr)
        return 3

    try:
        report = build_report(start, args.max_files, args.max_seconds, args.max_text_bytes)
        json.dump(report, sys.stdout, indent=2, sort_keys=False)
        sys.stdout.write("\n")
        return 0
    except KeyboardInterrupt:
        print("error: interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # Defensive boundary: fail closed with no partial secret-bearing dump.
        print(f"error: probe failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
