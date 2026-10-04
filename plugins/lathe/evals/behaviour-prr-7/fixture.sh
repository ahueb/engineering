#!/usr/bin/env bash
# Scenario 7: a product with digital elements sold in the EU, with no vulnerability reporting
# path (no security contact, no coordinated-disclosure process).
set -euo pipefail
DIR="$(dirname "${BASH_SOURCE[0]}")"
bash "$DIR/../fixture-service.sh" --no-commit

cat > docs/product-info.md <<'MD'
# Product information
orders-api is packaged and sold as part of a commercial "OrdersBox" appliance distributed to
retail customers in the European Union (a product with digital elements under EU market rules).
MD

cat >> README.md <<'MD'

## Security
There is no `SECURITY.md`, no published security contact address, no PGP key, and no
coordinated-disclosure or vulnerability-reporting process anywhere in this repository or its
distribution channel.
MD

git init -q && git add -A && git -c user.email=dev@example.com -c user.name=dev commit -qm "orders-api: sold in the EU, no vulnerability reporting path"
