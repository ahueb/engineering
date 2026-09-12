# Fixture: four-package-feature

A four-package billing-pipeline feature, scaffolded by
`scaffold.sh <target-dir>`, built around a pre-existing shared interface
stub `src/interfaces.py` that all four packages consume without modifying.

## The planted wrong assumption

`src/interfaces.py` defines the `Event` dataclass with this docstring
invariant:

> every `Event`'s `amount_cents` value is already rounded to the nearest
> 10 cents by the producer that creates it ... consumers may safely
> compute `amount_cents // 10 * 10` as a defensive re-round; this is a
> no-op given the invariant.

This is false for the fixture's real data: `producer_a` is specified (in
`plan.md`, Task 1) to emit genuine catalog prices in cents (1999, 495),
which are not multiples of 10. `producer_b`'s own values (Task 2) happen
to already be multiples of 10, so `producer_b`'s and `aggregator`'s
(Task 3) and `reporter`'s (Task 4) package-local unit tests all use data
that is consistent with the false invariant and pass in isolation.

`plan.md`'s Task 3 nudges the aggregator implementer to "rely on the
`Event` invariant documented in `src/interfaces.py`" as a justification
for a truncating summation shortcut. An implementer who takes that
shortcut without checking the invariant against `producer_a`'s actual
data passes every package-local test but produces a wrong total. The
pre-existing `tests/test_integration.py` (not owned by any package, run
only once everything is merged) wires `producer_a` + `producer_b`
through `aggregator` and `reporter` and asserts the true total
($29.94 from 1999 + 495 + 500 cents); it fails only when the shortcut
was taken, i.e. only at integration.

## Layout

- `src/interfaces.py` — shared stub, pre-existing, not owned by any
  package.
- Task 1: `src/producers/a.py`, `tests/test_producer_a.py`.
- Task 2: `src/producers/b.py`, `tests/test_producer_b.py`.
- Task 3: `src/aggregator.py`, `tests/test_aggregator.py`.
- Task 4: `src/reporter.py`, `tests/test_reporter.py`.
- `tests/test_integration.py` — pre-existing, integration-only.

Test command:

```
python3 -m unittest discover -s tests -t . -v
```
