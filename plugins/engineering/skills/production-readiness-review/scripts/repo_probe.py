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
from pathlib import Path
from typing import Iterable

SCHEMA_VERSION = "1.0"
DEFAULT_MAX_FILES = 50000
MAX_TEXT_BYTES = 1_000_000
MAX_PATHS_PER_SIGNAL = 80
MAX_CONTENT_PATHS_PER_SIGNAL = 30

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
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return 127, "", str(exc)


def git_info(start: Path) -> tuple[Path, dict]:
    if not shutil.which("git"):
        return start, {"available": False, "is_repo": False}

    code, out, _ = safe_run(["git", "-C", str(start), "rev-parse", "--show-toplevel"], start)
    if code != 0 or not out:
        return start, {"available": True, "is_repo": False}

    root = Path(out).resolve()
    _, head, _ = safe_run(["git", "rev-parse", "HEAD"], root)
    _, branch, _ = safe_run(["git", "branch", "--show-current"], root)
    status_code, status, _ = safe_run(["git", "status", "--porcelain=v1", "--untracked-files=normal"], root)

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


def is_sensitive(path: Path) -> bool:
    if SENSITIVE_BASENAME_RE.match(path.name):
        return True
    lowered = {part.lower() for part in path.parts}
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


def should_scan_text(path: Path) -> bool:
    if is_sensitive(path) or path.is_symlink():
        return False
    if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {"Dockerfile", "Containerfile", "Makefile", "Jenkinsfile"}:
        return False
    try:
        return path.stat().st_size <= MAX_TEXT_BYTES
    except OSError:
        return False


def iter_files(root: Path, max_files: int) -> tuple[list[Path], bool, list[str]]:
    files: list[Path] = []
    warnings: list[str] = []
    capped = False

    def onerror(exc: OSError) -> None:
        warnings.append(f"scan error: {exc.filename or '<unknown>'}: {exc.strerror or exc}")

    for dirpath, dirnames, filenames in os.walk(root, topdown=True, followlinks=False, onerror=onerror):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in EXCLUDED_DIRS and not (Path(dirpath) / d).is_symlink()
        )
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if path.is_symlink():
                continue
            files.append(path)
            if len(files) >= max_files:
                capped = True
                return files, capped, warnings
    return files, capped, warnings


def add_limited(bucket: dict[str, list[str]], key: str, value: str, limit: int) -> None:
    values = bucket.setdefault(key, [])
    if len(values) < limit and value not in values:
        values.append(value)


def build_report(start: Path, max_files: int) -> dict:
    root, git = git_info(start)
    files, capped, scan_warnings = iter_files(root, max_files)

    suffix_counts: collections.Counter[str] = collections.Counter()
    signals: dict[str, list[str]] = {}
    content_signals: dict[str, list[str]] = {}
    text_scanned = 0
    unreadable_text = 0

    for path in files:
        rel = relpath(path, root)
        suffix = path.suffix.lower() or "<none>"
        suffix_counts[suffix] += 1

        if not is_sensitive(path):
            for category in classify_path(rel):
                add_limited(signals, category, rel, MAX_PATHS_PER_SIGNAL)

        if not should_scan_text(path):
            continue
        try:
            data = path.read_bytes()
            text = data.decode("utf-8", errors="ignore")
            text_scanned += 1
        except OSError:
            unreadable_text += 1
            continue

        for category, pattern in CONTENT_PATTERNS.items():
            if pattern.search(text):
                add_limited(content_signals, category, rel, MAX_CONTENT_PATHS_PER_SIGNAL)

    for values in signals.values():
        values.sort()
    for values in content_signals.values():
        values.sort()

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

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at_utc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "root": str(root),
        "git": git,
        "scan": {
            "file_count": len(files),
            "capped": capped,
            "max_files": max_files,
            "text_files_scanned_for_signal_presence": text_scanned,
            "suffix_counts": dict(suffix_counts.most_common(40)),
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
    return parser.parse_args(list(argv))


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if args.max_files < 1:
        print("error: --max-files must be >= 1", file=sys.stderr)
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
        report = build_report(start, args.max_files)
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
