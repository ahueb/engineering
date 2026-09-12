---
model: claude-sonnet-5
max_turns: 40
timeout_seconds: 900
tags: [behaviour, behaviour-readiness]
allowed_tools: [Read, Grep, Glob]
---
/engineering:production-readiness-review Review an AI-enabled service for production readiness. Its normal web-service controls are strong, but model versioning, evaluation slices, prompt-injection/tool-abuse tests, provider fallback, and model cost ceilings are not evidenced.
