---
model: claude-sonnet-5
max_turns: 40
timeout_seconds: 900
tags: [behaviour, behaviour-readiness]
allowed_tools: [Read, Grep, Glob]
---
/engineering:production-readiness-review Assess whether a service that is not ready for GA could safely run as a 1% internal canary behind a kill switch. Make the release boundary explicit.
