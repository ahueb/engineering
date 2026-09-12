#!/usr/bin/env bash
# Scenario 3: high code coverage, a clean SAST scan, and good average latency, but no
# critical-journey semantic correctness, authorization-abuse, tail-latency, or migration
# rollback evidence.
set -euo pipefail
DIR="$(dirname "${BASH_SOURCE[0]}")"
bash "$DIR/../fixture-service.sh" --no-commit

cat > docs/coverage-summary.md <<'MD'
# Coverage summary
Line coverage: 95.2%. All lines in `src/server.js` are exercised by `npm test`.
Tests assert response shape only (e.g. `{ ok: true }`); they do not assert business outcomes,
authorization rules, or query correctness against real data.
MD

cat > docs/sast-report.md <<'MD'
# SAST scan
Tool: single open-source static analyzer, default ruleset, run once against `src/`.
Findings: 0.
No dependency/SCA scan, no dynamic analysis, and no manual authorization-logic review were run.
MD

cat > docs/perf-report.md <<'MD'
# Load test summary
Average response time under synthetic load: 42ms. p95/p99 and tail-latency behavior under
sustained peak load were not measured.
MD

mkdir -p deploy/migrations
cat > deploy/migrations/0002_add_orders_status.sql <<'SQL'
ALTER TABLE orders ADD COLUMN status TEXT NOT NULL DEFAULT 'pending';
SQL
cat > docs/migration-notes.md <<'MD'
# Migration 0002
Adds a required `status` column with a default. No rollback script is provided, and there is
no record of this migration (or its reversal) having been rehearsed against a copy of
production data.
MD

git init -q && git add -A && git -c user.email=dev@example.com -c user.name=dev commit -qm "orders-api: high coverage, clean SAST, good average latency"
