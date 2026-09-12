---
model: claude-sonnet-5
max_turns: 40
timeout_seconds: 900
tags: [behaviour, behaviour-readiness]
allowed_tools: [Read, Grep, Glob]
---
/engineering:production-readiness-review Judge a release that has 95% code coverage, zero findings from one SAST scanner, and excellent average latency, but no evidence about critical-journey semantic correctness, authorization abuse cases, tail latency, or rollback after schema migration.
