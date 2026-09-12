# Production Readiness Rubric

Use this reference to make the gate and dimension judgments. It is a synthesis, not a verbatim reproduction of any one standard or vendor checklist.

## Decision principle

Production readiness is assurance for a specific **release-context pair**. The object under review is not merely source code: it includes the deployable candidate, configuration, data/migrations, dependencies, operating environment, observability, recovery mechanisms, operators, support process, and mandatory obligations relevant to the proposed exposure.

Hard gates are non-compensable. Graded dimensions provide diagnostic depth after or alongside the gate decision; they never override a failed gate.

## Hard gates

### G1 Candidate identity and provenance

**Question:** Is the exact thing being judged identifiable, reproducible, and traceable to what will be deployed?

Look for:
- commit/artifact/version identity;
- clean or explicitly accounted-for working-tree differences;
- deterministic or controlled build inputs and lockfiles;
- configuration/schema/IaC version linkage;
- artifact integrity/provenance/SBOM where risk warrants it;
- promotion rules that prevent testing one candidate and deploying another;
- source integrity (protected history, required review) as distinct from build provenance;
- where an SBOM is claimed, its contents: component name, version, supplier, hash, license, dependency relationship, generation timestamp and tool, known unknowns.

Defeaters:
- tests executed against a different commit/artifact;
- undocumented manual build or production-only patching;
- mutable/unpinned critical dependencies without bounded policy;
- unknown production configuration or schema version;
- dirty working tree or generated file substituted between test and deploy (candidate drift).

### G2 Critical functional correctness

**Question:** Do the critical user/mission journeys satisfy explicit acceptance criteria under relevant normal and edge conditions?

Look for:
- identified critical journeys and requirements;
- direct tests with meaningful oracles;
- negative/edge/error-path and regression coverage;
- integration/contract behavior where dependencies matter;
- candidate-specific execution results.

Defeaters:
- critical behavior untested or known incorrect;
- tests assert transport success but not semantic/business correctness;
- important manual assumptions without evidence;
- unresolved defects that can violate acceptance criteria;
- green suite omits a critical journey, concurrency condition, or integration boundary (green-test false assurance);
- test mocks the exact component whose contract is at risk (weak oracle);
- high coverage used as a proxy while critical behavior stays unexercised (coverage theater);
- flaky, disabled, or quarantined tests suppress a real signal on a critical path (flake masking).

### G3 Security, privacy, and supply chain

**Question:** Are material attack, authorization, privacy, secret, dependency, build, and abuse risks acceptably controlled for this exposure?

Look for:
- threat/trust-boundary analysis proportional to risk;
- authentication and authorization tests, including object/business-logic boundaries;
- secret handling and least privilege;
- dependency and included-code verification;
- build provenance/integrity where relevant;
- privacy/data classification, minimization, retention, encryption, and access controls;
- abuse/rate-limit protections where relevant;
- current vulnerability disposition, not scanner output alone;
- CI token permissions minimized, branch protection and required checks, signed releases or attestations, vulnerability reporting path.

Defeaters:
- exploitable critical/high-impact vulnerability without accepted mitigation;
- material authorization path not verified;
- credentials/secrets embedded or uncontrolled;
- unknown handling of sensitive data;
- mandatory security/privacy requirement unmet;
- clean dependency/SAST/DAST scan coexists with broken object or business-logic authorization (scanner equivalence);
- a queue, admin path, webhook, build runner, or AI tool wrongly treated as trusted (trust-boundary omission);
- source/build/dependency provenance can be substituted or tampered with after verification (supply-chain gap);
- deletion, retention, export, backup copies, or support access unaddressed after collection/encryption (privacy lifecycle gap).

### G4 Data integrity and recoverability

**Question:** Can state be preserved, migrated, restored, reconciled, and recovered within required limits?

Look for:
- data model/schema compatibility;
- migration rehearsal and failure handling;
- backup scope, retention, integrity, encryption, and restore evidence;
- measured RPO/RTO where applicable;
- reconciliation/idempotency and replay semantics;
- data corruption/loss detection;
- restore test recency relative to the last schema or storage change;
- sampled-restore evidence with a date.

Defeaters:
- backups exist but restore has not been demonstrated where recovery is material;
- destructive migration with no tested recovery/forward-fix path;
- unknown RPO/RTO against explicit business needs;
- irreversible external side effects ignored by rollback plans;
- restore would fail because encryption keys, control-plane services, credentials, or human access are unavailable in the same disaster (restore dependency trap);
- old and new application versions cannot safely coexist during rollout, with unbounded locks, backfills, or retries (migration trap).

### G5 Safe deployment and reversion

**Question:** Is change introduction repeatable, bounded, observable, stoppable, and recoverable?

Look for:
- automated/repeatable deployment path;
- environment/config validation;
- staged rollout, canary, feature flags, or other blast-radius controls as warranted;
- rollback or forward-recovery strategy including schema/data/external effects;
- pre/post-deploy checks and stop criteria;
- tested rollback/recovery mechanics;
- upgrade→downgrade→upgrade tested where version skew is possible;
- a named metric that triggers rollback;
- an emergency change path that is tested and audited.

Defeaters:
- one-shot manual production procedure;
- rollback assumes code-only reversibility;
- no stop condition for progressive rollout;
- deployment path materially differs from the tested path without evidence;
- rollback's version-skew re-enable path is untested or its trigger metric is undefined (rollback fiction);
- runtime flags, secrets, quotas, schema, or feature toggles are not versioned/promoted consistently with code (configuration divergence);
- staging/local success may not represent production due to topology, scale, data, or dependency differences (environment-fidelity gap).

### G6 Observability and alertability

**Question:** Can important user-impacting failure be detected, localized, and acted on quickly enough?

Look for:
- user/business-facing SLIs as well as infrastructure health;
- logs/metrics/traces or equivalent diagnostics appropriate to the system;
- actionable alerts tied to symptoms/SLOs, with ownership;
- synthetic/critical-journey checks where appropriate;
- diagnostic correlation and safe data handling;
- evidence alerts and dashboards actually function;
- SLO target with owner, approval date, and an error-budget consequence.

Defeaters:
- only host/process health while incorrect business output can remain green;
- dashboards with no actionable alerting;
- alerts without owner/runbook/escalation;
- observability exists only in staging when production is the claim;
- alert reaches no one with access, authority, context, or a tested next action (alert dead end).

### G7 Operational ownership and incident response

**Question:** Can identifiable operators support, diagnose, stop, recover, and communicate during incidents?

Look for:
- named service ownership and escalation paths;
- on-call/support coverage proportional to need;
- production access and break-glass procedures;
- exercised runbooks/playbooks;
- incident communication/severity process;
- training/handover and staffing depth;
- post-incident learning loop.

Defeaters:
- no accountable owner;
- runbook exists but operators cannot execute it under incident conditions;
- single-person recovery knowledge for a critical service;
- missing production access or escalation path;
- a quiet incident history is treated as reliability proof despite low traffic or no failure exercises (no-incidents fallacy).

### G8 Capacity and performance

**Question:** Does the candidate meet latency, throughput, concurrency, resource, and growth needs with adequate headroom?

Look for:
- explicit performance/capacity objectives;
- representative peak, burst, and concurrency tests;
- tail latency, saturation, queueing, resource ceilings, storage growth;
- dependency/provider quotas;
- degradation behavior and autoscaling limits;
- cost/resource implications at target scale.

Defeaters:
- only average latency or nominal-load testing;
- capacity ceiling unknown near expected demand;
- unbounded queues/storage/cardinality;
- critical provider quota below plausible demand;
- target capacity inferred from a much smaller test without validated scaling behavior (capacity extrapolation);
- autoscaling, cardinality, egress, or retry storms produce unacceptable cost before technical saturation (cost cliff).

### G9 Resilience and dependency failure

**Question:** Are foreseeable component/dependency failures isolated, bounded, and recoverable without unacceptable cascading impact?

Look for:
- dependency inventory and criticality;
- timeouts, bounded retries/backoff/jitter, circuit breaking/load shedding as appropriate;
- failure isolation and blast-radius design;
- degraded-mode behavior;
- failover/fault tests or direct evidence;
- shared-fate analysis for redundant components;
- a failure-mode analysis artifact for critical journeys;
- distinguish fault injection exercised in a representative environment (E3) from staging-only (E2).

Defeaters:
- unbounded retry amplification;
- nominal redundancy sharing a decisive failure domain;
- single dependency outage cascades without bounded response;
- failover exists only on architecture diagrams;
- system behaves unsafely when a dependency is slow, stale, or returns invalid data rather than cleanly down (partial failure);
- queues, retries, dead letters, or temporary files grow without bound during degradation (queue/backlog runaway).

### G10 Continuity and disaster recovery

**Question:** For consequences that warrant it, can the service/business recover from site, region, account, control-plane, or systemic loss?

Look for:
- continuity/DR objectives linked to business impact;
- recovery architecture and dependency assumptions;
- exercised failover/restore/rebuild procedures;
- alternate access/control paths;
- measured recovery time/data loss;
- communication and decision authority during disaster.

Use N/A only when the impact/risk genuinely makes dedicated continuity controls unnecessary and the rationale is explicit.

Defeaters:
- failover only on diagrams;
- unmeasured RTO/RPO;
- shared control plane or account between primary and recovery;
- recovery never rehearsed end to end.

### G11 Known-risk closure

**Question:** Are known defects, anomalies, exceptions, flaky checks, operational gaps, and residual risks understood and dispositioned?

Look for:
- blocker/critical defect inventory;
- flaky/disabled test disposition;
- risk register or equivalent for material residuals;
- exception owner, scope, mitigation, expiry/review;
- unexplained anomalies investigated;
- release stop criteria tied to known risks.

Defeaters:
- unexplained critical test/production anomaly;
- ignored disabled/flaky test on a critical path;
- overdue exception or residual risk without owner;
- material "we think it is fine" assumption without evidence;
- certificates, tokens, quotas, licenses, or provider deprecations will fail later despite launch success (time-bomb dependency);
- dependencies, runtime, or data cannot be upgraded, exported, or retired without unsafe manual work (upgrade/retirement gap).

### G12 Mandatory domain obligations

**Question:** Are all applicable legal, regulatory, contractual, safety, accessibility, licensing, policy, and domain-specific requirements satisfied?

Look for:
- evidence that applicable obligations were identified;
- required approvals/certifications/reviews;
- license/notice obligations;
- accessibility requirements for user-facing systems;
- domain assurance for medical, financial, safety, scientific, real-time, AI, data, or other specialized systems;
- change authorization and audit record where SOC 2 CC8.1 or ISO 27001 A.8.32 is in scope;
- EU CRA vulnerability-handling and reporting obligations where the product is sold in the EU.

Defeaters:
- mandatory requirement not met;
- applicability has never been assessed for a high-consequence domain;
- generic software checklist used to waive domain-specific assurance;
- the same team relies mainly on its own assertions without independent reproduction or review (reviewer capture);
- a metric such as coverage, deployment frequency, or uptime is optimized while real outcomes worsen (Goodhart/metric gaming).

## Readiness dimensions

Score each applicable dimension on the 0-4 readiness-state axis and E0-E4 evidence axis from SKILL.md. Do not average into a universal production score.

### D1 Functional suitability and critical-journey correctness
Completeness, correctness, business rules, edge/error cases, contracts, critical outcomes.

### D2 Quality in use, UX, and accessibility
User task success, usability, accessibility, error protection/recovery, client/device compatibility, documentation for intended users.

### D3 Reliability, availability, durability, and recovery
SLOs, failure rates, durability, failover, restore, RTO/RPO, graceful degradation, reliability under sustained operation.

### D4 Performance, capacity, scalability, and resource efficiency
Tail latency, throughput, concurrency, load shape, saturation, headroom, scaling limits, storage/resource growth.

### D5 Security, privacy, abuse resistance, and supply-chain integrity
Threats, identity, authorization, secrets, dependencies, build integrity, data protection, abuse/fraud paths.

### D6 Observability, diagnostics, and production feedback
User-impact signals, logs, metrics, traces, synthetic checks, alert quality, diagnostic usability, feedback loops.

### D7 Incident response, operations, and business continuity
Ownership, on-call/support, runbooks, escalation, drills, incident communication, recovery, continuity.

### D8 Release, change, configuration, and migration safety
CI/CD, artifact promotion, IaC/config, staged rollout, feature flags, rollback/forward fix, schema and client compatibility.

### D9 Architecture, dependencies, interoperability, and blast radius
Coupling, failure domains, critical dependencies, retries/timeouts, limits/quotas, compatibility, isolation.

### D10 Maintainability, testability, and technical sustainability
Modularity, testability, reviewability, upgrade path, reproducibility, technical debt, operability of future change.

### D11 Ownership, staffing, governance, and long-term support
Bus factor, accountable owners, staffing depth, training, handover, risk authority, lifecycle/retirement ownership.

### D12 Economic and resource sustainability
Cloud/runtime cost, observability/storage cardinality, licenses, quotas, vendor limits, operational labor, predictable scaling economics, cost anomaly alerting, and a unit-economics forecast at target scale.

### D13 Safety, compliance, and domain-specific assurance
Hazards, regulatory constraints, scientific/numerical validity, accessibility, auditability, specialized independent verification.

## Conditions

Record for each condition attached to a CONDITIONALLY READY verdict: exact exposure boundary; compensating control; stop/rollback trigger; accountable owner; expiry or reassessment event.
See SKILL.md for the verdict, confidence, and condition-conversion decision rules.

## Final challenge

For every gate marked PASS, ask:
> What realistic event would make this claim false, and what direct evidence shows that event is prevented, bounded, detected, or recoverable?

If the answer is only an assertion, plan, architecture label, or proxy metric, downgrade the evidence strength and reconsider the gate.
