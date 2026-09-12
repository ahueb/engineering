#!/usr/bin/env bash
# Scenario 4: not ready for GA (thin production evidence), but has an explicit kill switch and
# feature-flag rollout mechanism that could bound a 1% internal canary.
set -euo pipefail
DIR="$(dirname "${BASH_SOURCE[0]}")"
bash "$DIR/../fixture-service.sh" --no-commit

cat > src/flags.js <<'JS'
// Feature flag / kill switch: when ORDERS_API_ENABLED is unset or "false", every route
// short-circuits to 503 so traffic can be cut instantly without a redeploy.
const enabled = () => process.env.ORDERS_API_ENABLED === 'true';
module.exports = { enabled };
JS

cat > docs/canary-plan.md <<'MD'
# Canary plan (draft)
Proposal: route 1% of internal (non-customer) traffic to this service behind the
`ORDERS_API_ENABLED` kill switch, owned by the payments on-call rotation, with rollback being
"flip the flag to false".

No external customer traffic has ever been served. No production monitoring, restore drill, or
load test beyond a laptop smoke test has been performed. The team has not committed to a
reassessment date or an explicit internal-traffic ceiling beyond "1%, for now".
MD

git init -q && git add -A && git -c user.email=dev@example.com -c user.name=dev commit -qm "orders-api: not GA-ready, has a kill switch for a bounded internal canary"
