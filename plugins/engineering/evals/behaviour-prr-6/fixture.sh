#!/usr/bin/env bash
# Scenario 6: architecture docs claim a highly-available multi-region service, but the actual
# deployment shares a single database and there is no exercised failover evidence.
set -euo pipefail
DIR="$(dirname "${BASH_SOURCE[0]}")"
bash "$DIR/../fixture-service.sh" --no-commit

cat > docs/architecture.md <<'MD'
# Architecture

orders-api is deployed active-active across two regions (us-east-1, eu-west-1) behind a global
load balancer, giving high availability with automatic failover.
MD

cat > deploy/region-us-east-1.yaml <<'YML'
apiVersion: apps/v1
kind: Deployment
metadata: { name: orders-api-us-east-1 }
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: orders-api
          image: registry.example.com/orders-api:latest
          env:
            - { name: DATABASE_URL, value: "postgres://primary-db.example.com/orders" }
YML
cat > deploy/region-eu-west-1.yaml <<'YML'
apiVersion: apps/v1
kind: Deployment
metadata: { name: orders-api-eu-west-1 }
spec:
  replicas: 2
  template:
    spec:
      containers:
        - name: orders-api
          image: registry.example.com/orders-api:latest
          env:
            - { name: DATABASE_URL, value: "postgres://primary-db.example.com/orders" }
YML

cat > docs/incident-history.md <<'MD'
# Incident / failover history
No region failover has ever been triggered, tested, or exercised (in staging or production).
Alert routing exists in the monitoring vendor's console but no on-call engineer has confirmed
they can act on a page from it, and control-plane (kubectl/cloud console) access for the
on-call rotation has not been verified.
MD

git init -q && git add -A && git -c user.email=dev@example.com -c user.name=dev commit -qm "orders-api: 'multi-region HA' deployment sharing one database"
