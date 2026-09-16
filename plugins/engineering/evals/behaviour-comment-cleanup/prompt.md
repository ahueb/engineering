---
model: claude-sonnet-5
max_turns: 40
timeout_seconds: 900
tags: [behaviour, behaviour-cleanup, comment-guidance-write]
allowed_tools: [Read, Grep, Glob, Skill]
---
Run `/engineering:comment-cleanup` on this repository. You are authorized only to clean up comments and docstrings. You are NOT authorized to change any behavior, executable code, or consumer-visible text (help output, error strings, generated files, licenses, or vendor files).

When the skill has finished, write ONE final message that reports:
1. The scope of the cleanup (which files you reviewed and which you changed).
2. The changed paths.
3. For each file you changed: comments/docstrings you retained as-is, deleted, or rewrote, and why.
4. Any comment you deliberately deferred rather than touched, and why (for example: it points to inaccessible or unverifiable information, or removing/rewriting it would require a judgment call outside the cleanup's scope).
5. Any conflict you found between this repository's contract/documentation and what the code actually does.
6. Any checks you ran (if any) and their result.
7. Any consumer of a comment (for example a help-text reader, generated-code marker, or build directive) that you could not fully verify.
