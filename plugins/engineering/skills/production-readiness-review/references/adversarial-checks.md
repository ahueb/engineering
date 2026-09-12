# Adversarial Readiness Checks

Use these as attempted falsifications of apparent readiness. Do not mechanically require every item; select those plausible for the system and exposure.

## Candidate and environment

### Candidate drift
Could the artifact deployed differ from the artifact tested because of an unpinned dependency, mutable tag, manual build step, generated file, production-only patch, or dirty working tree?

### Environment-fidelity gap
Could staging/local success fail to represent production due to topology, scale, identity, data, provider, kernel/runtime, feature flag, configuration, network, or dependency differences?

### Configuration divergence
Are runtime flags, secrets, quotas, schema, feature toggles, or infrastructure parameters versioned and promoted consistently with code?

## Correctness and testing

### Green-test false assurance
Do tests omit a critical journey, failure mode, integration boundary, concurrency condition, or data shape?

### Weak oracle
Can the test pass while the user/business result is wrong? Examples: asserting HTTP 200 instead of semantic output, snapshotting malformed behavior, mocking the component whose contract is actually at risk.

### Coverage theater
Would a high coverage percentage remain possible while critical behavior is untested? Is coverage being used as a proxy for effectiveness rather than a locator for missing exercised code?

### Flake masking
Are flaky/disabled/quarantined tests suppressing a real signal? Are retries hiding nondeterminism on critical paths?

## Deployment and data

### Rollback fiction
Does rollback cover only code while migrations, queues, caches, external side effects, irreversible writes, or incompatible clients remain changed?

### Migration trap
Can old and new application versions coexist safely during rollout/rollback? Are long locks, backfills, partial failures, and retries bounded?

### Backup illusion
Is "backup configured" being treated as proof of recoverability without restore/integrity evidence?

### Restore dependency trap
Would restore fail because encryption keys, control-plane services, credentials, DNS, artifact registries, or human access are unavailable in the same disaster?

## Reliability and dependencies

### Shared-fate high availability
Do nominally redundant instances/regions/accounts share a database, DNS/control plane, credential, quota, network dependency, deployment pipeline, or human action that defeats redundancy?

### Retry amplification
Can retries multiply traffic during failure, overload the recovering dependency, or cause duplicate side effects? Are timeout budgets and retry layers coordinated?

### Partial failure
Does the system behave safely when one dependency is slow, stale, partitioned, inconsistent, rate-limited, or returns semantically invalid data rather than being cleanly down?

### Queue/backlog runaway
Can queues, retries, logs, metrics cardinality, dead letters, temporary files, or storage grow without bound during degradation?

## Observability and operations

### Monitoring theater
Could users receive wrong/stale/incomplete results while infrastructure dashboards stay green? Are alerts symptom-based and actionable?

### Alert dead end
Does an alert reach someone with access, authority, context, and a tested next action? Could alert routing itself fail silently?

### Runbook theater
Can the named operator actually execute the runbook under incident conditions? Are prerequisites, permissions, credentials, decision points, and rollback steps available?

### Organizational single point of failure
Is one person the only holder of recovery, deployment, credential, data, or vendor knowledge?

### No-incidents fallacy
Is a short quiet history being treated as reliability proof despite low traffic, limited exposure, no failure exercises, or changed architecture?

## Security and privacy

### Scanner equivalence
Could a clean dependency/SAST/DAST scan coexist with broken object authorization, business-logic abuse, unsafe default permissions, data exfiltration, insecure operational access, or exposed secrets?

### Trust-boundary omission
Is a service, queue, admin path, webhook, build runner, AI tool, or internal network path incorrectly treated as trusted?

### Supply-chain gap
Can source/build/dependency provenance be substituted, tampered with, or rebuilt differently after verification?

### Privacy lifecycle gap
Are collection and encryption addressed but deletion, retention, export, backup copies, logs, analytics, and support access ignored?

## Performance and economics

### Average masks tail
Do averages hide p95/p99 latency, burst collapse, coordinated omission, queueing, or noisy-neighbor behavior?

### Capacity extrapolation
Is target capacity inferred from a much smaller test without validated scaling behavior, provider quotas, stateful bottlenecks, or load shape?

### Cost cliff
Could autoscaling, log/trace cardinality, egress, third-party per-request billing, model inference, storage retention, or retry storms produce unacceptable cost before technical saturation?

## Time and lifecycle

### Time-bomb dependency
Will certificates, tokens, domains, quotas, licenses, retention windows, scheduled jobs, temporary compatibility bridges, or provider deprecations fail later despite launch success?

### Upgrade/retirement gap
Can dependencies/runtime/schema be upgraded and the service eventually retired or data exported/deleted without unsafe manual archaeology?

## Governance and domain

### Domain omission
Has a generic web/service checklist ignored specialized obligations such as safety, medical/financial controls, scientific/numerical validity, accessibility, data lineage, AI evaluation, real-time constraints, or contractual residency?

### Reviewer capture
Is the same team relying mainly on its own assertions, or has consequential evidence been independently reproduced/reviewed where warranted?

### Goodhart/metric gaming
Could teams optimize a metric (coverage, deployment frequency, vulnerability count, uptime, ticket count) while actual user outcomes or risk worsen?

## Final challenge

For every gate marked PASS, ask:

> What realistic event would make this claim false, and what direct evidence shows that event is prevented, bounded, detected, or recoverable?

If the answer is only an assertion, plan, architecture label, or proxy metric, downgrade the evidence strength and reconsider the gate.
