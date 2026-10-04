---
model: claude-sonnet-5-5
max_turns: 40
timeout_seconds: 900
tags: [behaviour, behaviour-readiness]
allowed_tools: [Read, Grep, Glob]
---
/lathe:production-readiness-review Review an AI-enabled service for production readiness for GA to all customers. Auth, alerting, a pinned image, and a drilled restore are in place, but model versioning, evaluation slices, prompt-injection/tool-abuse tests, provider fallback, and model cost ceilings are not evidenced.
