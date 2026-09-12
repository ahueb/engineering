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

Seven output-behavior scenarios for the audit itself (green CI is not readiness, backup documentation is not restore evidence, proxy-metric theater, bounded canary, AI overlay, multi-region falsification, CRA-scope product without a vulnerability reporting path) are described in `../skills/production-readiness-review/references/evals-behavior.md`. They need a scaffolded repository per scenario and are not automated here.
