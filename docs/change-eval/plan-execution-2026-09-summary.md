# plan-execution benchmark: current vs. bounded-check

Decision rule (pre-registered before the run): adopt the bounded-check variant only if every completed fixture pair shows equal or better correctness on every run and the variant's worst-run cost is within 20% of the current variant's worst-run cost for that fixture; an incomplete pair, or a within-cell cost spread above 20%, makes the result "no decision".

## Fixture: two-package-refactor

| variant | run | valid (fan-out) | tests passed | cost (USD) | wall-clock (s) | repair rounds | diff-stat lines |
|---|---|---|---|---|---|---|---|
| current | 1 | True | True | 1.2686395499999998 | 256.9 | 1 | 17 |
| current | 2 | True | True | 0.9362292499999999 | 197.64 | 1 | 17 |
| current | 3 | True | True | 1.0666497499999998 | 254.73 | 1 | 17 |
| bounded-check | 1 | True | True | 0.9488598 | 185.53 | 1 | 17 |
| bounded-check | 2 | True | True | 1.0404342000000002 | 223.56 | 1 | 17 |
| bounded-check | 3 | True | True | 1.2066519500000001 | 236.41 | 1 | 17 |

**Fixture verdict:** no decision (within-cell cost spread > 20%)

## Fixture: four-package-feature

| variant | run | valid (fan-out) | tests passed | cost (USD) | wall-clock (s) | repair rounds | diff-stat lines |
|---|---|---|---|---|---|---|---|
| current | 1 | True | True | 0.73109155 | 168.21 | 1 | 16 |
| current | 2 | False | True | 0.19500979999999998 | 69.16 | 0 | 16 |
| current | 3 | True | True | 0.6805675 | 180.61 | 0 | 16 |
| bounded-check | 1 | True | True | 0.4260489 | 94.02 | 0 | 16 |
| bounded-check | 2 | True | True | 0.72024065 | 171.33 | 0 | 16 |
| bounded-check | 3 | False | False | 0.10030679999999999 | 26.15 | 0 | 12 |

**Fixture verdict:** no decision (incomplete pair)

## Fixture: six-package-migration

| variant | run | valid (fan-out) | tests passed | cost (USD) | wall-clock (s) | repair rounds | diff-stat lines |
|---|---|---|---|---|---|---|---|
| current | 1 | True | True | 0.7936996000000003 | 121.36 | 0 | 23 |
| current | 2 | True | True | 0.8103191999999999 | 153.16 | 0 | 23 |
| current | 3 | True | True | 0.7911791 | 222.24 | 0 | 23 |
| bounded-check | 1 | False | True | 0.1825612 | 47.57 | 0 | 23 |
| bounded-check | 2 | True | True | 0.41341779999999995 | 67.73 | 0 | 23 |
| bounded-check | 3 | False | True | 0.19555939999999997 | 138.29 | 0 | 23 |

**Fixture verdict:** no decision (incomplete pair)

## Overall

**No decision.** At least one fixture is incomplete, has a within-cell cost spread above 20%, or lacks cost data; see per-fixture verdicts above.
