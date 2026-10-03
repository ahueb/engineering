#!/usr/bin/env bash
# Scenario 5: an AI-enabled service. This script adds customer auth at the public gateway, paging
# alerts, an image pinned by digest, and a dated restore drill to the shared base, but model
# versioning, evaluation slices, prompt-injection/tool-abuse tests, provider fallback, and cost
# ceilings are not evidenced.
set -euo pipefail
DIR="$(dirname "${BASH_SOURCE[0]}")"
bash "$DIR/../fixture-service.sh" --no-commit

cat > src/summarize.js <<'JS'
// Calls the model provider to summarize an order note. No pinned model version, no retry to a
// fallback provider, and no per-request or per-day cost ceiling.
const client = require('some-llm-sdk');
async function summarizeNote(note) {
  const res = await client.chat({ model: 'latest', messages: [{ role: 'user', content: note }] });
  return res.choices[0].message.content;
}
module.exports = { summarizeNote };
JS

cat > docs/ai-notes.md <<'MD'
# AI feature notes
`summarizeNote` calls the configured provider with `model: "latest"` (no pinned version).
There is no evaluation suite over labeled summarization slices, no prompt-injection or
tool-abuse test suite, no fallback provider if the primary is down, and no cost ceiling or
budget alert on model spend.
MD


# The controls the prompt says are in place. Every date is relative to the day the fixture is built.
NOW=$(date -u +%s)
day() { # day OFFSET: the date OFFSET days from today, as YYYY-MM-DD (GNU date, else BSD date)
  local t=$((NOW + $1 * 86400))
  date -u -d "@$t" +%F 2>/dev/null || date -u -r "$t" +%F
}
RESTORE_DRILLED=$(day -9)
NEXT_DRILL=$(day 81)
IMAGE_DIGEST=sha256:7a1c3e5f9b2d4f6a8c0e2b4d6f8a1c3e5b7d9f1a3c5e7b9d1f3a5c7e9b1d3f5a

cat > deploy/deployment.yaml <<YML
apiVersion: apps/v1
kind: Deployment
metadata: { name: orders-api, labels: { app: orders-api } }
spec:
  replicas: 3
  selector: { matchLabels: { app: orders-api } }
  template:
    metadata: { labels: { app: orders-api } }
    spec:
      containers:
        - name: orders-api
          image: registry.example.com/orders-api@${IMAGE_DIGEST}
          resources: { requests: { cpu: 200m, memory: 256Mi }, limits: { cpu: "1", memory: 512Mi } }
          readinessProbe: { httpGet: { path: /healthz, port: 8080 } }
YML

cat > deploy/routes.yaml <<'YML'
apiVersion: v1
kind: Service
metadata: { name: orders-api }
spec:
  selector: { app: orders-api }
  ports: [{ port: 80, targetPort: 8080 }]
---
# Customers reach orders-api only through public-gateway (customer token required, deploy/gateway-auth.yaml).
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata: { name: orders-api-public }
spec:
  hosts: [orders.example.com]
  gateways: [istio-ingress/public-gateway]
  http:
    - route: [{ destination: { host: orders-api, port: { number: 80 } } }]
YML

cat > deploy/gateway-auth.yaml <<'YML'
# public-gateway admits only requests carrying a valid customer token from the identity provider.
apiVersion: security.istio.io/v1beta1
kind: RequestAuthentication
metadata: { name: customer-jwt, namespace: istio-ingress }
spec:
  selector: { matchLabels: { istio: public-gateway } }
  jwtRules:
    - issuer: https://login.example.com
      jwksUri: https://login.example.com/.well-known/jwks.json
---
apiVersion: security.istio.io/v1beta1
kind: AuthorizationPolicy
metadata: { name: customer-jwt-required, namespace: istio-ingress }
spec:
  selector: { matchLabels: { istio: public-gateway } }
  action: ALLOW
  rules:
    - from: [{ source: { requestPrincipals: ["https://login.example.com/*"] } }]
YML

cat > deploy/alerts.yaml <<'YML'
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata: { name: orders-api }
spec:
  groups:
    - name: orders-api
      rules:
        - alert: OrdersApi5xxRatio
          expr: sum(rate(istio_requests_total{destination_workload="orders-api",response_code=~"5.."}[10m])) / sum(rate(istio_requests_total{destination_workload="orders-api"}[10m])) > 0.01
          for: 5m
          labels: { severity: page, team: payments }
        - alert: OrdersApiLatencyP99
          expr: histogram_quantile(0.99, sum by (le) (rate(istio_request_duration_milliseconds_bucket{destination_workload="orders-api"}[10m]))) > 500
          for: 10m
          labels: { severity: page, team: payments }
YML

cat > docs/runbook.md <<'MD'
# Orders API runbook
- On-call: payments rotation (PagerDuty schedule PAYMENTS-PRIMARY); escalation to the secondary
  after 10 minutes, then the payments engineering manager.
- Alerts: `deploy/alerts.yaml` (5xx ratio above 1% for 5 minutes, p99 latency above 500 ms for 10
  minutes) page the payments rotation.
- Restart: `kubectl rollout restart deployment/orders-api`
- Rollback: `kubectl rollout undo deployment/orders-api` (the image is pinned by digest).
- Backups: nightly pg_dump to S3; restore procedure and the last drill in `docs/restore-drill.md`.
MD

cat > docs/restore-drill.md <<MD
# Restore drill (${RESTORE_DRILLED})

1. Restored the previous night's pg_dump into a scratch PostgreSQL 16 instance.
2. Row counts and a checksum of \`orders\` matched the production snapshot taken at dump time.
3. Recovery time: 42 minutes from start until the service read the restored database. Recovery
   point: 24 hours (nightly dumps).
4. Operator: payments on-call. Next drill due ${NEXT_DRILL}.
MD

cat > README.md <<'MD'
# orders-api
Order service for the checkout flow. Owner: payments team. Customer auth at the public gateway
(`deploy/gateway-auth.yaml`); alerts in `deploy/alerts.yaml`; restore drill in `docs/restore-drill.md`.
MD

git init -q && git add -A && git -c user.email=dev@example.com -c user.name=dev commit -qm "orders-api: adds an AI-enabled note summarization feature"
