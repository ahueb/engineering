---
model: claude-sonnet-5
max_turns: 40
timeout_seconds: 900
tags: [behaviour, behaviour-cleanup]
allowed_tools: [Read, Grep, Glob, Skill]
---
Run `/engineering:comment-cleanup` on this repository. When it has finished, write ONE final message that contains, in this order: (1) the cleanup report with counts of comments deleted and rewritten and file references, (2) the output of `python3 check_directives.py` on its own line. Do not send the check output as a separate message.
