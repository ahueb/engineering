---
name: change-eval
description: Evaluate competing Claude Code workflows, models, prompts, agents, or implementation variants with repeatable evidence. Use when optimizing coding-agent quality, cost, latency, token use, correctness, or reliability, or when deciding whether a configuration change actually improves software delivery.
---

# Change evaluation

Define the decision before running the comparison.

1. Select representative tasks from the target workload. Include normal tasks and adversarial cases that expose likely failure modes.
2. Freeze task inputs, repository revision, environment, acceptance criteria, and grader logic before comparing variants.
3. Prefer outcome graders over style graders: tests passed, required behavior present, regression absence, security properties, and build health.
4. Track at minimum: task success, repeated-trial reliability, input/output tokens or usage, latency, human interventions, number of repair loops, and unnecessary diff size.
5. Use multiple trials when model stochasticity could change the conclusion. Do not report pass@k or pass^k without stating the estimator or independence assumptions used.
6. Inspect transcripts or diffs for reward hacking: weakened tests, skipped checks, hidden scope reductions, excessive hardcoding, or accidental acceptance-criterion changes.
7. Compare total cost to reach a correct final result, not only first-pass model price.
8. Report confidence and limitations. Do not generalize beyond the task distribution tested.
