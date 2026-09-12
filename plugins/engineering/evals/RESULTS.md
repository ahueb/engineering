# Trigger eval results

Recorded from `claude plugin eval . --case 'prr-*' --runs 1 --ablation none --scaffold --trust-plugin -j 4`.

| Run date (UTC) | Claude Code | Plugin | Cases | Passed | Cost (USD) | Notes |
|---|---|---|---:|---:|---:|---|
| 2026-09-12 | 2.1.269 | 2.5.1 (pre-release tree) | 20 | 20 | 8.75 | eval model claude-opus-5[1m]; each trigger case scaffolds the `fixture-service.sh` orders-api repository |
| 2026-09-12 | 2.1.269 | 2.5.0 | 20 | 17 | 4.51 | no scaffold: trigger-04, -08, -10 failed because the workspace was empty and the model answered "nothing to review" without invoking the skill |

Per-case (latest run): prr-no-trigger-01=1, prr-no-trigger-02=1, prr-no-trigger-03=1, prr-no-trigger-04=1, prr-no-trigger-05=1, prr-no-trigger-06=1, prr-no-trigger-07=1, prr-no-trigger-08=1, prr-no-trigger-09=1, prr-no-trigger-10=1, prr-trigger-01=1, prr-trigger-02=1, prr-trigger-03=1, prr-trigger-04=1, prr-trigger-05=1, prr-trigger-06=1, prr-trigger-07=1, prr-trigger-08=1, prr-trigger-09=1, prr-trigger-10=1.

What this does and does not show: every positive prompt invoked `production-readiness-review` and no negative prompt did, on one run each. It does not measure report quality; the seven behaviour scenarios in `../skills/production-readiness-review/references/evals-behavior.md` remain manual. Rerun after changing the skill description or when Claude Code changes skill listing behaviour; three or more runs per case are needed before treating a single failure as a regression.
