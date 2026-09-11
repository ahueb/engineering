---
name: independent-review
description: Perform an explicitly requested independent read-focused review of a meaningful implementation for correctness, regressions, architecture, security, performance, and test adequacy.
argument-hint: "[change, diff, component, or review scope]"
disable-model-invocation: true
context: fork
agent: general-purpose
model: opus
effort: high
background: false
disallowed-tools: Edit, Write, NotebookEdit, Agent, Skill, Artifact, WebSearch, WebFetch
---

Independently review $ARGUMENTS. Do not modify the implementation.

Prioritize material defects involving requirements, correctness, edge cases, contracts, state/error handling, concurrency, complexity, resource use, security, compatibility, architecture, and verification quality.

Trace relevant execution paths and run targeted non-mutating verification when useful. Distinguish confirmed defects, material risks, and optional improvements. Ignore formatter-level preferences and insignificant micro-optimizations.

For each material finding give severity, location, failure mechanism, evidence, and recommended correction. State explicitly when no material defect is found. Stop when the material change surface is adequately evaluated.
