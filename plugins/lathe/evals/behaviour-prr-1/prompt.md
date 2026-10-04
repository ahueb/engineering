---
model: claude-sonnet-5-5
max_turns: 40
timeout_seconds: 900
tags: [behaviour, behaviour-readiness]
allowed_tools: [Read, Grep, Glob]
---
/lathe:production-readiness-review Audit the current repository for GA production readiness. The repo has strong unit tests and CI, but do not assume any external operational controls that are not evidenced.
