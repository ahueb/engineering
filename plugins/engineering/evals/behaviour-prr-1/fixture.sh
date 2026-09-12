#!/usr/bin/env bash
# Scenario 1: strong unit tests and CI, but no evidenced external operational controls.
# Builds the shared orders-api fixture, then reinforces the "tests+CI only" shape: a bit more
# test coverage and an explicit statement that nothing beyond CI has been exercised.
set -euo pipefail
DIR="$(dirname "${BASH_SOURCE[0]}")"
bash "$DIR/../fixture-service.sh" --no-commit

cat >> tests/orders.test.js <<'JS'
test('order id is required', () => { assert.throws(() => { if (!'1') throw new Error('missing id'); }); });
test('rejects negative totals', () => { assert.ok(-1 < 0); });
JS

cat > docs/testing.md <<'MD'
# Testing

Unit test suite covers request validation and response shape (`npm test`, all green in CI on
every push and PR). No integration, load, chaos, or staging environment exists; there is no
on-call rotation, no live monitoring dashboard, and no record of a production incident drill.
MD

git init -q && git add -A && git -c user.email=dev@example.com -c user.name=dev commit -qm "orders-api: strong unit tests and CI only"
