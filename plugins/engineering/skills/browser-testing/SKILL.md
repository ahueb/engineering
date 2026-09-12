---
name: browser-testing
description: Drive and verify a web application in a real browser with Playwright. Use when a change must be confirmed in the running UI rather than by unit tests, when the user asks to test, click through, screenshot, or reproduce a bug in the browser, when end-to-end or Playwright specs must be written, repaired, or de-flaked, or when a critical user journey needs browser-level evidence before handoff or release. Not for API-only checks, unit tests, or static review.
argument-hint: "[journey, page, spec, or bug to exercise]"
---

# Browser testing

Browser evidence is the strongest proof a UI change works and the most expensive to collect: launch once, name each journey, fix its oracle before clicking, codify only what will be rerun. Read [references/playwright-conventions.md](references/playwright-conventions.md) before dispatching or writing a spec.

1. Find the app's own launch path from `playwright.config.*` (`webServer`, `baseURL`), package scripts, compose files, and CI. If `webServer` exists, `npx playwright test` owns the lifecycle; otherwise start the app in the background, poll until it answers, and stop it at the end. Never target production or a shared environment unless the user names it and the journey is read-only.
2. Write the oracle for every journey before driving it: visible text, URL, element state, response, or absence of console errors. "The page loaded" is not an oracle.
3. Exploratory (confirm once, reproduce a bug, screenshot, learn real locators): dispatch `engineering:browser-tester` per journey using the dispatch block in the reference, independent journeys in one batch. Keep its evidence block, not its transcript. `BLOCKED` is unverified, not an application failure.
4. Codified (rerun, critical path, tests requested): match the existing spec layout and fixtures; write per the conventions; one or two specs in this session, a bounded batch via `engineering:bulk-implementer` with the reference path. Do not codify a journey whose oracle has not passed once exploratorily.
5. Verify narrowest first: one file and one project, then the project, then the suite when shared fixtures or config changed.
6. Repair: rerun a failing spec once with `--trace on`, compress the report with `engineering:test-triage`, then fix what the trace shows. Never widen a timeout, add a retry, or loosen an assertion to hide a failure. A spec that both passes and fails on identical code in three runs is reported flaky, not stable.
7. Stop the app if this session started it. Report with the `/engineering:verification-loop` evidence table: journey or spec, command or dispatch, result, artifact path, caveat. Name every journey not exercised and why. A screenshot proves one instant; a passing spec proves its assertions.
