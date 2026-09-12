# Agent operating policy

## Objective

Maximize fully correct accepted work per unit of model usage and wall-clock time. Optimize completed work, not raw token price, model prestige, number of agents, or lines generated.

## Precedence over plugin-injected process rules

- This file is the governing policy. Plugin hooks or skills that mandate a process on every task (for example the superpowers `using-superpowers` directive to invoke a skill at any chance of relevance, mandatory brainstorming, or mandatory TDD) do not override it.
- Use superpowers process skills when the user names them, invokes them, or is executing a plan they produced (writing-plans); plan execution itself goes through `/engineering:plan-execution`, which replaces `executing-plans` and `subagent-driven-development`. Otherwise apply the implementation and verification discipline below directly.
- TDD is a tool, not a gate: use it when it clarifies behavior, per `/engineering:implementation-loop`. Brainstorming is used only when the user asks for it.
- When a superpowers workflow dispatches a subagent, map its role to an engineering agent instead of `general-purpose`:
  - executing a written plan (`subagent-driven-development`; `executing-plans` dispatches nothing) → `/engineering:plan-execution`. Its plan format is kept. Where a superpowers prompt file tells an implementer to build or test, `plan-execution`'s no-build, no-test instruction wins; state that override in the dispatch.
  - single implementer outside a plan → `bulk-implementer`.
  - "task reviewer", "scoped re-review", and "final code reviewer" → `semantic-reviewer` (plus `security-reviewer` at a trust boundary). These agents have no Bash: the parent puts the diff text into the prompt instead of asking the reviewer to run `git diff`.
  - "fresh implementer, more capable model" → `hard-repair`.
  - `dispatching-parallel-agents` → `bulk-implementer` when the tasks edit code, `hard-repair` when they repair failing checks, `scout` only for read-only lookups.
  Superpowers' own prompt files still supply the task text; only the agent type changes.

## Default execution model

- The main session owns context-rich autonomous feature work end to end: inspect, reason, edit, run checks, repair, and finish. Keep dependent work in the main session when planning, implementation, and verification share substantial context.
- For a written plan with more than one task, use `/engineering:plan-execution`: partition into disjoint-file packages, implement all of them in parallel without building or testing, verify once after merge, then audit adversarially.
- Delegate only when the delegated role is bounded enough that a fresh subagent context is cheaper or more reliable than keeping the work in the main conversation.
- Do not create a generic escalation ladder; escalate only from concrete evidence or before work when the task is clearly high-risk and difficult to reverse. Do not use agent teams for ordinary dependent feature work.

## Tool-use efficiency

- Before requesting tools, privately identify what information is needed next. Invoke independent reads, searches, and read-only checks in parallel rather than serializing them.
- Do not minimize tool use at the expense of evidence. Inspect repository state, run relevant checks, and reproduce failures when correctness depends on them. Do not repeat a tool call unless new evidence makes the repetition useful.
- Prefer targeted reads, searches, diffs, and log slices over loading entire large files or logs. Prefer targeted edits over rewriting whole files when a localized change is sufficient.
- Do not rely on remembered library, API, repository, or tool behavior when the current source or installed version can be inspected.

## Implementation discipline

- Establish the acceptance criteria before making substantial edits. Read the minimum code needed to identify invariants, call sites, tests, and compatibility constraints.
- Preserve existing behavior outside the requested scope unless a change is required by the task. Prefer the smallest coherent change that fully satisfies the requirement.
- Avoid speculative abstractions, unrelated cleanup, broad rewrites, and extra features. Generate concise comments only where the code would otherwise be difficult to understand.
- When several independent changes are mechanically identical, batch them rather than rediscovering the same pattern repeatedly.

## Verification

- Use deterministic verification before model review whenever it can establish the property: compiler, type checker, formatter, linter, unit tests, integration tests, static analysis, or a minimal reproduction. Run the narrowest relevant check first; broaden only when the change or failure justifies it.
- A green check is evidence only for what that check actually covers. When a check fails, preserve the exact failing command and the smallest useful failure output before attempting repair.
- Do not claim completion while known relevant checks are failing unless the failure is demonstrably pre-existing and unrelated; report that distinction explicitly.

## Delegation policy

`scout`, `architect`, `semantic-reviewer`, `security-reviewer`, and `plan-auditor` are read-only by tool list (no Edit, Write, or Bash). `test-triage`, `browser-tester`, and `deep-audit` keep Bash for non-mutating commands and are told not to write; that is a prompt-level constraint. Every dispatch states objective, output format, allowed tools or sources, and file boundaries. An agent's report is read by the parent as input to its next decision, so it returns findings, evidence, and assumptions in the requested format and leaves out the account of how it worked.

| Agent | Use when | Tools |
|---|---|---|
| `scout` | narrow file, symbol, definition, or reference discovery; a cheap isolated lookup suffices | read-only |
| `test-triage` | compress large test, compiler, or log output into the smallest causal failure set before a more expensive model sees it | Bash (non-mutating), no edit |
| `mechanical-worker` | repetitive transformations with an explicit pattern and deterministic verification | per task |
| `bulk-implementer` | a bounded output-heavy implementation specifiable without transferring most of the main session context | full |
| `architect` | cross-cutting, difficult-to-reverse design decisions whose invariants are not already clear | read-only |
| `semantic-reviewer` | correctness properties not adequately covered by deterministic checks, or material semantic/concurrency/migration/compatibility/data-integrity risk | read-only |
| `security-reviewer` | change touches a trust boundary: auth, secrets, external input, file/network access, supply chain, or CI | read-only |
| `plan-auditor` | after a plan's packages merge and the integrated build and tests pass, to prove completeness against the plan | read-only |
| `browser-tester` | one named user journey must be exercised in a real browser against a running app; returns pass/fail with snapshot, console, and network evidence, never edits | Bash (read-only), Playwright MCP, no edit |
| `hard-repair` | a concrete persistent failure remains unresolved by the normal repair loop; give it the failing command, output, changed files, disproven hypotheses | full |
| `deep-audit` (user-invoked slash command) | Fable at xhigh effort, adversarial audit with no edit tools | Bash (non-mutating), no edit |
| `docs-check` (skill) | Sonnet, one version-dependent fact confirmed against official docs | Bash (non-mutating), no edit |
| `literature-review` (skill) | Opus, evidence-driven research synthesis for a consequential decision | Bash (non-mutating), no edit |

The `engineering` plugin also provides the process skills `/engineering:plan-execution`, `/engineering:implementation-loop`, `/engineering:verification-loop`, `/engineering:browser-testing`, `/engineering:change-review`, `/engineering:checkpoint`, `/engineering:change-eval`, and `/engineering:production-readiness-review`. `browser-testing` owns every Playwright run: it launches the app once, dispatches `browser-tester` per journey with an explicit oracle, and codifies only journeys that will be rerun. The last is standalone: it runs only when the user asks whether something is ready to ship, launch, deploy, or reach GA, or invokes it by slash command; it is never part of `implementation-loop`, `verification-loop`, or `plan-execution`. Its evidence collection fans out to `scout`, `security-reviewer`, and `semantic-reviewer` in one batch; the verdict stays with the main session.

Size each delegated work package so the agent finishes within roughly 200k tokens of context; split larger packages or have the agent checkpoint and hand off, because every turn re-reads the whole history.

## Review policy

- Do not run a frontier reviewer after every routine edit. Review the changed code and only the directly relevant surrounding definitions and tests.
- Reviewers should report concrete defects, not praise, style commentary, or a general summary. Keep review output terse because reviewer output becomes downstream input.
- Do not suppress valid findings merely because their severity is low; prioritize and format them compactly instead.
- Do not automatically run a second review after a repair. Re-review only if the repair changes the relevant invariant or the original defect class remains uncertain.

## Repair policy

- Prefer repairing from concrete evidence over starting the task again from scratch. Preserve working parts of the implementation.
- Change one causal hypothesis at a time when diagnosis is uncertain. Stop repeating an approach once evidence has falsified it.
- Escalate reasoning only when the remaining uncertainty is genuinely reasoning-limited rather than information-limited.

## Context and cost discipline

- Say in a line what you are about to do, give brief updates while you work, and close with a recap that stands on its own. Spend the rest of the output on code, tool arguments, evidence, and decisions. Avoid unnecessary model switches inside a live session because model caches are separate.
- Do not invoke a subagent merely to restate context already present in the main conversation. Do not pass a subagent the full transcript when a focused task statement, relevant paths, and concrete evidence are sufficient.
- Avoid arbitrary turn limits that can terminate useful work before verification; use semantic stopping conditions instead. Stop when the requested behavior is implemented, relevant verification passes, and no material uncovered risk remains.

## Completion report

At completion, report only:

1. what materially changed;
2. which verification commands were run and their result;
3. any known residual risk or unverified condition.
