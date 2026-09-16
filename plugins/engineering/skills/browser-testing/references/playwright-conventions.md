# Playwright conventions

Applies to `@playwright/test` specs and to journeys driven through the Playwright MCP tools. Repository conventions override this file where they conflict; say so in the report.

## Dispatch block for `engineering:browser-tester`

One journey per dispatch, containing exactly:

- `JOURNEY`: a short name.
- `URL`: base URL and starting path.
- `PRECONDITIONS`: user, seeded data, flags, viewport, and where they come from (environment variables or a fixture file the parent names; never inline secrets).
- `STEPS`: numbered user actions, one per line.
- `ORACLE`: the conditions that make the journey pass.
- `EVIDENCE`: screenshots at named steps and the output directory (default `test-results/browser-tester/`), console errors, network failures.
- `BOUNDARY`: no file edits, no installs, no server start or stop, stay on the named origin.

The agent returns `JOURNEY`, `RESULT` (PASS | FAIL | BLOCKED), `STEPS_EXECUTED`, `ORACLE_EVIDENCE`, `CONSOLE_ERRORS`, `NETWORK_FAILURES`, `ARTIFACTS`, `BLOCKERS`.

`browser-tester` has no Bash: it confirms the application is reachable by calling `browser_navigate` itself (a failed navigation is a BLOCKED result), not by shelling out to curl or similar. Launch the app and confirm it answers before dispatch; the agent's own `browser_navigate` is its only reachability check.

## Locators

Prefer, in order: `getByRole` with an accessible name, `getByLabel`, `getByPlaceholder`, `getByText` (exact where the text is short), `getByTestId`. Use CSS or XPath only for structure the page exposes no other way, and say why. Never depend on generated class names, DOM position, or `nth()` without a stable reason.

Through MCP, take a `browser_snapshot` first and act on the `ref` values it returns; do not guess selectors. Re-snapshot after navigation or any action that re-renders the target.

## Assertions

Use web-first assertions that wait: `expect(locator).toBeVisible()`, `toHaveText`, `toHaveURL`, `toHaveValue`, `toBeEnabled`. Do not assert on `isVisible()` or `textContent()` return values; they do not wait. Assert the oracle the journey was given, not incidental page content.

## Waiting

No `page.waitForTimeout` or fixed sleeps. Wait for a locator state, a URL, a response (`page.waitForResponse` with a predicate), or a network-idle only when the page has no polling. Through MCP, use `browser_wait_for` with text or a locator condition, not time, except as a last resort with the reason recorded.

## Test structure

- One journey per `test`. Name it by the user-visible outcome.
- Isolate state: fresh context per test (the default), seeded data created in `beforeEach` or a fixture and removed afterwards, no dependence on test order.
- Authentication through `storageState` from a setup project, not by logging in inside every test.
- Fixtures in the repository's fixture file; do not duplicate a fixture in a spec.
- No `test.only`, `test.skip` without an issue reference, or commented-out assertions in committed code.
- Keep `retries` at the repository value; a spec that needs retries to pass is reported as flaky, not fixed by configuration.

Keep comments that explain non-obvious fixture isolation, locator/wait choices, compatibility constraints, or an active exception; keep required issue references. Describe only what the test's assertions establish. Do not narrate every browser action or use comments to justify skipped/weak assertions. Update nearby rationale when the test changes, preserving machine-read directives and snapshot conventions.

## Config

Honour the existing `playwright.config.*`. `webServer` with `reuseExistingServer: !process.env.CI` is the standard way to launch the app. `trace: 'on-first-retry'` and `screenshot: 'only-on-failure'` are the expected defaults; use `--trace on` for a one-off reproduction rather than changing the config.

## Commands

```bash
npx playwright test                                   # full suite, every project
npx playwright test tests/checkout.spec.ts             # one file
npx playwright test -g "adds item to cart"             # one test by title
npx playwright test --project=chromium                 # one browser project
npx playwright test --trace on --reporter=line         # reproduce with a trace
npx playwright show-trace test-results/<dir>/trace.zip # inspect a trace
npx playwright test --repeat-each 3                    # flake check
npx playwright install --with-deps chromium            # browsers missing (asks the parent first)
```

Browsers absent from the machine are an environment gap: install only with the user's or parent's consent and record it.

## Playwright MCP tool map

| Need | Tool |
|---|---|
| Open a URL | `browser_navigate` |
| Read the page as an accessibility tree with refs | `browser_snapshot` |
| Click, type, select, hover, press key | `browser_click`, `browser_type`, `browser_select_option`, `browser_hover`, `browser_press_key` |
| Fill several fields at once | `browser_fill_form` |
| Wait for text or a condition | `browser_wait_for` |
| Capture evidence | `browser_take_screenshot`, `browser_console_messages`, `browser_network_requests` |
| Run page-side JavaScript to read state | `browser_evaluate` |
| Dialogs, uploads, tabs, viewport | `browser_handle_dialog`, `browser_file_upload`, `browser_tabs`, `browser_resize` |
| Finish | `browser_close` |

Prefer snapshots over screenshots for deciding what to do next; screenshots are for the report. `browser_run_code_unsafe` is not for testing use.

## Evidence

A screenshot proves the state at one instant. A passing spec proves the assertions it contains. A console with no errors proves nothing about network failures; check `browser_network_requests` or the trace for non-2xx responses on the journey's own origin.
