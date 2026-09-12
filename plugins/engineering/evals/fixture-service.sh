#!/usr/bin/env bash
# Shared scaffold for prr-trigger-* cases: a small but realistic service repository so the
# readiness question has something to review. Runs in the empty eval workspace (cwd) as the
# eval author, before Claude starts. Invoked from each case's fixture.sh with --scaffold.
set -euo pipefail
mkdir -p src tests .github/workflows deploy docs
cat > package.json <<'JSON'
{ "name": "orders-api", "version": "1.4.0", "private": true,
  "scripts": { "test": "node --test tests/", "start": "node src/server.js", "lint": "eslint src" },
  "dependencies": { "express": "4.19.2", "pg": "8.11.5" },
  "devDependencies": { "eslint": "9.9.0" } }
JSON
printf '{ "lockfileVersion": 3, "name": "orders-api", "packages": {} }\n' > package-lock.json
cat > src/server.js <<'JS'
const express = require('express');
const { Pool } = require('pg');
const app = express();
const pool = new Pool({ connectionString: process.env.DATABASE_URL });
app.get('/healthz', (_req, res) => res.json({ ok: true }));
app.get('/orders/:id', async (req, res) => {
  const { rows } = await pool.query('SELECT * FROM orders WHERE id = $1', [req.params.id]);
  if (!rows.length) return res.status(404).end();
  res.json(rows[0]);
});
app.post('/orders', express.json(), async (req, res) => {
  const { rows } = await pool.query('INSERT INTO orders(total) VALUES ($1) RETURNING *', [req.body.total]);
  res.status(201).json(rows[0]);
});
module.exports = app;
if (require.main === module) app.listen(process.env.PORT || 8080);
JS
cat > tests/orders.test.js <<'JS'
const test = require('node:test');
const assert = require('node:assert');
test('healthz shape', () => { assert.deepStrictEqual({ ok: true }, { ok: true }); });
test('order total is numeric', () => { assert.strictEqual(typeof 12.5, 'number'); });
JS
cat > .github/workflows/ci.yml <<'YML'
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - run: npm ci
      - run: npm test
YML
cat > deploy/deployment.yaml <<'YML'
apiVersion: apps/v1
kind: Deployment
metadata: { name: orders-api }
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: orders-api
          image: registry.example.com/orders-api:latest
          readinessProbe: { httpGet: { path: /healthz, port: 8080 } }
YML
cat > docs/runbook.md <<'MD'
# Orders API runbook
- Restart: `kubectl rollout restart deployment/orders-api`
- Rollback: `kubectl rollout undo deployment/orders-api`
- Backups: nightly pg_dump to S3 (restore procedure: TODO)
MD
cat > README.md <<'MD'
# orders-api
Order service for the checkout flow. Owner: payments team. Alerts: none configured yet.
MD
git init -q && git add -A && git -c user.email=dev@example.com -c user.name=dev commit -qm "orders-api 1.4.0 release candidate"
