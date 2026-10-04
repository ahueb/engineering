#!/usr/bin/env bash
# Scaffold the two-package-refactor fixture into $1 (created fresh).
# Usage: scaffold.sh <target-dir>
set -euo pipefail

TARGET="${1:?usage: scaffold.sh <target-dir>}"
rm -rf "$TARGET"
mkdir -p "$TARGET/src" "$TARGET/tests"

cat > "$TARGET/src/__init__.py" <<'EOF'
EOF
cat > "$TARGET/tests/__init__.py" <<'EOF'
EOF

cat > "$TARGET/src/orders.py" <<'EOF'
"""Order total calculations (tax logic duplicated inline; see plan.md)."""


def calc_total(items):
    """items: list of (name, price) with price in dollars. Returns total with tax."""
    subtotal = 0.0
    for _name, price in items:
        if price < 0:
            raise ValueError("price must not be negative")
        subtotal += price
    tax = round(subtotal * 0.0825, 2)
    return round(subtotal + tax, 2)


def calc_total_with_discount(items, discount_pct):
    """Same as calc_total but applies a percentage discount before tax."""
    subtotal = 0.0
    for _name, price in items:
        if price < 0:
            raise ValueError("price must not be negative")
        subtotal += price
    if not 0 <= discount_pct <= 100:
        raise ValueError("discount_pct must be between 0 and 100")
    discounted = subtotal * (1 - discount_pct / 100)
    tax = round(discounted * 0.0825, 2)
    return round(discounted + tax, 2)
EOF

cat > "$TARGET/tests/test_orders.py" <<'EOF'
import unittest

from src.orders import calc_total, calc_total_with_discount


class TestOrders(unittest.TestCase):
    def test_calc_total(self):
        self.assertAlmostEqual(calc_total([("widget", 10.0)]), 10.83, places=2)

    def test_calc_total_rejects_negative(self):
        with self.assertRaises(ValueError):
            calc_total([("bad", -1.0)])

    def test_calc_total_with_discount(self):
        self.assertAlmostEqual(
            calc_total_with_discount([("widget", 100.0)], 10), 97.43, places=2
        )

    def test_calc_total_with_discount_bad_pct(self):
        with self.assertRaises(ValueError):
            calc_total_with_discount([("widget", 100.0)], 150)


if __name__ == "__main__":
    unittest.main()
EOF

cat > "$TARGET/src/shipping.py" <<'EOF'
"""Shipping cost calculations (rate lookup duplicated inline; see plan.md)."""


def calc_shipping(weight_kg):
    if weight_kg <= 0:
        raise ValueError("weight_kg must be positive")
    if weight_kg <= 1:
        rate = 4.99
    elif weight_kg <= 5:
        rate = 9.99
    elif weight_kg <= 20:
        rate = 19.99
    else:
        rate = 39.99
    return rate


def calc_shipping_express(weight_kg):
    if weight_kg <= 0:
        raise ValueError("weight_kg must be positive")
    if weight_kg <= 1:
        rate = 4.99
    elif weight_kg <= 5:
        rate = 9.99
    elif weight_kg <= 20:
        rate = 19.99
    else:
        rate = 39.99
    return round(rate * 1.5, 2)
EOF

cat > "$TARGET/tests/test_shipping.py" <<'EOF'
import unittest

from src.shipping import calc_shipping, calc_shipping_express


class TestShipping(unittest.TestCase):
    def test_calc_shipping_tiers(self):
        self.assertEqual(calc_shipping(0.5), 4.99)
        self.assertEqual(calc_shipping(3), 9.99)
        self.assertEqual(calc_shipping(15), 19.99)
        self.assertEqual(calc_shipping(50), 39.99)

    def test_calc_shipping_rejects_nonpositive(self):
        with self.assertRaises(ValueError):
            calc_shipping(0)

    def test_calc_shipping_express(self):
        self.assertEqual(calc_shipping_express(0.5), 7.49)

    def test_calc_shipping_express_rejects_nonpositive(self):
        with self.assertRaises(ValueError):
            calc_shipping_express(-1)


if __name__ == "__main__":
    unittest.main()
EOF

cat > "$TARGET/plan.md" <<'EOF'
# Plan: remove duplicated tax and shipping-rate logic

Two independent refactors. Each task owns disjoint files.

## Task 1: extract tax calculation

Files: `src/orders.py` (modify), `src/tax.py` (new), `tests/test_tax.py` (new).

Interface: `src/tax.py` exposes `compute_tax(amount: float) -> float`,
implementing an 8.25% tax rate rounded to 2 decimals; raises `ValueError`
for a negative `amount`.

Update `src/orders.py`'s `calc_total` and `calc_total_with_discount` to
call `compute_tax` instead of computing tax inline. Their observable
behaviour (return values and raised exceptions) must not change.

Acceptance: `tests/test_orders.py` passes unchanged. `tests/test_tax.py`
tests `compute_tax` directly: a positive amount, zero, a negative amount
raising `ValueError`, and a rounding case (e.g. amount that produces a
tax value needing rounding).

## Task 2: extract shipping-rate lookup

Files: `src/shipping.py` (modify), `src/rates.py` (new), `tests/test_rates.py` (new).

Interface: `src/rates.py` exposes `lookup_rate(weight_kg: float) -> float`,
implementing the tiered rate table (<=1kg: 4.99, <=5kg: 9.99, <=20kg:
19.99, else: 39.99); raises `ValueError` for `weight_kg <= 0`.

Update `src/shipping.py`'s `calc_shipping` and `calc_shipping_express` to
call `lookup_rate` instead of computing the tier inline. Their observable
behaviour must not change.

Acceptance: `tests/test_shipping.py` passes unchanged. `tests/test_rates.py`
tests `lookup_rate` directly across all four tiers and the error case.

## Test command

```
python3 -m unittest discover -s tests -t . -v
```
EOF

cd "$TARGET"
git init -q
git add -A
git -c user.email=fixture@example.com -c user.name=fixture commit -q -m "scaffold: two-package-refactor fixture"
