# Output-behavior scenarios

Fresh-session scenarios for judging audit quality. Each needs a representative repository; grade against the expectations listed.

## 1. Audit the current repository for GA production readiness. The repo has strong unit tests and CI, but do not assume any external operational controls that are not evidenced.

**Expected:** A gate-first readiness report that refuses to equate green CI with production readiness, explicitly marks material external operational evidence as UNKNOWN when absent, and returns NOT READY if those unknowns are necessary for GA.

Expectations:
- Reports G1-G12 with PASS/FAIL/UNKNOWN/N/A and E0-E4 evidence strength.
- Separates observed repository facts from inferred or unknown production facts.
- Does not invent on-call, restore, DR, live monitoring, or production configuration evidence.
- Does not average dimensions into a universal readiness score.

## 2. Do a readiness review. The repository says backups are enabled and contains a restore runbook, but there is no restore-drill output or other direct recovery evidence.

**Expected:** The audit treats backup configuration and a restore runbook as evidence that controls/procedures exist, not proof that recovery works; G4/G10 remain appropriately UNKNOWN or fail if an explicit recovery criterion is unmet.

Expectations:
- Distinguishes documentation from exercised recovery evidence.
- Attempts the backup-illusion and restore-dependency adversarial checks.
- States what acceptance evidence would close the gap.

## 3. Judge a release that has 95% code coverage, zero findings from one SAST scanner, and excellent average latency, but no evidence about critical-journey semantic correctness, authorization abuse cases, tail latency, or rollback after schema migration.

**Expected:** The audit rejects proxy-metric theater, identifies weak/unknown evidence in correctness, security, performance, and release/reversion gates, and does not allow high coverage/scanner cleanliness/averages to compensate.

Expectations:
- Challenges code coverage as a standalone proxy.
- Challenges scanner equivalence and business-logic authorization gaps.
- Requires p95/p99 or otherwise appropriate tail/peak evidence rather than averages alone.
- Detects rollback fiction for schema/data changes.

## 4. Assess whether a service that is not ready for GA could safely run as a 1% internal canary behind a kill switch. Make the release boundary explicit.

**Expected:** The audit may return CONDITIONALLY READY only for the strictly bounded canary if no hard gate fails within that boundary and explicit controls, stop criteria, owner, and reassessment/expiry are present; it must still say not ready for GA.

Expectations:
- Does not weaken GA criteria to obtain a conditional verdict.
- Records the precise exposure boundary and rollback/stop trigger.
- Requires explicit ownership and reassessment conditions for material residual risk.

## 5. Review an AI-enabled service for production readiness. Its normal web-service controls are strong, but model versioning, evaluation slices, prompt-injection/tool-abuse tests, provider fallback, and model cost ceilings are not evidenced.

**Expected:** The audit activates the AI/ML domain overlay and treats missing AI-specific evidence as material rather than declaring the system ready from generic web-service controls alone.

Expectations:
- Applies G12 domain obligations and AI/ML overlay checks.
- Considers model/prompt/tool/data versioning, evaluations, agentic abuse, provider dependency, and cost.
- Explains which gaps are blockers versus residual risks for the proposed exposure.

## 6. Adversarially review an apparently mature multi-region service. Architecture docs say it is highly available, but determine whether shared dependencies, failover exercises, control-plane access, alert routing, and operator capability are actually evidenced.

**Expected:** The audit attempts to falsify HA claims using shared-fate, failover, alert-dead-end, runbook-theater, and organizational-SPOF checks; labels architecture claims E1/E2 unless exercised/direct evidence supports them.

Expectations:
- Does not treat the label multi-region as failover evidence.
- Looks for shared failure domains and exercised failover/recovery evidence.
- Separates monitoring configuration from actionable operator response capability.
