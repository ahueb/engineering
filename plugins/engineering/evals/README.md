# Plugin evals

Trigger-quality cases for `production-readiness-review`: ten prompts that should invoke the skill (`prr-trigger-*`) and ten that should not (`prr-no-trigger-*`). Each case has one `tool_used: Skill` grader.

```bash
cd plugins/engineering
claude plugin eval . --tag prr-trigger        # positive cases
claude plugin eval . --tag prr-no-trigger     # negative cases
claude plugin eval . --case 'prr-*' --runs 1  # quick layout check
```

Run with the session default model. On a 200K-context model such as Haiku the skill listing overruns its default budget and later skills lose their descriptions, so trigger cases fail for a reason unrelated to the description text; `settings.recommended.json` raises `skillListingBudgetFraction` to 0.02 for normal sessions, but eval runs do not read user settings.

Every run is a model call on your account. Results land in `evals/results/`, which is ignored by git.

Six output-behavior scenarios for the audit itself (green CI is not readiness, backup documentation is not restore evidence, proxy-metric theater, bounded canary, AI overlay, multi-region falsification) are described in `../skills/production-readiness-review/references/evals-behavior.md`. They need a scaffolded repository per scenario and are not automated here.
