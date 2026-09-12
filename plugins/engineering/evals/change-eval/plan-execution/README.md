# plan-execution benchmark (decision 5)

Compares two variants of the `plan-execution` skill across three frozen
fixtures, per the change-eval methodology
(`plugins/engineering/skills/change-eval/SKILL.md`) and decision 5 of
`docs/plans/2026-09-12-assurance-root-causes.md`.

This benchmark does not modify the shipped skill. It runs the shipped
skill ("current") and a patched copy ("bounded-check") side by side and
records evidence; whether the shipped skill actually changes is decided
separately, from the results, in a follow-up release (out of scope here).

## Layout

- `fixtures/two-package-refactor/`, `fixtures/four-package-feature/`,
  `fixtures/six-package-migration/` — each has `scaffold.sh <target-dir>`
  (creates a fresh git repository with tests and `plan.md`) and a
  `README.md` documenting the fixture. `four-package-feature` plants one
  deliberate wrong assumption in a shared interface stub; see its
  README for the mechanism.
- `variants/current/` — no stored plugin copy (see its README); `run.sh`
  copies the live `plugins/engineering` directory at run time.
- `variants/bounded-check/skill.patch` — a unified diff against
  `skills/plan-execution/SKILL.md` adding one step to the fan-out
  dispatch instructions: an implementer may run the package's own unit
  tests or type check once, capped at 60 seconds, before returning.
  `run.sh` applies it to a fresh copy of the live plugin at run time.
- `lib/parse_run.py` — parses one run's `stream-json` transcript log:
  fan-out detection (an `Agent`/`Task` tool use), cost
  (`total_cost_usd` from the final `result` event), and repair rounds
  (count of `Bash` invocations of the fixture's test command, minus the
  first).
- `lib/summarize.py` — reads `results.jsonl` and applies the decision-5
  rule to produce `summary.md`.
- `run.sh` — orchestrator; see `--dry-run` output and header comment for
  the exact invocation.

## Running

```
# List the 18 (fixture, variant, run) cells in interleaved order and the
# frozen inputs. Does not invoke claude or touch the network.
./run.sh --dry-run

# Real run. --budget-usd is required and must come from the caller
# (set from the Task 0.6 pilot: 1.5 * single-run cost * 18).
./run.sh --budget-usd 3.00 [--output-dir DIR] [--runs 3]
```

Each real run:

1. Scaffolds a fresh fixture repository with the fixture's `scaffold.sh`.
2. Builds the variant's plugin directory (a fresh copy of the live
   `plugins/engineering`, patched for `bounded-check`).
3. Builds a scratch `CLAUDE_CONFIG_DIR` holding only a copy of
   `$HOME/.claude/.credentials.json` (or
   `$CLAUDE_CONFIG_DIR/.credentials.json` if that variable is already
   set in the caller's environment).
4. Runs `claude -p '/engineering:plan-execution <plan.md>' --plugin-dir
   <variant-dir> --model sonnet --output-format stream-json
   --permission-mode acceptEdits --allowedTools Read Write Edit Bash
   Agent Skill Grep Glob` inside the fixture repository, capturing the
   `stream-json` transcript.
5. Parses the transcript for fan-out (a run without an `Agent`/`Task`
   tool use is recorded `valid: false`, per decision 5 / Task 0.6), cost,
   and repair rounds.
6. Independently runs the fixture's own test command
   (`python3 -m unittest discover -s tests -t .`) in the resulting repo
   to get an authoritative `tests_passed`, not merely whatever the
   transcript claims.
7. Records wall-clock and `git diff --stat` line count (intent-to-add is
   used first so new untracked files are included).
8. Appends one JSON record to `results.jsonl`.

After each completed pair (both variants for the same fixture and run
index), the cumulative recorded cost is compared to `--budget-usd`; once
it is exceeded, the run stops (the per-cell stop rule). Stopping mid-way
through a fixture leaves that fixture's pair incomplete, which
`summarize.py` reports as "no decision" for that fixture, per decision 5.

## Decision rule (verbatim, decision 5)

> adopt the bounded-check variant only if every completed fixture pair
> shows equal or better correctness on every run and the variant's
> worst-run cost is within 20% of the current variant's worst-run cost
> for that fixture; an incomplete pair, or a within-cell cost spread
> above 20%, makes the result "no decision".

`lib/summarize.py` applies this per fixture and then combines fixture
verdicts: adopt only if every fixture says adopt; "no decision" if any
fixture is incomplete or has excess cost spread; otherwise reject.

## Assumptions

- The exact `claude -p` invocation in decision 5 / the shared contract
  is used verbatim, with no added flags. If the installed CLI requires
  `--verbose` for `--output-format stream-json` under `-p`, set
  `EXTRA_CLAUDE_FLAGS="--verbose"` in the environment before invoking
  `run.sh`; the script appends `$EXTRA_CLAUDE_FLAGS` to the command but
  does not add anything on its own.
- Fan-out is detected via a tool named `Agent` or `Task` in the
  transcript (the contract's `--allowedTools` list names it `Agent`;
  `Task` is accepted defensively in case the CLI's tool_use name
  differs from the grant name).
- "Repair rounds" counts `Bash` tool_use invocations whose command
  contains the fixture's test-command substring (`unittest discover`),
  minus the first (the first is the initial integrated run, not a
  repair), floored at 0.
- Cost comes from the final `result` event's `total_cost_usd` field
  (falling back to `cost_usd` if a CLI version names it differently).
- `results.jsonl` and `summary.md` are written under
  `--output-dir` (default `./.runs/<UTC timestamp>/` next to `run.sh`);
  each fixture repo built during a real run is left on disk under a
  system temp directory for inspection and is not auto-deleted by
  `run.sh`.
- No `.claude-plugin`/`evals` exclusion beyond `evals/change-eval/plan-execution/.runs`
  is applied when copying `plugins/engineering` into a variant
  directory; the rest of the plugin (including this benchmark's own
  fixtures/variants) is copied along but is inert at agent run time
  since nothing invokes it.
