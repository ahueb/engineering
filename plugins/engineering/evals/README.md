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

## Comment-guidance suite

Eight native cases (`behaviour-comment-cleanup` plus `comment-guidance-review-only`,
`comment-guidance-implementation`, `comment-guidance-plan`, `comment-guidance-change-review`,
`comment-guidance-mechanical`, `comment-guidance-repair`, `comment-guidance-doc-plan`) exercise
comment/docstring guidance end to end: explicit cleanup, natural-language review, implementation,
plan-execution, change-review, mechanical rename, hard-repair, and plan-auditor. Each is tagged
`comment-guidance-write` or `comment-guidance-read`; `behaviour-comment-cleanup` carries both
`behaviour`/`behaviour-cleanup` and `comment-guidance-write`. Run reads and writes as separate
invocations with separate budgets:

```bash
: "${COMMENT_WRITE_BUDGET_USD:?Set an authorized budget for this invocation}"
: "${COMMENT_SUBJECT_MODEL:?Set the tested parent model}"
: "${COMMENT_JUDGE_MODEL:?Set the tested judge model}"

claude plugin eval plugins/engineering \
  --tag comment-guidance-write --scaffold --trust-plugin \
  --ablation none --runs 3 --threshold 1.0 \
  --model "$COMMENT_SUBJECT_MODEL" --judge-model "$COMMENT_JUDGE_MODEL" \
  --allow-tools Read Grep Glob Skill Agent Edit Write \
    "Bash(python3 *)" "Bash(git *)" \
  --keep-temp --no-publish --max-cost-usd "$COMMENT_WRITE_BUDGET_USD"
```

```bash
: "${COMMENT_READ_BUDGET_USD:?Set a separate authorized budget}"
claude plugin eval plugins/engineering \
  --tag comment-guidance-read --scaffold --trust-plugin \
  --ablation none --runs 3 --threshold 1.0 \
  --model "$COMMENT_SUBJECT_MODEL" --judge-model "$COMMENT_JUDGE_MODEL" \
  --allow-tools Read Grep Glob Skill Agent \
  --keep-temp --no-publish --max-cost-usd "$COMMENT_READ_BUDGET_USD"
```

The read cases' `no-edit`/`no-write`/`no-bash` graders document intent rather than measure
refusal: with the read-arm grant above the harness removes those tools from the session, so
read-mode scope is harness-enforced. Their value is as a tripwire if the grant is ever widened.

Prerequisites: Claude Code >= 2.1.273, verified locally for `--keep-temp` support; on Linux the
`Bash` grants above additionally require bubblewrap and socat to be installed for the eval
sandbox to run bash tools at all. The budget variables above are authorized-budget inputs you
must set explicitly; they are not recommended dollar amounts.

`--keep-temp` retains each run's scaffold workspace instead of deleting it. Retaining the
workspace path is not itself a passing result: for every actual retained workspace, run

```bash
python3 scripts/comment_guidance_checks.py artifacts \
  --case "$CASE_ID" \
  --fixtures plugins/engineering/evals/comment-guidance-support/fixtures.json \
  --manifest plugins/engineering/evals/comment-guidance-support/manifest.json \
  --candidate "$RETAINED_WORKSPACE" \
  --report "$TRUSTED_REPORT_PATH"
```

from the repository root, against each retained workspace, before treating that trial as
verified. The report's `artifact_status` covers only the deterministic checks this helper
implements; `semantic_status` is always `REQUIRES_REVIEW` and is never a substitute for reading
the `llm`-graded findings.

Trust boundary: `--trust-plugin` authorizes the inspected plugin/scaffold code in this
repository, not an arbitrary untrusted repository. Run this suite in a disposable config with no
unrelated secrets, no production credentials, and no side-effecting real integrations; a
read-only or bounded-write prompt is not itself a security sandbox.

Incomplete-run handling: a cost-limit abort, a denied required tool, a missing subagent trace, or
a retained workspace that cannot be located is an **unverified** trial, not a passing or failing
one — do not count it toward a pass rate and do not silently drop it from the reported
denominator.

`directives-intact`-style and `rubric`-style graders in these cases grade the *contents of
scaffolded and edited files after the run* (via `focus`/`target: { source: file, path: ... }`),
not the agent's final message; a final-message grader here is retained only for honest self-
reporting of scope and exceptions, not as evidence of artifact correctness.
