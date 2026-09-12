# Plugin evals

Trigger-quality cases for `production-readiness-review`: ten prompts that should invoke the skill (`prr-trigger-*`) and ten that should not (`prr-no-trigger-*`). Each case has one `tool_used: Skill` grader.

Every `prr-trigger-*` case has a `case.yaml` naming `fixture.sh`, which builds the shared `fixture-service.sh` orders-api repository in the workspace so the readiness question has something to review; pass `--scaffold` (and `--trust-plugin` when not interactive) or the positive cases run against an empty directory and fail for the wrong reason.

```bash
cd plugins/engineering
claude plugin eval . --tag prr-trigger --scaffold --trust-plugin        # positive cases
claude plugin eval . --tag prr-no-trigger                                # negative cases
claude plugin eval . --case 'prr-*' --runs 1 --scaffold --trust-plugin   # full suite, one run each
claude plugin eval . --case 'prr-*' --scaffold --trust-plugin --ablation none --threshold 1.0  # CI gate: fail on any grader miss
```

Negative cases pass trivially on the without-plugin arm; run them with `--ablation none` to make the check meaningful.

Run with the session default model. On a 200K-context model such as Haiku the skill listing overruns its default budget and the least-invoked skills lose their descriptions, so trigger cases fail for a reason unrelated to the description text; `settings.recommended.json` raises `skillListingBudgetFraction` to 0.02 for normal sessions, but eval runs do not read user settings (the eval sandbox loads no user settings, hooks, or other plugins).

Every run is a model call on your account (about 9 USD for the full suite at one run per case). Raw results land in `evals/results/`, which is ignored by git; summarise a run in `RESULTS.md`.

## Output-behavior (outcome-graded) cases

Seven output-behavior scenarios for the audit itself (green CI is not readiness, backup
documentation is not restore evidence, proxy-metric theater, bounded canary, AI overlay,
multi-region falsification, CRA-scope product without a vulnerability reporting path) are
described in `../skills/production-readiness-review/references/evals-behavior.md` and
implemented as `behaviour-prr-1` … `behaviour-prr-7`. Each scaffolds its own repository (via
`fixture-service.sh` plus scenario-specific artefacts) and is graded on the report's
machine-checkable `VERDICT:`/`GATE G<n>:` lines and an `llm` rubric — no reliance on
`tool_used: Skill` alone. Run them with grants that exclude `Edit`/`Write` (the audit must stay
read-only):

```bash
cd plugins/engineering
claude plugin eval . --tag behaviour-readiness --scaffold --trust-plugin --ablation none \
  --judge-model sonnet --allow-tools Read Grep Glob "Bash(python3 *)" --max-cost-usd 13
```

`behaviour-comment-cleanup` exercises `/engineering:comment-cleanup` against a small polyglot
repository and asserts that every protected directive comment (lint/type suppressions, build
directives, source-map and bundler magic comments, `@generated` headers) survives byte-identical
while ordinary stale comments are rewritten. It needs `Edit`/`Write` and runs as a separate
invocation with its own budget:

```bash
cd plugins/engineering
claude plugin eval . --case behaviour-comment-cleanup --scaffold --trust-plugin --ablation none \
  --judge-model sonnet --allow-tools Read Grep Glob Skill Edit Write "Bash(python3 *)" --max-cost-usd 6
```

These two invocations are separate on purpose: `--case 'prr-*'` (the trigger-quality suite
above) must never be widened to `behaviour-*` — the `behaviour-*` cases are outcome-graded,
cost far more per run, and need write grants the trigger suite does not.
