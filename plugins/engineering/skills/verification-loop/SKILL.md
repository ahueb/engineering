---
name: verification-loop
description: Verify that a software change actually works and is safe to finish. Use after implementation, before handoff or merge, after fixing a defect, or whenever a user asks to validate correctness, completeness, build health, tests, regressions, or production-facing behavior.
---

# Verification loop

Treat verification as evidence gathering, not ritual.

1. Determine the intended behavior and the repository's own definition of success from tests, CI, build files, contracts, schemas, and documentation.
2. Inspect the changed files and `git diff` before choosing checks.
3. Run focused checks that exercise the changed behavior.
4. Run broader repository-standard checks when feasible: relevant tests, type checks, lint/static analysis, build/package checks, and critical integration or end-to-end flows. Launch independent checks in parallel and collect all results before judging.
5. For a bug fix, demonstrate that the original failure mode is covered by a regression test or an equivalent reproducible check when practical.
6. Check negative and boundary cases that are plausible for the changed code. Prioritize data loss, security boundaries, concurrency, migrations, compatibility, and error handling over arbitrary line coverage.
7. Do not weaken tests, linters, types, security settings, or build configuration merely to make verification pass unless that change is itself required and justified.
8. If a check cannot run because of environment, credentials, external services, unavailable hardware, or time limits, record that gap explicitly instead of inferring success.
9. Finish with a compact evidence table: check, command or method, result, and remaining caveat.
