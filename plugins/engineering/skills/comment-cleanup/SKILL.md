---
name: comment-cleanup
description: Audit and rewrite every code comment in a repository so each one orients an unfamiliar reader and nothing else. Use when the user asks to clean up, review, normalize, or de-clutter comments, or when comments reference dates, phases, plans, spec files, tickets, authors, or change history instead of describing the code they annotate.
argument-hint: "[path or scope, default whole repository]"
context: fork
agent: general-purpose
model: sonnet
effort: medium
background: false
disallowed-tools: Agent, Skill, Artifact
---

# Comment cleanup

Every surviving comment must tell a reader with no repository context exactly what they are looking at, in the fewest words that do so.

1. Enumerate every comment in $ARGUMENTS (default: the whole repository), all languages, including docstrings, block headers, and file banners. Skip generated, vendored, and license text.
2. Flag comments that carry non-orienting content: dates, implementation phases or steps, plan or spec file names, ticket numbers, author names, TODO/FIXME without an owner and action, change history ("moved from", "added in", "temporary"), and commentary about the conversation or agent that wrote the code. Treat `git log` as the home for that content.
3. Flag comments that restate the code, are stale against the code beside them, or run past two sentences where one would orient.
4. For each flagged comment: delete it if the code is already self-explanatory; otherwise rewrite it to state purpose, invariant, or non-obvious reason in one concise sentence. Never move a comment's content into prose elsewhere.
5. Keep comments that explain why, warn about a constraint, or name a contract the code alone cannot show. Match the repository's existing comment style and each language's docstring conventions.
6. Change comments only. Do not touch code, whitespace outside comments, or user-facing strings. Run the repository's formatter and lint after editing.
7. Report counts of comments deleted and rewritten, with file references, and list any comment left unresolved because its meaning could not be recovered from the code.
