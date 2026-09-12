---
model: claude-sonnet-5
max_turns: 40
timeout_seconds: 900
tags: [behaviour, behaviour-readiness]
allowed_tools: [Read, Grep, Glob]
---
/engineering:production-readiness-review Adversarially review an apparently mature multi-region service. Architecture docs say it is highly available, but determine whether shared dependencies, failover exercises, control-plane access, alert routing, and operator capability are actually evidenced.
