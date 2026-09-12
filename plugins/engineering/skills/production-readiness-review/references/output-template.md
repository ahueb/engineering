# Readiness Report Output Contract

Adapt prose length to the repository, but preserve this decision structure.

# Production Readiness Review

**Verdict:** READY | CONDITIONALLY READY | NOT READY  
**Evidence confidence:** High | Moderate | Low  
**Candidate:** commit/artifact/branch + dirty status  
**Proposed exposure:** exact exposure, or "not specified"  
**Audit boundary:** what was and was not inspected

## Executive decision

In 1-3 paragraphs:
- state the decision and the strongest evidence;
- state the decisive blockers/unknowns;
- if narrower exposure is supportable, distinguish it from the requested exposure.

## Blocking findings

Put actual blockers first. Use stable IDs such as `PRR-B01`.

| ID | Gate | Finding | Evidence | Why it blocks |
|---|---|---|---|---|

If there are no blockers, say so; do not invent findings.

## Hard-gate decision

| Gate | Status | Evidence | Key evidence / rationale |
|---|---|---|---|
| G1 Candidate identity & provenance | PASS/FAIL/UNKNOWN/N/A | E0-E4 | ... |
| G2 Critical functional correctness | ... | ... | ... |
| G3 Security/privacy/supply chain | ... | ... | ... |
| G4 Data integrity & recoverability | ... | ... | ... |
| G5 Safe deployment & reversion | ... | ... | ... |
| G6 Observability & alertability | ... | ... | ... |
| G7 Operational ownership & incident response | ... | ... | ... |
| G8 Capacity & performance | ... | ... | ... |
| G9 Resilience & dependency failure | ... | ... | ... |
| G10 Continuity / disaster recovery | ... | ... | ... |
| G11 Known-risk closure | ... | ... | ... |
| G12 Mandatory domain obligations | ... | ... | ... |

Every N/A requires a rationale. Every material UNKNOWN must be reflected in the verdict.

## Readiness dimensions

| Dimension | State | Evidence | Main observation |
|---|---:|---|---|
| D1 Functional suitability | 0-4 | E0-E4 | ... |
| D2 Quality in use / UX / accessibility | ... | ... | ... |
| D3 Reliability / availability / recovery | ... | ... | ... |
| D4 Performance / capacity / efficiency | ... | ... | ... |
| D5 Security / privacy / supply chain | ... | ... | ... |
| D6 Observability / diagnostics | ... | ... | ... |
| D7 Operations / incident response / continuity | ... | ... | ... |
| D8 Release / change / migration safety | ... | ... | ... |
| D9 Architecture / dependencies / blast radius | ... | ... | ... |
| D10 Maintainability / testability | ... | ... | ... |
| D11 Ownership / staffing / governance | ... | ... | ... |
| D12 Economic / resource sustainability | ... | ... | ... |
| D13 Safety / compliance / domain assurance | ... | ... | ... |

Use N/A sparingly where the dimension truly cannot apply; explain material omissions.

## Validation performed

List exact commands and outcomes. Example:

| Command | Exit | What it establishes | Limitations |
|---|---:|---|---|
| `...` | 0 | ... | ... |

Also list important files/evidence inspected, using `path:line` where practical.

## Adversarial challenge results

For the most important apparent PASSes, record the attempted defeater and resolution:

| Challenge | Result | Evidence / consequence |
|---|---|---|
| Candidate drift | Refuted / residual / blocker | ... |

Do not dump the entire checklist when items are irrelevant.

## Unknowns and unverified external facts

Explicitly include:
- production-only configuration not visible locally;
- operational/staffing claims not directly evidenced;
- current external vulnerability/EOL/regulatory/provider facts not verified;
- tests that could not execute and why;
- environment-fidelity limits.

## Actions required before READY

Order by decision impact, not convenience. For each:

1. **Action** - concrete change or evidence to produce.
   - Closes: gate/finding ID.
   - Acceptance evidence: what a reviewer must see to mark it resolved.
   - Owner: use known owner, otherwise `unassigned` (do not invent one).

## Residual risk and bounded release conditions

For READY/CONDITIONALLY READY, record each material residual with:
- risk;
- exposure boundary;
- compensating control;
- stop/rollback trigger;
- owner/decision authority if known;
- expiry/reassessment trigger.

## Decision record

Include:
- candidate/environment identity;
- exact approved exposure;
- decision;
- critical residual risks;
- rollout stop criteria;
- rollback/recovery trigger;
- early-life support expectations;
- reassessment trigger;
- risk-acceptance authority (or `unknown`).

End with one sentence answering: **What would have to change for this verdict to change?**
