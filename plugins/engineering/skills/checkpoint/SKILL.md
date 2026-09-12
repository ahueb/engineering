---
name: checkpoint
description: Create or update an explicit handoff checkpoint for a long-running software task. Use when the user asks to save progress, hand work to another session or agent, preserve state before a context reset, or document exactly what is complete, incomplete, attempted, verified, and still risky.
---

# Checkpoint

Create a concise handoff artifact that another session can trust without replaying the entire conversation. When the work follows a superpowers plan (`superpowers:writing-plans` output, executed by `superpowers:executing-plans` or `superpowers:subagent-driven-development`), reference the plan file and the task numbers completed so the next session resumes from the plan's own ledger.

Include:
- objective and acceptance criteria;
- current repository/branch/worktree identity when available;
- completed changes with file references;
- in-progress and not-started work;
- approaches attempted that failed and the evidence for failure;
- verification already run, including exact commands and outcomes;
- known defects, open questions, external dependencies, and risk;
- the smallest next actions to continue safely.

Prefer facts derivable from the repository and tool output. Do not copy transient speculation into the checkpoint as fact. Mark unresolved assumptions explicitly.

If a file is requested, default to a project-local path such as `.claude/checkpoints/<descriptive-name>.md` only when that location is acceptable to the repository; otherwise ask where to place it or return the checkpoint in chat.
