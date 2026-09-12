---
model: claude-sonnet-5
max_turns: 40
timeout_seconds: 900
tags: [behaviour, behaviour-readiness]
allowed_tools: [Read, Grep, Glob]
---
/engineering:production-readiness-review Do a readiness review. The repository says backups are enabled and contains a restore runbook, but there is no restore-drill output or other direct recovery evidence.
