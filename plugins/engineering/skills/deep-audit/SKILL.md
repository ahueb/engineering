---
name: deep-audit
description: Perform an explicitly requested high-assurance adversarial audit of software or system architecture, using Fable only for difficult or consequential verification.
argument-hint: "[implementation, architecture, or audit scope]"
disable-model-invocation: true
context: fork
agent: general-purpose
model: fable
effort: xhigh
background: false
disallowed-tools: Edit, Write, NotebookEdit, Agent, Skill, Artifact
---

Audit $ARGUMENTS independently and adversarially. Do not modify the implementation.

1. Establish requirements, invariants, architecture constraints, and acceptance criteria.
2. Trace actual behavior and verification evidence rather than trusting summaries or passing tests.
3. Examine applicable correctness, data integrity, concurrency, complexity, resource use, failure recovery, security, compatibility, operability, and test-quality risks.
4. Try to falsify correctness with boundary, malformed, duplicate, reordered, repeated, interrupted, concurrent, partial-failure, and scale cases where relevant.
5. Validate suspected defects with targeted evidence when practical. Do not promote speculation to confirmed failure.
6. Use external documentation only when explicitly requested or when a material external/version-specific fact cannot be established locally. Do not expand into broad research without request.
7. Avoid style-only findings, duplicate symptoms of one root cause, speculative abstractions, and immaterial micro-optimizations.
8. Stop when material risk surfaces are covered and further work is unlikely to change readiness or uncertainty.

Return: overall verdict/confidence; blocking findings; other material findings by severity; residual uncertainty; verification considered; readiness. For each finding include failure mechanism, evidence, remediation, and post-fix verification.
