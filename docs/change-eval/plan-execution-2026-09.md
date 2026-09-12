# plan-execution change eval: current vs. bounded-check (2026-09-12)

Question: does a `plan-execution` variant that bounds the integrated verification loop ("bounded-check", `plugins/engineering/evals/change-eval/plan-execution/variants/bounded-check`) beat the shipped skill ("current") on correctness and cost? Harness, fixtures, and the verbatim decision rule live in `plugins/engineering/evals/change-eval/plan-execution/`.

## Setup

- Claude Code 2.1.269, `claude -p '/engineering:plan-execution <plan>' --plugin-dir <variant> --model sonnet --output-format stream-json`, scratch `CLAUDE_CONFIG_DIR`.
- Three fixtures (two-package refactor, four-package feature, six-package migration), two variants, three runs per cell: 18 runs, budget 32 USD, spent 12.51 USD.
- A run counts only if the skill fanned out to at least one subagent (an `Agent` tool use in the stream); a run without fan-out is `valid: false` and its pair is incomplete.
- Pilot (6 runs, 3.8 USD, recorded earlier): fan-out on the two- and four-package fixtures, none on the six-package fixture; the fixture was not enlarged, and the full run shows the six-package fixture does fan out under the current variant on all three runs.

## Result

Per-run table: `plan-execution-2026-09-summary.md` (the harness's `summary.md`, copied verbatim).

| fixture | current valid runs | bounded-check valid runs | tests passed (current / bounded) | worst valid cost USD (current / bounded) | verdict |
|---|---|---|---|---|---|
| two-package-refactor | 3/3 | 3/3 | 3/3 / 3/3 | 1.27 / 1.21 | no decision (within-cell cost spread > 20%) |
| four-package-feature | 2/3 | 2/3 | 3/3 / 2/3 (the invalid bounded run also failed its tests) | 0.73 / 0.72 | no decision (incomplete pair) |
| six-package-migration | 3/3 | 1/3 | 3/3 / 3/3 | 0.81 / 0.41 | no decision (incomplete pair) |

**Overall: no decision.** The `plan-execution` skill is unchanged.

What the data does say, outside the decision rule: the bounded-check variant skipped fan-out in 3 of 9 runs (the current variant in 1 of 9), and the one run that produced a failing test was a bounded-check run that did not fan out. Cheaper runs of the bounded variant are mostly runs that did less, not runs that did the same work for less. A future rerun needs fixtures large enough that neither variant ever skips fan-out, or a variant prompt that forbids skipping it; until then the cost comparison is not interpretable.

## Harness defects fixed after this run

Found by the post-run audit and fixed in the tree, not affecting the numbers above: `run.sh` used GNU-only `date +%s.%N` for wall-clock (now Python `time.time()`), interpolated `--budget-usd` into Python source (now validated as a plain decimal and passed as an argument), and `summarize.py`'s cost test was two-sided (a strictly cheaper variant counted as "not within 20%"); it is now one-sided. Re-running `summarize.py` on this run's `results.jsonl` with the one-sided test gives the same three verdicts.
