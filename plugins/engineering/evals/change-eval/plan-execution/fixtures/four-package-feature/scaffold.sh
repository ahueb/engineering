#!/usr/bin/env bash
# Scaffold the four-package-feature fixture into $1 (created fresh).
# Usage: scaffold.sh <target-dir>
set -euo pipefail

TARGET="${1:?usage: scaffold.sh <target-dir>}"
rm -rf "$TARGET"
mkdir -p "$TARGET/src/producers" "$TARGET/tests"

cat > "$TARGET/src/__init__.py" <<'EOF'
EOF
cat > "$TARGET/src/producers/__init__.py" <<'EOF'
EOF
cat > "$TARGET/tests/__init__.py" <<'EOF'
EOF

cat > "$TARGET/src/interfaces.py" <<'EOF'
"""Shared event interface for the billing pipeline.

Pre-existing, shared by every package below. Do not modify.

INVARIANT (assumed true by all consumers): every Event's `amount_cents`
value is already rounded to the nearest 10 cents by the producer that
creates it. Consumers may safely compute `amount_cents // 10 * 10` as a
defensive re-round if they need one; this is a no-op given the invariant.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Event:
    kind: str
    amount_cents: int
    currency: str = "USD"
EOF

cat > "$TARGET/src/producers/a.py" <<'EOF'
"""Producer A: emits real catalog prices in cents."""
from src.interfaces import Event


def produce():
    """Real catalog prices, in cents, not necessarily multiples of 10."""
    return [
        Event(kind="widget", amount_cents=1999, currency="USD"),
        Event(kind="gadget", amount_cents=495, currency="USD"),
    ]
EOF

cat > "$TARGET/tests/test_producer_a.py" <<'EOF'
import unittest

from src.producers.a import produce
from src.interfaces import Event


class TestProducerA(unittest.TestCase):
    def test_produce_returns_catalog_events(self):
        events = produce()
        self.assertEqual(
            events,
            [
                Event(kind="widget", amount_cents=1999, currency="USD"),
                Event(kind="gadget", amount_cents=495, currency="USD"),
            ],
        )


if __name__ == "__main__":
    unittest.main()
EOF

cat > "$TARGET/src/producers/b.py" <<'EOF'
"""Producer B: emits a flat shipping fee, already a multiple of 10 cents."""
from src.interfaces import Event


def produce():
    return [Event(kind="shipping", amount_cents=500, currency="USD")]
EOF

cat > "$TARGET/tests/test_producer_b.py" <<'EOF'
import unittest

from src.producers.b import produce
from src.interfaces import Event


class TestProducerB(unittest.TestCase):
    def test_produce_returns_shipping_event(self):
        self.assertEqual(
            produce(), [Event(kind="shipping", amount_cents=500, currency="USD")]
        )


if __name__ == "__main__":
    unittest.main()
EOF

cat > "$TARGET/tests/test_aggregator.py" <<'EOF'
import unittest

from src.aggregator import total_cents
from src.interfaces import Event


class TestAggregator(unittest.TestCase):
    def test_total_cents_sums_events(self):
        events = [
            Event(kind="a", amount_cents=100, currency="USD"),
            Event(kind="b", amount_cents=200, currency="USD"),
        ]
        self.assertEqual(total_cents(events), 300)

    def test_total_cents_empty(self):
        self.assertEqual(total_cents([]), 0)


if __name__ == "__main__":
    unittest.main()
EOF

cat > "$TARGET/tests/test_reporter.py" <<'EOF'
import unittest

from src.reporter import format_report


class TestReporter(unittest.TestCase):
    def test_format_report(self):
        self.assertEqual(format_report(2494), "$24.94")
        self.assertEqual(format_report(0), "$0.00")
        self.assertEqual(format_report(5), "$0.05")


if __name__ == "__main__":
    unittest.main()
EOF

cat > "$TARGET/tests/test_integration.py" <<'EOF'
"""Pre-existing integration test. Not owned by any package. Run only once
everything is merged; exercises the real, wired-together pipeline."""
import unittest

from src.producers.a import produce as produce_a
from src.producers.b import produce as produce_b
from src.aggregator import total_cents
from src.reporter import format_report


class TestIntegration(unittest.TestCase):
    def test_full_pipeline_total(self):
        events = produce_a() + produce_b()
        total = total_cents(events)
        # 1999 + 495 + 500 = 2994 cents = $29.94
        self.assertEqual(format_report(total), "$29.94")


if __name__ == "__main__":
    unittest.main()
EOF

cat > "$TARGET/plan.md" <<'EOF'
# Plan: billing pipeline (producer -> aggregator -> reporter)

Four independent packages, each owning disjoint files, built against the
pre-existing shared interface `src/interfaces.py` (do not modify it).

## Task 1: producer A

Files: `src/producers/a.py` (new), `tests/test_producer_a.py` (new).

Interface: `produce() -> list[Event]` returning real catalog prices in
cents for two items: widget at $19.99 (1999 cents) and gadget at $4.95
(495 cents), both currency "USD".

Acceptance: `tests/test_producer_a.py` asserts `produce()` returns
exactly those two `Event`s.

## Task 2: producer B

Files: `src/producers/b.py` (new), `tests/test_producer_b.py` (new).

Interface: `produce() -> list[Event]` returning one shipping fee event of
500 cents ($5.00), currency "USD".

Acceptance: `tests/test_producer_b.py` asserts `produce()` returns
exactly that event.

## Task 3: aggregator

Files: `src/aggregator.py` (new), `tests/test_aggregator.py` (new).

Interface: `total_cents(events: list[Event]) -> int`, summing
`amount_cents` across all events. You may rely on the `Event` invariant
documented in `src/interfaces.py` for any rounding-related implementation
choices.

Acceptance: `tests/test_aggregator.py` asserts the sum over a small list
of synthetic events.

## Task 4: reporter

Files: `src/reporter.py` (new), `tests/test_reporter.py` (new).

Interface: `format_report(total_cents: int) -> str`, formatting cents as
a dollar string with two decimals and a leading `$`, e.g. `2494 ->
"$24.94"`.

Acceptance: `tests/test_reporter.py` asserts the formatting for several
hardcoded cent values.

## Test command

```
python3 -m unittest discover -s tests -t . -v
```
EOF

cd "$TARGET"
git init -q
git add -A
git -c user.email=fixture@example.com -c user.name=fixture commit -q -m "scaffold: four-package-feature fixture"
