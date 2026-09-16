# Trigger eval results

Recorded from `claude plugin eval . --case 'prr-*' --runs 1 --ablation none --scaffold --trust-plugin -j 4`.

| Run date (UTC) | Claude Code | Plugin | Cases | Passed | Cost (USD) | Notes |
|---|---|---|---:|---:|---:|---|
| 2026-09-12 | 2.1.269 | 2.7.1 + reworded descriptions (released as 2.7.2) | 20 | 20 | 9.36 | eval model claude-opus-5[1m]; run on the final tree after the description style change |
| 2026-09-12 | 2.1.269 | 2.7.1 | 20 | 20 | 9.54 | eval model claude-opus-5[1m]; scaffolded |
| 2026-09-12 | 2.1.269 | 2.5.1 (pre-release tree) | 20 | 20 | 8.75 | eval model claude-opus-5[1m]; each trigger case scaffolds the `fixture-service.sh` orders-api repository |
| 2026-09-12 | 2.1.269 | 2.5.0 | 20 | 17 | 4.51 | no scaffold: trigger-04, -08, -10 failed because the workspace was empty and the model answered "nothing to review" without invoking the skill |

Per-case (latest run): prr-no-trigger-01=1, prr-no-trigger-02=1, prr-no-trigger-03=1, prr-no-trigger-04=1, prr-no-trigger-05=1, prr-no-trigger-06=1, prr-no-trigger-07=1, prr-no-trigger-08=1, prr-no-trigger-09=1, prr-no-trigger-10=1, prr-trigger-01=1, prr-trigger-02=1, prr-trigger-03=1, prr-trigger-04=1, prr-trigger-05=1, prr-trigger-06=1, prr-trigger-07=1, prr-trigger-08=1, prr-trigger-09=1, prr-trigger-10=1.

What this does and does not show: every positive prompt invoked `production-readiness-review` and no negative prompt did, on one run each. It does not measure report quality; that is measured by the outcome-graded `behaviour-prr-1`..`-7` and `behaviour-comment-cleanup` cases (results below). Rerun after changing the skill description or when Claude Code changes skill listing behaviour; three or more runs per case are needed before treating a single failure as a regression.

# Behaviour eval results

Recorded from `claude plugin eval . --case 'behaviour-prr-*' --runs 3 --scaffold --trust-plugin --ablation none --judge-model sonnet --allow-tools Read Grep Glob "Bash(python3 *)" --max-cost-usd 13` and the separate comment-cleanup invocation in `README.md`.

| Run date (UTC) | Claude Code | Plugin | Suite | Runs | Result | Cost (USD) | Notes |
|---|---|---|---:|---|---:|---|---|
| 2026-09-12 | 2.1.269 | 2.8.0 + this release's tree | `behaviour-prr-1`..`-7` | 7 × 3 | `VERDICT`/`GATE` regex graders: 18/18 on scenarios 1, 2, 3, 5, 6, 7; scenario 4: 0/3 (`NOT READY` where `CONDITIONALLY READY` is expected, see risk register R15); `llm` rubric 20/21 (one FAIL on scenario 5) | 9.84 | eval model claude-sonnet-5; prompts invoke the skill by slash command |
| 2026-09-12 | 2.1.269 | 2.8.0 + this release's tree | `behaviour-comment-cleanup` | 1 × 3 | 3/3 runs passed every grader (`directives-intact`, `rubric`, `skill-fired`) | 0.58 | eval model claude-sonnet-5; `Skill` added to the tool grants after a first 3-run batch (2/3) in which one run was denied the `Skill` tool by the sandbox |

Note on the 2026-09-12 `behaviour-comment-cleanup` row: this 3/3 result was measured under the
previous grader version, which graded the agent's final message with a regex plus an
`llm` rubric over that final message, and used a workspace-local convenience checker for line
membership. It did not grade file contents through an external, trusted checker and is not
evidence for the artifact-preservation, directive-attachment, or code-preservation properties the
current `directives-intact`/`rubric` graders and `scripts/comment_guidance_checks.py` assess.
Treat it only as historical evidence that the skill fired and produced a plausible final report.

## Comment-guidance suite results

Cases B01-B08 and installation/context tests I01-I04, as specified in
`docs/change-eval/comment-guidance-2026-09.md`.

| Case | Result |
|---|---|
| B01 `behaviour-comment-cleanup` (current grader version) | NOT_RUN |
| B02 `comment-guidance-review-only` | NOT_RUN |
| B03 `comment-guidance-implementation` | NOT_RUN |
| B04 `comment-guidance-plan` | NOT_RUN |
| B05 `comment-guidance-change-review` | NOT_RUN |
| B06 `comment-guidance-mechanical` | NOT_RUN |
| B07 `comment-guidance-repair` | NOT_RUN |
| B08 `comment-guidance-doc-plan` | NOT_RUN |
| I01 local `--plugin-dir` execution | NOT_RUN |
| I02 marketplace/cache installation | NOT_RUN |
| I03 policy path fallback/installed/legacy/stale | NOT_RUN |
| I04 supported-version and forked/direct-agent context | NOT_RUN |
