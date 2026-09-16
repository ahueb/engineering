---
name: verification-loop
description: Verify that a software change actually works and is safe to finish. Use after implementation, before handoff or merge, after fixing a defect, or whenever a user asks to validate correctness, completeness, build health, tests, regressions, or production-facing behavior.
---

# Verification loop

Treat verification as evidence gathering, not ritual.

1. Determine the intended behavior and the repository's own definition of success from tests, CI, build files, contracts, schemas, and documentation.
2. Inspect the changed files and `git diff` before choosing checks. Classify changed documentation as prose, contract, directive, executable example, or consumed text. For changed comments/docstrings, identify directive attachment, structured tags, executable examples, and runtime/documentation consumers before choosing checks. Compare with the pre-edit state and verify the affected consumers and preserved contract information; a green code test or unchanged directive text alone does not establish preservation. Record checks that could not run. Use `${CLAUDE_PLUGIN_ROOT}/skills/comment-cleanup/references/comment-guidance.md` only when a material documentation claim or consumer is in scope.
3. Run focused checks that exercise the changed behavior, including the applicable consumers of any changed documentation or contract.
4. Run broader repository-standard checks when feasible: relevant tests, type checks, lint/static analysis, build/package checks, and critical integration or end-to-end flows, plus preservation checks for any contract or consumer-sensitive text affected by the change. For a user-facing web change, run `/engineering:browser-testing` so the critical journey is exercised in a real browser with an explicit oracle. Launch independent checks in parallel and collect all results before judging.
5. For a bug fix, demonstrate that the original failure mode is covered by a regression test or an equivalent reproducible check when practical.
6. Check negative and boundary cases that are plausible for the changed code. Prioritize data loss, security boundaries, concurrency, migrations, compatibility, and error handling over arbitrary line coverage.
7. Do not weaken tests, linters, types, security settings, or build configuration merely to make verification pass unless that change is itself required and justified.
8. If a check cannot run because of environment, credentials, external services, unavailable hardware, or time limits, record that gap explicitly instead of inferring success.
9. Finish with a compact evidence table: check, command or method, result, and remaining caveat. Expose unrun checks and unresolved documentation/contract conflicts in this table rather than omitting them.
10. If the `superpowers:verification-before-completion` skill is available, invoke it before any completion claim; its evidence-before-assertion rule and this table are the same standard.
