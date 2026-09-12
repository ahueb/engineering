# Fixture: two-package-refactor

A small Python repo with two independent duplication-removal refactors.
`scaffold.sh <target-dir>` creates a fresh git repository at `<target-dir>`
containing:

- `src/orders.py`, `tests/test_orders.py` — two functions with inline,
  duplicated tax-calculation logic.
- `src/shipping.py`, `tests/test_shipping.py` — two functions with inline,
  duplicated shipping-rate-lookup logic.
- `plan.md` — a two-task plan: Task 1 extracts the tax logic into a new
  `src/tax.py` (+ `tests/test_tax.py`); Task 2 extracts the rate logic into
  a new `src/rates.py` (+ `tests/test_rates.py`). The two tasks own
  disjoint files and each touches at least two files, so plan-execution
  should partition them into two parallel packages.

No wrong assumption is planted in this fixture. Test command:

```
python3 -m unittest discover -s tests -t . -v
```

Acceptance: after the refactor, `tests/test_orders.py` and
`tests/test_shipping.py` still pass unchanged, and the new
`tests/test_tax.py` / `tests/test_rates.py` pass.
