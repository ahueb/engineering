---
name: change-review
description: Perform a fresh-context, evidence-based code review of a change, branch, pull request, or working tree. Use when the user asks for review, before merge or handoff, or after substantial implementation to find correctness, security, reliability, maintainability, and test gaps without inventing issues.
---

# Code review

Review the change as an adversarial maintainer, not as its author.

1. Read the user requirement or issue, then inspect the diff and enough surrounding code to understand invariants and callers.
2. Separate changed-code defects from pre-existing issues. Focus findings on the requested change unless a pre-existing issue is directly made worse.
3. Prioritize correctness, data integrity, security, authorization, concurrency, error handling, resource lifecycle, compatibility, migrations, and user-visible regressions. Validate material comment/docstring claims against the code, callers, tests, and applicable contract; report misleading guarantees, lost semantic constraints, and directive/consumer changes only with a concrete failure mechanism. Do not treat comment count, preferred wording, or missing prose on self-explanatory private code as a defect.
4. Validate suspicious findings against code paths, tests, schemas, configuration, or authoritative documentation before reporting them. Do not assume implementation correctness when the written contract disagrees.
5. Do not report stylistic preferences, formatting, or arbitrary complexity metrics at all — not as findings, notes, or observations, and not to say you are leaving them out — unless the repository explicitly requires them or they create concrete risk.
6. For every finding, provide severity, location, failure mechanism, evidence, and a specific remediation direction.
7. Avoid duplicates. Before reporting, delete any finding or note whose only basis is cosmetic formatting or whitespace that changes no behavior (for example a trailing blank line), unless the repository explicitly requires that formatting (step 5). Whitespace that changes meaning is not cosmetic: indentation in Python or YAML, the blank line a directive such as `//go:build` requires, and whitespace inside string literals. If no material defect is found, say so and list the most important verification gaps or assumptions that remain.
8. When the change touches a trust boundary or exposure (auth, secrets, external input, file or network access, network listeners or deployment configuration, privileges, supply chain, CI, or agent tool wiring), dispatch `engineering:security-reviewer` with the diff text and any deployment or exposure facts already established (where the code runs, what calls it, what the network can reach), marked as supplied rather than verified, however small the diff. Wait for its result, then write one report that merges its findings and carries its UNDETERMINED items and the exposure facts each finding rests on. State in the report that it was dispatched, or why it could not be.
9. Never modify code during review unless the user explicitly asks for fixes.
