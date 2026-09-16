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
5. Do not use stylistic preferences or arbitrary complexity metrics as defects unless the repository explicitly requires them or they create concrete risk.
6. For every finding, provide severity, location, failure mechanism, evidence, and a specific remediation direction.
7. Avoid duplicates. If no material defect is found, say so and list the most important verification gaps or assumptions that remain.
8. When the change touches a trust boundary (auth, secrets, external input, file or network access, supply chain, CI), dispatch `engineering:security-reviewer` with the diff text and merge its findings.
9. Never modify code during review unless the user explicitly asks for fixes.
