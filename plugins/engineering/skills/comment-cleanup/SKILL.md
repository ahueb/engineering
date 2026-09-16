---
name: comment-cleanup
description: Audit or improve code comments and docstrings within a requested scope, preserving accurate contracts, rationale, directives, and documentation consumers. Use for explicit comment or docstring review, cleanup, normalization, or documentation-drift requests. Review-only requests do not edit. Not for automatically cleaning comments during unrelated implementation or refactoring.
argument-hint: "[path or scope, default whole repository]"
context: fork
agent: general-purpose
model: sonnet
effort: medium
background: false
disallowed-tools: Agent, Skill, Artifact
---

# Comment and docstring cleanup

Read [comment-guidance](references/comment-guidance.md) before auditing or editing. For the evidence behind these rules, read [source-basis](references/source-basis.md) only when rationale or revalidation is requested.

1. Establish mode and scope from the request. Review/audit-only means no edits. An explicit cleanup invocation with no narrower scope covers tracked first-party source in the repository; include other files only when the request warrants it. Record excluded, unsupported, generated, vendored, and protected files. Do not infer whole-repository scope from an ordinary coding task.
2. Inspect the working tree and the applicable language, build, lint, test, and documentation configuration. Preserve user changes. Find comments/docstrings and their consumers using language-aware inspection where available; searches are discovery aids, not proof of exhaustive parsing.
3. Identify protected directives, structured tags and arguments, legal notices, shebangs, encoding lines, executable examples, generated content, and runtime/tool consumers. Preserve their bytes and attachment/scope unless their change is explicitly authorized. Do not edit a consumer-sensitive block when its behavior cannot be established safely.
4. For each material comment claim, distinguish current behavior, intended contract, rationale, and unresolved uncertainty. Check relevant code, callers, tests, schemas, and available authoritative references. Do not replace a contract with a description of a suspected bug.
5. Retain useful contracts, units, invariants, rationale, compatibility conditions, and durable references. Delete redundant narration or transient work history only when no required information is lost. Rewrite verified stale or ambiguous prose to the shortest sufficient form; use multiple sentences or structured docstrings when necessary. Preserve required documentation conventions.
6. Put information at the appropriate scope. In a comment-only cleanup, do not create or edit unrelated design documents; propose a relocation instead. When relocation is explicitly in scope, verify the durable destination before removing the local explanation and keep a useful local summary or pointer. Never replace an essential contract with an inaccessible link.
7. In audit-only mode, report supported findings and stop without editing. In edit mode, change only approved comment/docstring spans. Do not change executable code, unrelated whitespace, unrelated user-facing strings, configuration, or other user work. Do not let formatters broaden the diff.
8. Compare against the pre-edit state and run the narrow relevant checks, including documentation consumers when affected. Prefer formatter check mode. Establish whether failures are newly caused, pre-existing, flaky, or environmental; a changed result does not by itself prove a directive changed. Undo only this task's unsafe hunks, preserving the user's work, or defer the edit with its reason.
9. Report scope, changed paths, comments retained/deleted/rewritten/deferred, material contract conflicts, verification commands and results, and unverified consumers. Counts are inventory, not success metrics. Do not claim complete coverage for skipped languages or files.
