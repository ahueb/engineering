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
2. Protect machine-read comments; never delete or reword them: lint and type suppressions (`noqa`, `type: ignore`, `eslint-disable`, `pylint:`, `nolint`, `@ts-ignore`, `@ts-expect-error`), build and codegen directives (`//go:build`, `//go:generate`, `//go:embed`, `#pragma`, `// +build`, `#[cfg]`-adjacent doc attrs, `@generated`, `DO NOT EDIT`), tooling markers (`prettier-ignore`, `fmt: off/on`, `istanbul ignore`, `coverage:`, `sourceMappingURL`, bundler magic comments such as `webpackChunkName`), test directives (doctests, `# doctest:`, `t.Parallel` hints, snapshot markers), API documentation consumed by generators (Javadoc, JSDoc, rustdoc, Sphinx, OpenAPI annotations), shebangs and encoding lines, and any repository-specific magic comment found by grepping the build, lint, and CI configuration before editing. Reword the prose part of a documentation block only when the tags and their arguments stay byte-identical.
3. Flag comments that carry non-orienting content: dates, implementation phases or steps, plan or spec file names, ticket numbers, author names, TODO/FIXME without an owner and action, change history ("moved from", "added in", "temporary"), and commentary about the conversation or agent that wrote the code. Treat `git log` as the home for that content.
4. Flag comments that restate the code, are stale against the code beside them, or run past two sentences where one would orient.
5. For each flagged comment: delete it if the code is already self-explanatory; otherwise rewrite it to state purpose, invariant, or non-obvious reason in one concise sentence. Never move a comment's content into prose elsewhere.
6. Keep comments that explain why, warn about a constraint, or name a contract the code alone cannot show. Match the repository's existing comment style and each language's docstring conventions.
7. Change comments only. Do not touch code, whitespace outside comments, or user-facing strings. After editing run the repository's formatter, lint, type checker, and its standard test command; a comment change that alters any of their results is reverted, because that comment was a directive.
8. Report counts of comments deleted and rewritten, with file references, and list any comment left unresolved because its meaning could not be recovered from the code.
