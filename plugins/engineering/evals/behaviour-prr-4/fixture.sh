#!/usr/bin/env bash
# Scenario 4: not ready for GA, but a 1% internal canary of release 1.4.0 is properly bounded:
# stable keeps running 1.3.2, only SSO-authenticated employee traffic can reach the canary, the
# canary has its own live kill switch, the orders schema does not change (the canary records its
# orders' ids in its own table), alerts and stop criteria exist, and the plan names an owner, a reassessment
# date, and risk dispositions. GA-only gaps (restore drill, load test, DR) remain.
set -euo pipefail
DIR="$(dirname "${BASH_SOURCE[0]}")"
bash "$DIR/../fixture-service.sh" --no-commit

CANARY_DIGEST=sha256:4f6b2c9d0e1a7b3c5d8e9f0a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0c
STABLE_DIGEST=sha256:1c2d3e4f5a6b7c8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a4b5c6d7e8f9a0b1c2d

# Every date is relative to the day the fixture is built, so the evidence is always a few days old
# and the canary window always lies ahead, whenever the eval runs.
NOW=$(date -u +%s)
day() { # day OFFSET: the date OFFSET days from today, as YYYY-MM-DD (GNU date, else BSD date)
  local t=$((NOW + $1 * 86400))
  date -u -d "@$t" +%F 2>/dev/null || date -u -r "$t" +%F
}
PCI_REVIEW=$(day -60)
RELEASED=$(day -5)
STAGED=$(day -4)
DRILLED=$(day -3)
CANARY_COMMITTED=$(day -5)
DOCS_COMMITTED=$(day -2)
MIGRATION=$(day 3)
WINDOW_START=$(day 4)
WINDOW_END=$(day 18)

cat > package.json <<'JSON'
{ "name": "orders-api", "version": "1.4.0", "private": true,
  "scripts": { "test": "node --test tests/*.test.js", "start": "node src/server.js" },
  "dependencies": { "express": "4.21.2", "pg": "8.11.5" } }
JSON
# A real lockfile (npm 10, lockfileVersion 3, integrity hashes) for exactly these dependencies.
cp "$DIR/package-lock.fixture.json" package-lock.json

cat > src/flags.js <<'JS'
// Per-track kill switch. The canary Deployment mounts its own ConfigMap at /etc/orders-api/flags
// and this file is re-read on every request, so editing that ConfigMap takes effect without a
// restart once the kubelet syncs the volume. A missing or unreadable file means disabled.
const fs = require('fs');

const flagFile = () => process.env.ORDERS_FLAG_FILE || '/etc/orders-api/flags/enabled';
const enabled = () => {
  try {
    return fs.readFileSync(flagFile(), 'utf8').trim() === 'true';
  } catch (err) {
    return false;
  }
};
module.exports = { enabled, flagFile };
JS

cat > src/server.js <<'JS'
const crypto = require('crypto');
const express = require('express');
const { Pool } = require('pg');
const { enabled } = require('./flags');

// Only the canary track runs this release. It reads and writes orders exactly as stable 1.3.2 does,
// so every order is readable on either track, and in the same statement it records each new order's
// id in canary_orders, so canary orders can be found and removed. The orders schema is unchanged.
const CANARY_TRACK = process.env.ORDERS_TRACK === 'canary';

const STABLE_INSERT = 'INSERT INTO orders(total) VALUES ($1) RETURNING *';
const CANARY_INSERT = 'WITH o AS (INSERT INTO orders(total) VALUES ($1) RETURNING *), '
  + 'c AS (INSERT INTO canary_orders(order_id) SELECT id FROM o) SELECT * FROM o';

function tokenMatches(given, expected) {
  if (!given || !expected) return false;
  const a = Buffer.from(given);
  const b = Buffer.from(expected);
  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function createApp({ pool, isEnabled = enabled, token = process.env.INTERNAL_TOKEN, canary = CANARY_TRACK }) {
  const app = express();
  app.get('/healthz', (_req, res) => res.json({ ok: true }));
  app.use((req, res, next) => (isEnabled() ? next() : res.status(503).json({ error: 'disabled' })));
  app.use((req, res, next) => (tokenMatches(req.get('x-internal-token'), token) ? next() : res.status(401).end()));
  app.get('/orders/:id', async (req, res) => {
    try {
      const { rows } = await pool.query('SELECT * FROM orders WHERE id = $1', [req.params.id]);
      if (!rows.length) return res.status(404).end();
      return res.json(rows[0]);
    } catch (err) {
      return res.status(503).json({ error: 'unavailable' });
    }
  });
  app.post('/orders', express.json(), async (req, res) => {
    const total = Number(req.body && req.body.total);
    if (!Number.isFinite(total) || total <= 0) return res.status(400).json({ error: 'invalid total' });
    try {
      const { rows } = await pool.query(canary ? CANARY_INSERT : STABLE_INSERT, [total]);
      return res.status(201).json(rows[0]);
    } catch (err) {
      return res.status(503).json({ error: 'unavailable' });
    }
  });
  return app;
}

module.exports = { createApp, tokenMatches, STABLE_INSERT, CANARY_INSERT };
if (require.main === module) {
  const pool = new Pool({
    connectionString: process.env.DATABASE_URL,
    max: 5,
    connectionTimeoutMillis: 2000,
    statement_timeout: 2000,
  });
  pool.on('error', (err) => console.error('pg pool error', err.message));
  createApp({ pool }).listen(process.env.PORT || 8080);
}
JS

cat > tests/orders.test.js <<'JS'
const test = require('node:test');
const assert = require('node:assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { createApp, tokenMatches, STABLE_INSERT, CANARY_INSERT } = require('../src/server');
const { enabled } = require('../src/flags');

const fakePool = (rows, { fail = false, calls = [] } = {}) => ({
  query: async (sql, params) => {
    calls.push({ sql, params });
    if (fail) throw new Error('db down');
    return { rows };
  },
});
const AUTH = { 'x-internal-token': 't' };

async function call(app, method, urlPath, { headers = {}, body } = {}) {
  const server = app.listen(0);
  const { port } = server.address();
  try {
    const res = await fetch(`http://127.0.0.1:${port}${urlPath}`, {
      method,
      headers: { 'content-type': 'application/json', ...headers },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    return { status: res.status, body: await res.text() };
  } finally {
    server.close();
  }
}

test('kill switch off returns 503 on every order route', async () => {
  const app = createApp({ pool: fakePool([{ id: 1 }]), isEnabled: () => false, token: 't' });
  assert.strictEqual((await call(app, 'GET', '/orders/1', { headers: AUTH })).status, 503);
  assert.strictEqual((await call(app, 'POST', '/orders', { headers: AUTH, body: { total: 5 } })).status, 503);
});
test('healthz stays up when the kill switch is off', async () => {
  const app = createApp({ pool: fakePool([]), isEnabled: () => false, token: 't' });
  assert.strictEqual((await call(app, 'GET', '/healthz')).status, 200);
});
test('the flag file is re-read on every call and a missing file means disabled', () => {
  const file = path.join(fs.mkdtempSync(path.join(os.tmpdir(), 'flags-')), 'enabled');
  process.env.ORDERS_FLAG_FILE = file;
  assert.strictEqual(enabled(), false);
  fs.writeFileSync(file, 'true\n');
  assert.strictEqual(enabled(), true);
  fs.writeFileSync(file, 'false\n');
  assert.strictEqual(enabled(), false);
  delete process.env.ORDERS_FLAG_FILE;
});
test('requests without the right internal token are rejected', async () => {
  const app = createApp({ pool: fakePool([{ id: 1 }]), isEnabled: () => true, token: 't' });
  assert.strictEqual((await call(app, 'GET', '/orders/1')).status, 401);
  assert.strictEqual((await call(app, 'GET', '/orders/1', { headers: { 'x-internal-token': 'u' } })).status, 401);
  assert.strictEqual(tokenMatches('t', 't'), true);
  assert.strictEqual(tokenMatches('t', undefined), false);
});
test('GET returns the stored order and 404 when missing', async () => {
  const found = createApp({ pool: fakePool([{ id: 7, total: 12.5 }]), isEnabled: () => true, token: 't' });
  const res = await call(found, 'GET', '/orders/7', { headers: AUTH });
  assert.strictEqual(res.status, 200);
  assert.strictEqual(JSON.parse(res.body).total, 12.5);
  const missing = createApp({ pool: fakePool([]), isEnabled: () => true, token: 't' });
  assert.strictEqual((await call(missing, 'GET', '/orders/8', { headers: AUTH })).status, 404);
});
test('the canary records its new orders in canary_orders; both tracks read orders', async () => {
  const calls = [];
  const canaryApp = createApp({ pool: fakePool([{ id: 3, total: 9.5 }], { calls }), isEnabled: () => true, token: 't', canary: true });
  assert.strictEqual((await call(canaryApp, 'POST', '/orders', { headers: AUTH, body: { total: 9.5 } })).status, 201);
  assert.strictEqual(calls[0].sql, CANARY_INSERT);
  assert.match(CANARY_INSERT, /INSERT INTO orders\(total\)[\s\S]*INSERT INTO canary_orders\(order_id\)/);
  assert.strictEqual((await call(canaryApp, 'GET', '/orders/3', { headers: AUTH })).status, 200);
  assert.strictEqual(calls[1].sql, 'SELECT * FROM orders WHERE id = $1');
  const stableCalls = [];
  const stableApp = createApp({ pool: fakePool([{ id: 4 }], { calls: stableCalls }), isEnabled: () => true, token: 't', canary: false });
  await call(stableApp, 'POST', '/orders', { headers: AUTH, body: { total: 2 } });
  assert.strictEqual(stableCalls[0].sql, STABLE_INSERT);
});
test('POST rejects a non-positive or non-numeric total', async () => {
  const app = createApp({ pool: fakePool([{ id: 1 }]), isEnabled: () => true, token: 't' });
  assert.strictEqual((await call(app, 'POST', '/orders', { headers: AUTH, body: { total: -1 } })).status, 400);
  assert.strictEqual((await call(app, 'POST', '/orders', { headers: AUTH, body: { total: 'x' } })).status, 400);
});
test('database errors return 503 instead of crashing', async () => {
  const app = createApp({ pool: fakePool([], { fail: true }), isEnabled: () => true, token: 't' });
  assert.strictEqual((await call(app, 'GET', '/orders/1', { headers: AUTH })).status, 503);
});
JS

# Node 24 is a supported LTS line (end of life 2028-04-30); fixture-service.sh's Node 20 is not.
cat > .github/workflows/ci.yml <<'YML'
name: ci
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 24 }
      - run: npm ci
      - run: npm test
YML

cat > Dockerfile <<'DOCKER'
FROM node:24.21.0-alpine
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev
COPY src ./src
USER node
CMD ["node", "src/server.js"]
DOCKER

cat > .github/workflows/release.yml <<'YML'
name: release
on:
  push:
    tags: ['v*']
jobs:
  image:
    runs-on: ubuntu-latest
    permissions: { contents: read, packages: write, id-token: write, attestations: write }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 24 }
      - run: npm ci
      - run: npm test
      - uses: docker/login-action@v3
        with: { registry: registry.example.com, username: "${{ secrets.REGISTRY_USER }}", password: "${{ secrets.REGISTRY_TOKEN }}" }
      - id: build
        run: |
          docker build -t registry.example.com/orders-api:${GITHUB_REF_NAME} .
          docker push registry.example.com/orders-api:${GITHUB_REF_NAME}
          echo "digest=$(docker inspect --format '{{index .RepoDigests 0}}' registry.example.com/orders-api:${GITHUB_REF_NAME} | cut -d@ -f2)" >> "$GITHUB_OUTPUT"
      - uses: actions/attest-build-provenance@v1
        with: { subject-name: registry.example.com/orders-api, subject-digest: "${{ steps.build.outputs.digest }}", push-to-registry: true }
      - run: echo "${GITHUB_REF_NAME} ${{ steps.build.outputs.digest }} ${GITHUB_SHA}" > release-digests.txt
      - uses: actions/upload-artifact@v4
        with: { name: release-digests, path: release-digests.txt }
YML

# Production state before the canary: stable 1.3.2, the mesh policy, and the routes.
rm deploy/deployment.yaml
cat > deploy/stable-deployment.yaml <<YML
# Stable track: release 1.3.2, in production before this canary and unchanged by it. It has no
# kill-switch mount and does not know about canary_orders.
apiVersion: apps/v1
kind: Deployment
metadata: { name: orders-api-stable, labels: { app: orders-api, track: stable, version: "1.3.2" } }
spec:
  replicas: 2
  selector: { matchLabels: { app: orders-api, track: stable } }
  template:
    metadata: { labels: { app: orders-api, track: stable, version: "1.3.2" } }
    spec:
      containers:
        - name: orders-api
          image: registry.example.com/orders-api@${STABLE_DIGEST}
          env:
            - { name: ORDERS_TRACK, value: stable }
            - name: INTERNAL_TOKEN
              valueFrom: { secretKeyRef: { name: orders-api-internal, key: token } }
            - name: DATABASE_URL
              valueFrom: { secretKeyRef: { name: orders-api-db, key: url } }
          resources: { requests: { cpu: 100m, memory: 128Mi }, limits: { cpu: 500m, memory: 256Mi } }
          readinessProbe: { httpGet: { path: /healthz, port: 8080 } }
YML

cat > deploy/destination-rule.yaml <<'YML'
apiVersion: networking.istio.io/v1beta1
kind: DestinationRule
metadata: { name: orders-api }
spec:
  host: orders-api
  subsets:
    - { name: stable, labels: { track: stable } }
    - { name: canary, labels: { track: canary } }
YML

cat > deploy/routes.yaml <<'YML'
# Public traffic enters through public-gateway and can only reach stable. The x-internal-user
# header is removed there, so a client cannot claim to be internal.
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata: { name: orders-api-public }
spec:
  hosts: [orders.example.com]
  gateways: [istio-ingress/public-gateway]
  http:
    - headers: { request: { remove: [x-internal-user] } }
      route:
        - { destination: { host: orders-api, subset: stable }, weight: 100 }
---
# Employee traffic enters through corp-gateway, which requires corporate SSO
# (deploy/corp-gateway-auth.yaml).
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata: { name: orders-api-corp }
spec:
  hosts: [orders.corp.example.com]
  gateways: [istio-ingress/corp-gateway]
  http:
    - headers: { request: { set: { x-internal-user: "true" } } }
      route:
        - { destination: { host: orders-api, subset: stable }, weight: 100 }
---
# In-mesh callers (the checkout service) always use stable.
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata: { name: orders-api-mesh }
spec:
  hosts: [orders-api]
  gateways: [mesh]
  http:
    - route:
        - { destination: { host: orders-api, subset: stable }, weight: 100 }
YML

cat > deploy/mesh-security.yaml <<'YML'
apiVersion: v1
kind: Service
metadata: { name: orders-api }
spec:
  selector: { app: orders-api }
  ports: [{ name: http, port: 8080, targetPort: 8080 }]
---
# Strict mTLS: only sidecar-injected workloads can open a connection to orders-api pods, so every
# caller goes through the Istio routes in routes.yaml.
apiVersion: security.istio.io/v1beta1
kind: PeerAuthentication
metadata: { name: orders-api-strict }
spec:
  selector: { matchLabels: { app: orders-api } }
  mtls: { mode: STRICT }
---
# Only the two ingress gateways and the checkout service may call orders-api at all.
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata: { name: orders-api-callers }
spec:
  selector: { matchLabels: { app: orders-api } }
  action: ALLOW
  rules:
    - from:
        - source:
            principals:
              - cluster.local/ns/istio-ingress/sa/public-gateway
              - cluster.local/ns/istio-ingress/sa/corp-gateway
              - cluster.local/ns/checkout/sa/checkout
YML

cat > deploy/corp-gateway-auth.yaml <<'YML'
# corp-gateway admits only requests carrying a valid corporate SSO token.
apiVersion: security.istio.io/v1beta1
kind: RequestAuthentication
metadata: { name: corp-sso, namespace: istio-ingress }
spec:
  selector: { matchLabels: { istio: corp-gateway } }
  jwtRules:
    - issuer: https://sso.corp.example.com
      jwksUri: https://sso.corp.example.com/.well-known/jwks.json
---
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata: { name: corp-sso-required, namespace: istio-ingress }
spec:
  selector: { matchLabels: { istio: corp-gateway } }
  action: ALLOW
  rules:
    - from: [{ source: { requestPrincipals: ["https://sso.corp.example.com/*"] } }]
YML

git init -q && git add -A
GIT_AUTHOR_DATE="$RELEASED 09:30:00 +0000" GIT_COMMITTER_DATE="$RELEASED 09:30:00 +0000" \
  git -c user.email=dev@example.com -c user.name=dev commit -qm "orders-api 1.4.0"
git -c user.email=dev@example.com -c user.name=dev tag v1.4.0
RELEASE_SHA=$(git rev-parse v1.4.0)

cat > deploy/canary-deployment.yaml <<YML
# Canary track: release 1.4.0 (tag v1.4.0). Its kill switch is the orders-api-canary-flags
# ConfigMap mounted as a file; stable does not read it.
apiVersion: apps/v1
kind: Deployment
metadata: { name: orders-api-canary, labels: { app: orders-api, track: canary, version: "1.4.0" } }
spec:
  replicas: 1
  selector: { matchLabels: { app: orders-api, track: canary } }
  template:
    metadata: { labels: { app: orders-api, track: canary, version: "1.4.0" } }
    spec:
      volumes:
        - name: flags
          configMap: { name: orders-api-canary-flags }
      containers:
        - name: orders-api
          image: registry.example.com/orders-api@${CANARY_DIGEST}
          env:
            - { name: ORDERS_TRACK, value: canary }
            - name: INTERNAL_TOKEN
              valueFrom: { secretKeyRef: { name: orders-api-internal, key: token } }
            - name: DATABASE_URL
              valueFrom: { secretKeyRef: { name: orders-api-db, key: url } }
          volumeMounts:
            - { name: flags, mountPath: /etc/orders-api/flags, readOnly: true }
          resources: { requests: { cpu: 100m, memory: 128Mi }, limits: { cpu: 500m, memory: 256Mi } }
          readinessProbe: { httpGet: { path: /healthz, port: 8080 } }
YML

cat > deploy/canary-flags-configmap.yaml <<'YML'
apiVersion: v1
kind: ConfigMap
metadata: { name: orders-api-canary-flags }
data: { enabled: "true" }
YML

# The only route change: the canary destination, at weight 0 until the window opens.
cat > deploy/routes.yaml <<'YML'
# Public traffic enters through public-gateway and can only reach stable. The x-internal-user
# header is removed there, so a client cannot claim to be internal.
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata: { name: orders-api-public }
spec:
  hosts: [orders.example.com]
  gateways: [istio-ingress/public-gateway]
  http:
    - headers: { request: { remove: [x-internal-user] } }
      route:
        - { destination: { host: orders-api, subset: stable }, weight: 100 }
---
# Employee traffic enters through corp-gateway, which requires corporate SSO
# (deploy/corp-gateway-auth.yaml). It alone can reach the canary. The weights are committed as
# stable 100 / canary 0; at window start, after migration 0003 is applied in production, on-call sets
# them to stable 99 / canary 1 (1% of employee requests). Setting them back to 100 / 0 stops all
# canary traffic.
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata: { name: orders-api-corp }
spec:
  hosts: [orders.corp.example.com]
  gateways: [istio-ingress/corp-gateway]
  http:
    - headers: { request: { set: { x-internal-user: "true" } } }
      route:
        - { destination: { host: orders-api, subset: stable }, weight: 100 }
        - { destination: { host: orders-api, subset: canary }, weight: 0 }
---
# In-mesh callers (the checkout service) always use stable.
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata: { name: orders-api-mesh }
spec:
  hosts: [orders-api]
  gateways: [mesh]
  http:
    - route:
        - { destination: { host: orders-api, subset: stable }, weight: 100 }
YML

cat > deploy/alerts.yaml <<'YML'
# Canary volume is low (about 25 requests an hour, ~12 per 30 minutes), so these alert on counts
# over 30 minutes, not on ratios.
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata: { name: orders-api-canary }
spec:
  groups:
    - name: orders-api-canary
      rules:
        - alert: OrdersCanary5xx
          expr: sum(increase(istio_requests_total{destination_workload="orders-api-canary",response_code=~"5.."}[30m])) >= 2
          labels: { severity: page, team: payments }
        - alert: OrdersCanarySlow
          expr: sum(increase(istio_request_duration_milliseconds_count{destination_workload="orders-api-canary"}[30m])) >= 5 and histogram_quantile(0.99, sum by (le) (rate(istio_request_duration_milliseconds_bucket{destination_workload="orders-api-canary"}[30m]))) > 500
          labels: { severity: page, team: payments }
YML

mkdir -p deploy/migrations
cat > deploy/migrations/0003_create_canary_orders.sql <<'SQL'
-- Records which orders the canary created. A new table only: no existing table is altered, and with
-- no foreign key it takes no lock on orders, so stable 1.3.2 is unaffected.
CREATE TABLE canary_orders (
  order_id BIGINT PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
SQL
cat > deploy/migrations/0003_create_canary_orders.down.sql <<'SQL'
DROP TABLE canary_orders;
SQL

git add -A
GIT_AUTHOR_DATE="$CANARY_COMMITTED 16:00:00 +0000" GIT_COMMITTER_DATE="$CANARY_COMMITTED 16:00:00 +0000" \
  git -c user.email=dev@example.com -c user.name=dev commit -qm "deploy: canary 1.4.0 at weight 0, pinned to the digest from release run 412"

cat > docs/canary-plan.md <<MD
# Canary plan: orders-api 1.4.0

- **Candidate:** release 1.4.0, tag \`v1.4.0\`, image \`registry.example.com/orders-api@${CANARY_DIGEST}\`
  (built and pushed by \`.github/workflows/release.yml\`; see \`docs/ci-runs.md\`). Stable stays on
  1.3.2 (\`@${STABLE_DIGEST}\`), the known-good rollback target.
- **Exposure:** at most 1% of employee requests. Only \`corp-gateway\` (corporate SSO required, \`deploy/corp-gateway-auth.yaml\`) can
  reach the canary: the weights in \`deploy/routes.yaml\` are committed as stable 100 / canary 0
  and set to stable 99 / canary 1 at window start, after migration 0003 is applied in production. \`public-gateway\` removes the
  \`x-internal-user\` header and routes only to stable, and in-mesh callers always use stable. No
  external customer traffic can reach the canary. Strict mTLS and a caller allow-list
  (\`deploy/mesh-security.yaml\`) stop anything from bypassing these routes.
- **Volume:** the internal order tool peaks at about 2,500 requests an hour, so the canary sees
  about 25 an hour; capacity is not a concern at this boundary.
- **Data:** the canary (\`ORDERS_TRACK=canary\`) reads and writes \`orders\` exactly as stable 1.3.2
  does, so every order is readable on either track, and in the same statement records each new
  order's id in \`canary_orders\`. Migration 0003 only creates \`canary_orders\`; the \`orders\`
  schema does not change. It has a down migration and was applied, rolled back, and re-applied in
  staging (\`docs/ci-runs.md\`). Canary orders are employee test orders listed in \`canary_orders\`
  and may be deleted; nothing else may be.
- **Kill switch:** set \`enabled: "false"\` in \`deploy/canary-flags-configmap.yaml\` (canary only).
  The canary re-reads the mounted file on every request; the staging drill measured 35 s
  including the kubelet volume sync (\`docs/kill-switch-drill.md\`). Stable has no flag and is
  unaffected.
- **Rollback:** set the weights back to stable 100 / canary 0 in \`orders-api-corp\` (takes effect in seconds), then the
  kill switch, then scale the canary to 0.
- **Stop criteria (any one triggers rollback):** 2 or more canary 5xx responses in 30 minutes, canary
  p99 above 500 ms over 30 minutes with at least 5 requests (both page payments on-call through
  \`deploy/alerts.yaml\`), or any report of a wrong canary order total, which employees send to the
  payments on-call pager.
- **Owner:** payments on-call rotation; canary-window primary J. Rivera. Decision authority: the
  payments engineering manager.
- **Window and reassessment:** ${WINDOW_START} to ${WINDOW_END}. Reassess on ${WINDOW_END} or after any stop
  event, whichever comes first. Widening beyond 1% or to external users needs a new readiness review.
- **Compliance:** orders-api stores order IDs and totals only; card data stays in payments-gateway.
  See \`docs/pci-scope.md\`.

## Residual risks inside the canary boundary

| Risk | Disposition | Control | Owner | Expiry |
|---|---|---|---|---|
| Restore from backup never drilled | Accepted for the canary only: canary orders are disposable employee test orders, and the canary never updates or deletes an existing order | Additive migration with a down migration; nightly backups | Payments EM | ${WINDOW_END} |
| No load test | Accepted: about 25 requests an hour | Count-based alerts; rollback by weight | Payments EM | ${WINDOW_END} |
| Migration 0003 must run in production before the window opens | Accepted: it only creates \`canary_orders\`, scheduled for ${MIGRATION}; no existing table is touched | Down migration after the canary is scaled to 0 | Payments EM | ${WINDOW_END} |
| Tests use a fake database | Accepted: the canary's queries are 1.3.2's read and insert, with an insert into \`canary_orders\` in the same statement | Wrong-total reports page on-call; staging run in \`docs/ci-runs.md\` | Payments on-call | ${WINDOW_END} |

## Out of scope (GA blockers)

No restore drill, no load test, no disaster-recovery plan.
MD

cat > docs/kill-switch-drill.md <<MD
# Kill-switch and rollback drill (staging, ${DRILLED})

Setup: staging mirrors deploy/ (stable 1.3.2 x2, canary 1.4.0 x1, routes.yaml, destination-rule.yaml,
mesh-security.yaml, corp-gateway-auth.yaml) with the window weights applied: stable 99 / canary 1.

1. 14:02:10 UTC: set \`enabled: "false"\` in orders-api-canary-flags. First canary 503 at 14:02:45
   (35 s, kubelet volume sync). Stable kept serving 201s throughout (it has no flag).
2. 14:05:00: set \`enabled: "true"\`; canary served 201s again at 14:05:31. No pod restart.
3. 14:07:00: set the weights to stable 100 / canary 0 in orders-api-corp; the last canary request was logged at
   14:07:03 (3 s).
4. A request to public-gateway with \`x-internal-user: true\` was served by stable (header removed).
5. 50 requests from the checkout service (in mesh) all went to stable; a request from a pod
   without a sidecar was refused (strict mTLS, deploy/mesh-security.yaml).
6. 14:10:00: a NetworkPolicy blocked the staging canary pod's database egress, so its next 3
   requests returned 503 after the 2 s connection timeout. OrdersCanary5xx fired at 14:12:30 and
   paged the payments rotation (staging PagerDuty incident 4471, acknowledged 14:13:05). The
   NetworkPolicy was removed at 14:15:00.
7. A request to corp-gateway without a corporate SSO token was rejected with 403; the same request
   with a valid token was served.

Operator: J. Rivera. Recorded by: payments on-call.
MD

cat > docs/ci-runs.md <<MD
# Release evidence for v1.4.0

- Release workflow run 412 on tag v1.4.0, ${RELEASED} (commit \`${RELEASE_SHA}\`): \`npm ci\`, \`npm test\`
  (8 tests passed), image built and pushed, build provenance attested; the uploaded
  \`release-digests\` artifact records digest \`${CANARY_DIGEST}\` for that commit.
- Staging deploy ${STAGED}: migration 0003 applied, then rolled back with the down migration and
  re-applied; canary smoke test (create and read an order) passed against the staging database.
MD

cat > docs/pci-scope.md <<MD
# PCI DSS scope (review of ${PCI_REVIEW})

orders-api stores order IDs, totals, and timestamps. It never receives card numbers or
authentication data; payments-gateway owns card handling and is the only service in the
cardholder data environment. The ${PCI_REVIEW} scoping review by the security team placed orders-api
outside the CDE; no PCI requirement applies to this canary.
MD

cat > docs/runbook.md <<MD
# Orders API runbook
- Abort the canary: set the weights to stable 100 / canary 0 in \`orders-api-corp\` (deploy/routes.yaml), then
  \`enabled: "false"\` in orders-api-canary-flags, then scale \`deployment/orders-api-canary\` to 0.
- Roll back stable: \`kubectl rollout undo deployment/orders-api-stable\`.
- Migration 0003 rollback: apply \`deploy/migrations/0003_create_canary_orders.down.sql\` after the
  canary is scaled to 0 (applied and rolled back in staging on ${STAGED}).
- Backups: nightly pg_dump to S3 (restore procedure: TODO; GA blocker).
MD

cat > README.md <<'MD'
# orders-api
Order service for the checkout flow. Owner: payments team. Alerts: canary alerts in
`deploy/alerts.yaml`; GA alerting is not yet designed. Canary: see `docs/canary-plan.md`.
MD

git add -A
GIT_AUTHOR_DATE="$DOCS_COMMITTED 16:00:00 +0000" GIT_COMMITTER_DATE="$DOCS_COMMITTED 16:00:00 +0000" \
  git -c user.email=dev@example.com -c user.name=dev commit -qm "docs: canary plan and staging evidence for 1.4.0"
