---
name: production-readiness-review
description: Evaluate whether the current repository or release candidate is production-ready using evidence-backed hard gates, risk-relative readiness dimensions, and adversarial failure analysis. Use when asked whether a repo, service, app, feature, PR, branch, build, or release is ready to ship, launch, deploy, go live, hand to operations, or reach GA; for production/release/operational readiness reviews, release gates, go/no-go decisions, launch audits, or identifying blockers to production. Also use when explicitly asked to verify that the current repo is complete and safe for production. Do not use for ordinary code review, debugging, test writing, architecture discussion, or deployment execution unless a readiness judgment is requested.
---

# Production Readiness Review

Perform a read-only, evidence-first production readiness audit of the current repository or the release scope named by the user. Judge a specific candidate for a specific production exposure. Never equate repository quality, test success, or feature completeness with production readiness by itself.

## Core rules

1. Inspect before judging. Treat repository files, version-control state, command results, and user-supplied operational evidence as evidence. Separate **observed**, **inferred**, and **unknown** facts.
2. Use hard gates before graded dimensions. An applicable hard-gate failure cannot be compensated by strengths elsewhere.
3. Do not award execution evidence for documentation alone. A backup is not recovery evidence until a restore is exercised; a dashboard is not operability evidence until detection and response are demonstrated; redundancy is not failover evidence until failure behavior is exercised or otherwise directly established.
4. A passing test supports only the behavior and conditions it actually tests. Do not generalize from coverage percentage, test count, a green CI badge, a scanner result, average latency, historical uptime, or a process label.
5. Prefer candidate-specific, recent, traceable, representative, reproducible evidence. When evidence conflicts, prefer stronger and more direct evidence; explain the conflict.
6. Do not infer external operational facts from repository absence or presence. On-call staffing, cloud configuration, recovery drills, production traffic, regulatory approval, and live SLO attainment may be impossible to prove from a repo. Mark them unknown unless direct evidence is available.
7. Keep the audit read-only with respect to source, infrastructure, and remote systems. Do not edit project files, install dependencies, deploy, apply infrastructure, run production migrations, rotate secrets, create releases, push commits, or mutate remote services. Local build/test commands may create ordinary temporary build artifacts or caches when the project's own workflow normally does so.
8. Do not expose secrets. Never print secret values, private keys, tokens, credentials, or environment-variable contents in the report.
9. If current external facts materially affect readiness (for example an EOL dependency, active vulnerability, current regulation, or provider limit), verify them from authoritative sources when web access is available. Otherwise state that external freshness was not verified.
10. Do not force a universal numerical cutoff. Report the hard-gate decision and the two independent axes of readiness state and evidence strength.

## Scope the claim

Before collecting evidence, establish as much of the following as the available evidence permits:

- Candidate identity: repository root, branch, commit, dirty working-tree status, artifact/version if known.
- Target exposure: users/tenants, regions, traffic percentage, feature surface, data sensitivity, availability expectations, and whether the claim is canary, limited release, or GA.
- Critical journeys: the behaviors whose incorrectness or unavailability would make the release unacceptable.
- Environment boundary: what is in scope (application, infrastructure, dependencies, data stores, clients, operators) and what is external.

If the user does not specify an exposure, use the current working tree as the **source candidate under review**, but do not invent a deployable artifact or production operating envelope. Record those as unknown and judge only what the available evidence supports.

## Collect deterministic repository signals

When Python 3 is available, run the bundled read-only probe before deep inspection:

```bash
python3 "${CLAUDE_SKILL_DIR}/scripts/repo_probe.py" "${CLAUDE_PROJECT_DIR}"
```

If `python3` is unavailable, continue without it. The probe is a discovery aid, not readiness evidence by itself. Read the relevant files it identifies and corroborate important claims.

Then inspect, as applicable:

- manifests, lockfiles, build definitions, release metadata, and generated-artifact/provenance mechanisms;
- test layout, test configuration, CI workflows, quality gates, and critical-journey tests;
- deployment definitions, infrastructure-as-code, migrations, feature flags, rollout/rollback logic, and environment configuration strategy;
- monitoring, alerts, SLO/SLI definitions, health/readiness checks, dashboards-as-code, runbooks, incident/playbook material, backup/restore and disaster-recovery evidence;
- threat models, authorization/security tests, dependency/supply-chain controls, secret handling, SBOM/provenance, privacy/data classifications;
- capacity/load/soak/failure tests and dependency timeout/retry/circuit-breaking behavior;
- ownership, support, escalation, handover, deprecation/retirement, licensing, accessibility, and domain-specific assurance material.

For large repositories, dispatch read-only evidence collection in one batch and keep gate synthesis and the final verdict with the primary auditor:

- `engineering:scout`: locate test, CI, deployment, migration, operations, observability, and security files the probe did not surface, returning paths only.
- `engineering:security-reviewer`: collect evidence for gate G3 (authentication, authorization, secrets, dependency and supply-chain controls, trust boundaries) and report findings as evidence with `path:line`, not as a verdict.
- `engineering:semantic-reviewer`: examine the critical-journey tests for gate G2 and report weak oracles, mocked contracts, and untested failure modes.

All three are read-only by tool list. Their output is evidence to be weighed under the rubric; none of them decides a gate.

## Run high-value validation safely

Prefer commands already declared by the repository's CI, task runner, package manager, or contributor documentation. Run only commands that are safe in the local audit environment and do not require installing new dependencies or mutating remote/prod systems.

Prioritize, when present and feasible:

1. build/reproducibility checks;
2. unit, integration, contract, end-to-end, migration, and regression tests relevant to critical journeys;
3. lint/type/static-analysis checks when they guard real defects;
4. project-configured security/dependency/secret/supply-chain checks;
5. local smoke tests and performance/failure checks that are already part of the project and safe to execute.

Record the exact command, exit status, candidate identity, and important limitations. A command that cannot run because of missing credentials, services, hardware, dependencies, or environment fidelity is **unverified**, not passed.

## Apply the rubric

Read [references/rubric.md](references/rubric.md) before assigning gate decisions. Evaluate all 12 hard gates and all 13 readiness dimensions that are applicable.
Consult [references/evidence-protocol.md](references/evidence-protocol.md) whenever a material claim depends on documentation, command output, indirect evidence, missing evidence, or conflicting evidence.

Use these states for hard gates:

- **PASS** - the gate's material claims are supported strongly enough for the proposed exposure.
- **FAIL** - direct evidence shows the gate is not satisfied.
- **UNKNOWN** - material evidence is missing, stale, ambiguous, or cannot be verified.
- **N/A** - demonstrably not applicable; include a short rationale.

Use separate evidence strength:

- **E0** - no usable or traceable evidence.
- **E1** - assertion, plan, policy, or documentation only.
- **E2** - direct evidence, but partial, stale, nonrepresentative, or not candidate-specific.
- **E3** - recent, traceable, repeatable, representative, candidate-specific evidence.
- **E4** - independently reproduced and/or demonstrated under bounded real-production or realistic adverse conditions.

Use readiness state for each graded dimension:

- **0 Unknown/absent**
- **1 Ad hoc**
- **2 Defined but incompletely demonstrated**
- **3 Validated for the candidate under representative conditions**
- **4 Robustly demonstrated at realistic scale and adverse conditions**

Do not average these into a universal score.

## Apply domain overlays

Infer domain overlays only from evidence in the repository or user-provided context. Read [references/domain-overlays.md](references/domain-overlays.md) for any applicable overlay. A generic rubric is not allowed to suppress mandatory domain-specific obligations.

## Adversarially attack the apparent result

Before the verdict, read [references/adversarial-checks.md](references/adversarial-checks.md). Try to falsify every apparent PASS, especially critical gates. Look for stale evidence, candidate drift, test-oracle weaknesses, staging/production mismatch, shared-fate redundancy, rollback fiction, retry amplification, restore gaps, alert/runbook theater, metric gaming, organizational single points of failure, time-bomb dependencies, cost cliffs, and omitted domain obligations.

For each serious defeater, either:

- identify evidence that bounds/refutes it;
- downgrade the gate/evidence rating; or
- record it as an explicit residual risk.

Do not silently ignore a plausible defeater.

## Make the decision

Use the following non-compensable decision rules:

- **READY**: every applicable hard gate passes; no material unknown prevents the claimed exposure; critical claims have sufficiently direct, representative evidence; residual risks are explicit and acceptable to the identified decision authority.
- **CONDITIONALLY READY**: no hard gate is actually failed for the **strictly bounded** exposure; remaining gaps are noncritical within that boundary and have explicit compensating controls, stop criteria, owners, and expiry/reassessment conditions where appropriate. Never use this as a softer label for a failed hard gate.
- **NOT READY**: any applicable hard gate fails, or a material unknown prevents a defensible readiness claim for the proposed exposure.

A legal, safety, regulatory, privacy, or other mandatory requirement cannot be waived by a score. A formal exception is relevant only when the applicable policy permits it and the evidence identifies the authorized risk owner, scope, compensating controls, and expiry/review point.

If the evidence would support a narrower exposure than the one requested, state that explicitly (for example, "not ready for GA; evidence may support a 1% internal canary subject to ...") rather than weakening the GA standard.

## Produce the report

Read [references/output-template.md](references/output-template.md) immediately before writing the final report. Cite repository evidence as `path:line` where practical and command evidence by exact command plus exit status. Distinguish blockers from recommendations.

Always include:

- verdict, audit scope, candidate identity, target exposure, and confidence;
- blocking findings first;
- a complete G1-G12 gate table with status and evidence strength;
- D1-D13 dimension ratings for applicable dimensions;
- commands/evidence actually inspected or executed;
- adversarial challenges and how they were resolved;
- unknowns and external facts not verified;
- ordered actions required before READY;
- residual risks and a decision record for READY or CONDITIONALLY READY.

For the methodological provenance of this rubric, consult [references/source-basis.md](references/source-basis.md) only when the user asks why a criterion exists, requests literature support, or asks to revalidate the rubric against current standards.
