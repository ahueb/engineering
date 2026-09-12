# Domain Overlays

Apply only overlays supported by repository/user context. These add requirements; they never remove generic hard gates.

## Data-intensive systems

Add checks for:
- data lineage and source-of-truth ownership;
- schema and semantic contracts, not just syntactic schema;
- freshness/completeness/uniqueness/validity expectations as relevant;
- reconciliation and detection of silent partial processing;
- idempotency, replay, backfill, and late/out-of-order data behavior;
- partition/time-zone/encoding/identifier edge cases;
- reproducibility of transformations and model/features derived from data;
- retention, deletion, export, backup copies, and privacy propagation;
- reprocessing capacity and recovery from corrupt intermediates.

## AI/ML and agentic systems

Add checks for:
- exact model, prompt, tool, policy, retrieval corpus, and data versioning;
- representative evaluation sets and slice-level performance;
- harmful failure modes and misuse/abuse testing;
- drift/change detection and reevaluation triggers;
- human oversight/override where consequence warrants it;
- provider/model availability, rate limits, latency, cost, fallback, and version changes;
- prompt injection, tool abuse, data exfiltration, excessive agency, unsafe action boundaries, and permission minimization for agentic systems;
- reproducibility limits for stochastic outputs and acceptance criteria appropriate to them;
- bias/fairness and transparency requirements when applicable to the use case;
- rollback/fallback when model or retrieval quality degrades.

Do not claim compliance with an AI governance framework solely from technical tests.

## User-facing web/mobile/desktop clients

Add checks for:
- WCAG/accessibility obligations and automated + manual evidence appropriate to the UI;
- supported browser/OS/device matrix;
- responsive layout and input modes;
- slow/offline/degraded network behavior;
- client/server version skew during rollout;
- safe update mechanism and rollback where relevant;
- localization/time-zone/encoding/date handling when applicable;
- telemetry/privacy consent and user-data handling.

## Public APIs, SDKs, libraries, and CLIs

Add checks for:
- compatibility/versioning policy;
- documented contracts and machine-readable schemas where useful;
- backwards/forwards compatibility and deprecation window;
- rate/size/concurrency limits and stable error semantics;
- authentication examples that do not encourage unsafe patterns;
- package/signing/provenance and dependency-minimization concerns;
- install/upgrade/uninstall behavior across supported environments;
- release notes and migration guidance for breaking changes.

## Infrastructure/platform/operator tooling

Add checks for:
- blast radius and permission boundaries;
- dry-run/plan/preview and confirmation behavior for destructive actions;
- idempotency and partial-failure recovery;
- locking/concurrency controls;
- credential and audit-log handling;
- safe defaults and guardrails against wrong-account/wrong-region/wrong-cluster actions;
- control-plane dependency and break-glass paths;
- version skew and upgrade order.

## Financial/payment systems

Add checks for:
- exact monetary arithmetic/rounding/currency rules;
- idempotency and duplicate prevention;
- reconciliation and ledger invariants;
- authorization/fraud/chargeback paths;
- auditability and immutable evidence where required;
- applicable financial/payment regulatory and contractual obligations;
- failure semantics for partial external processor outcomes.

## Scientific/analytical software

Add checks for:
- numerical correctness and precision/stability;
- independent comparison against known/reference results;
- unit/coordinate/reference-build/normalization assumptions;
- provenance and reproducibility of data + parameters + environment;
- sensitivity analysis where results depend on thresholds/initialization;
- detection of invalid scientific assumptions, not only software exceptions;
- versioned algorithms and output schemas;
- validation appropriate to downstream decision consequence.

## Medical, safety-critical, embedded, and real-time systems

A generic rubric is insufficient by itself. Add the applicable regulated/safety lifecycle and independent assurance, which may include:
- hazard analysis and traceability from hazards to controls/tests;
- safety requirements and independence of verification;
- timing/resource/worst-case behavior;
- fail-safe/degraded-safe state;
- hardware/environmental fault assumptions;
- configuration/change control and audit records;
- required quality-system, regulatory, certification, or post-market obligations.

If applicability or mandatory requirements cannot be determined, G12 is UNKNOWN and READY is not defensible for the regulated/safety-critical exposure.
