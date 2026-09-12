---
name: production-readiness-review
description: Audit production readiness evidence-first with non-compensable hard gates, graded dimensions, and adversarial falsification, returning READY, CONDITIONALLY READY, or NOT READY. Use when asked whether a repo, branch, PR, service, build, or release is ready to ship, launch, deploy, go live, or reach GA; for an operational or launch readiness review, release gate, canary or GA assessment, on-call handover, or go/no-go; or when asked to challenge or disprove a claim that something is production ready. Not for ordinary code review, debugging, test writing, or deployment execution.
---

# Production Readiness Review
Perform a read-only, evidence-first production readiness audit of the current repository or the release scope named by the user. Judge a specific candidate for a specific production exposure. Never equate repository quality, test success, or feature completeness with production readiness by itself.

## Core rules
1. Inspect before judging. Separate **observed**, **inferred**, and **unknown** facts. Do not infer external operational facts (on-call staffing, cloud configuration, recovery drills, production traffic, regulatory approval, live SLO attainment) from repository absence or presence; mark unknown unless direct evidence is available.
2. Use hard gates before graded dimensions. An applicable hard-gate failure cannot be compensated by strengths elsewhere.
3. Do not award execution evidence for documentation alone: a backup is not recovery evidence until restored; a dashboard is not operability evidence until detection and response are demonstrated; redundancy is not failover evidence until failure behavior is exercised or otherwise directly established.
4. A passing test supports only the behavior and conditions it actually tests. Do not generalize from coverage percentage, test count, a green CI badge, a scanner result, average latency, historical uptime, or a process label. Prefer candidate-specific, recent, traceable, representative, reproducible evidence; when evidence conflicts, prefer stronger and more direct evidence and explain the conflict.
5. Keep the audit read-only with respect to source, infrastructure, and remote systems: no edits, dependency installs, deploys, infrastructure changes, production migrations, secret rotation, releases, pushes, or remote mutation (ordinary local build/test artifacts/caches are fine). Never expose secret values, keys, tokens, credentials, or environment-variable contents in the report.
6. If current external facts materially affect readiness (an EOL dependency, active vulnerability, current regulation, provider limit), verify them from authoritative sources when web access is available; otherwise state that external freshness was not verified.
7. Do not force a universal numerical cutoff. Report the hard-gate decision and the two independent axes of readiness state and evidence strength.

## Claim discipline
For each material claim, work claim -> argument -> evidence -> defeaters -> disposition: state the proposition, the reasoning that would make it true (with assumptions), the supporting artifacts, the plausible ways it could still be false, and how each material defeater is prevented, detected, bounded, recovered from, or accepted.

Prefer evidence that is direct rather than inferential, tied to the exact candidate, representative of the target environment, recent enough that the mechanism has not materially changed, repeatable/reproducible rather than anecdotal, measured under failure/adverse conditions when the claim concerns failure behavior, and independently observed when consequence warrants stronger assurance. Repository presence is not proof that an external production control is enabled or used. Rate argument validity separately from evidence strength (the weak-oracle check): record an argument gap — the evidence does not actually entail the claim — as a defeater even when the evidence is E3.

Use **UNKNOWN** when a claim may be true but material evidence is unavailable, stale, or nonrepresentative. Use **FAIL** when evidence directly contradicts the gate or an explicit mandatory criterion is unmet. A material UNKNOWN necessary for the claimed exposure blocks READY exactly as a FAIL does, but stays recorded as UNKNOWN so the reason remains epistemically accurate.

## Scope the claim
Before collecting evidence, establish as much of the following as the available evidence permits:
- Candidate identity: repository root, branch, commit, dirty working-tree status, artifact/version if known.
- Target exposure: users/tenants, regions, traffic percentage, feature surface, data sensitivity, availability expectations, and whether the claim is canary, limited release, or GA.
- Critical journeys: the behaviors whose incorrectness or unavailability would make the release unacceptable.
- Environment boundary: what is in scope (application, infrastructure, dependencies, data stores, clients, operators) and what is external.

If the user does not specify an exposure, use the current working tree as the **source candidate under review**, but do not invent a deployable artifact or production operating envelope; record those as unknown and judge only what the available evidence supports.

## Collect deterministic repository signals
When Python 3 is available, run the bundled read-only probe before deep inspection:
```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/repo_probe.py" "${CLAUDE_PROJECT_DIR}"
```
If unavailable, continue without it; the probe is a discovery aid, not readiness evidence by itself. Read the files it identifies, corroborate important claims, and then inspect whatever each rubric gate's "Look for" list names that the probe did not surface.

For large repositories, dispatch read-only evidence collection in one batch and keep gate synthesis and the final verdict with the primary auditor:
- `engineering:scout`: locate test, CI, deployment, migration, operations, observability, and security files the probe did not surface, returning paths only.
- `engineering:security-reviewer`: Scope: the whole candidate, not a change. Return evidence with `path:line`, not a verdict. Collect evidence for gate G3 (authentication, authorization, secrets, dependency and supply-chain controls, trust boundaries).
- `engineering:semantic-reviewer`: Scope: the whole candidate, not a change. Return evidence with `path:line`, not a verdict. Examine the critical-journey tests for gate G2 and report weak oracles, mocked contracts, and untested failure modes.
- `engineering:browser-tester`: only when the candidate is a web application that can be run locally without new dependencies. One dispatch per critical journey via `/engineering:browser-testing` step 3; the result is direct G2 evidence for that journey and nothing else.

The first three are read-only by tool list; `browser-tester` has Bash and Playwright but is told not to edit. Their output is evidence to be weighed under the rubric; none of them decides a gate.

## Run high-value validation safely
Prefer commands already declared by the repository's CI, task runner, package manager, or contributor documentation, run only what is safe locally without installing new dependencies or mutating remote/prod systems, and prioritize build/reproducibility checks, tests relevant to critical journeys, lint/type/static-analysis that guards real defects, project-configured security/dependency/supply-chain checks, and local smoke/performance/failure checks already part of the project.

For every command run, record: exact command, working directory, candidate commit/working-tree state, exit status, the relevant concise result, and environmental limitations. A command that cannot run because of missing credentials, services, hardware, dependencies, or environment fidelity is **unverified**, not passed.

## Apply the rubric
Read [references/rubric.md](references/rubric.md) before assigning gate decisions. Evaluate all 12 hard gates and all 13 readiness dimensions that are applicable.

Hard-gate status is one of **PASS** (material claims supported strongly enough for the proposed exposure), **FAIL** (direct evidence shows the gate unsatisfied), **UNKNOWN** (material evidence missing, stale, ambiguous, or unverifiable), or **N/A** (demonstrably not applicable, with a short rationale). Rate evidence strength separately: **E0** no usable/traceable evidence; **E1** assertion/plan/policy/documentation only; **E2** direct but partial, stale, nonrepresentative, or not candidate-specific; **E3** recent, traceable, repeatable, representative, candidate-specific; **E4** meets every E3 property and is additionally independently reproduced or demonstrated under bounded real-production or realistic adverse conditions.

Rate readiness state for each graded dimension: **0** unknown/absent; **1** ad hoc; **2** defined but incompletely demonstrated; **3** validated for the candidate under representative conditions; **4** robustly demonstrated at realistic scale and adverse conditions. Evidence strength says how well a claim is known; readiness state says what has been achieved — rate both, never derive one from the other, and never average either into a universal score.

Evidence confidence is the minimum evidence strength across applicable hard gates: E3/E4 everywhere -> High; any E2 on a critical gate -> Moderate; any E0/E1 on a critical gate -> Low. Never let confidence turn a FAIL into a PASS.

## Apply domain overlays
Infer domain overlays only from evidence in the repository or user-provided context. Read [references/domain-overlays.md](references/domain-overlays.md) for any applicable overlay. A generic rubric is not allowed to suppress mandatory domain-specific obligations.

## Adversarially attack the apparent result
Each rubric gate's "Defeaters" list is the falsification checklist; before the verdict, work through it for every apparent PASS, especially critical gates, and close with the rubric's final-challenge question. For each serious defeater, either identify evidence that bounds/refutes it, downgrade the gate/evidence rating, or record it as an explicit residual risk. Do not silently ignore a plausible defeater.

## Make the decision
Use the following non-compensable decision rules:
- **READY**: every applicable hard gate passes; no material unknown prevents the claimed exposure; critical claims have sufficiently direct, representative evidence; residual risks are explicit and acceptable to the identified decision authority.
- **CONDITIONALLY READY**: no hard gate is actually failed for the **strictly bounded** exposure; remaining gaps are noncritical within that boundary and have explicit compensating controls, stop criteria, owners, and expiry/reassessment conditions where appropriate. Never use this as a softer label for a failed hard gate.
- **NOT READY**: any applicable hard gate fails, or a material unknown prevents a defensible readiness claim for the proposed exposure.

A condition never converts a failed applicable hard gate: if any applicable hard gate is FAIL, the verdict is NOT READY regardless of bounding. A legal, safety, regulatory, privacy, or other mandatory requirement cannot be waived by a score; a formal exception is relevant only when policy permits it and the evidence identifies the authorized risk owner, scope, compensating controls, and expiry/review point. If the evidence would support a narrower exposure than requested, state that explicitly (for example, "not ready for GA; evidence may support a 1% internal canary subject to ...") rather than weakening the GA standard.

## Produce the report
Read [references/output-template.md](references/output-template.md) immediately before writing the final report. The report's first lines, before any other text, must be the machine-checkable block verbatim: `VERDICT: READY` (or `CONDITIONALLY READY` or `NOT READY`), then one `GATE G1: PASS|FAIL|UNKNOWN|N/A` line per gate through `GATE G12: ...`, each value matching that gate's status in the hard-gate table exactly. These lines are not decorative: they are the machine-graded record of the decision, so never disagree with, omit, or abbreviate them, and do not also print a separate prose `**Verdict:**` line. Cite repository evidence as `path:line` where practical and command evidence by exact command plus exit status. Distinguish blockers from recommendations. Every section of the template is required; a complete G1-G12 gate table and D1-D13 ratings are never abbreviated.

For the methodological provenance of this rubric, consult [references/source-basis.md](references/source-basis.md) only when the user asks why a criterion exists, requests literature support, or asks to revalidate the rubric against current standards.
