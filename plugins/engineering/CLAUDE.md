# Agent operating policy

## Objective

Maximize fully correct accepted work per unit of model usage and wall-clock time. Optimize completed work, not raw token price, model prestige, number of agents, or lines generated.

## Precedence over plugin-injected process rules

- This file is the governing policy. Plugin hooks or skills that mandate a process on every task (for example the superpowers `using-superpowers` directive to invoke a skill at any chance of relevance, mandatory brainstorming, or mandatory TDD) do not override it.
- Use superpowers process skills when the user names them, invokes them, or is executing a plan they produced (writing-plans, executing-plans, subagent-driven-development). Otherwise apply the implementation and verification discipline below directly.
- TDD and brainstorming are tools, not gates: use them when they clarify behavior or requirements, per `/engineering:implementation-loop`.

## Default execution model

- The main session owns context-rich autonomous feature work end to end: inspect, reason, edit, run checks, repair, and finish.
- Keep dependent work in the main session when planning, implementation, and verification share substantial context.
- Delegate only when the delegated role is bounded enough that a fresh subagent context is cheaper or more reliable than keeping the work in the main conversation.
- Do not create a generic escalation ladder. Escalate only from concrete evidence or before work when the task is clearly high-risk and difficult to reverse.
- Do not use agent teams for ordinary dependent feature work.

## Tool-use efficiency

- Before requesting tools, privately identify what information is needed next.
- Invoke independent reads, searches, and read-only checks in parallel rather than serializing them.
- Do not minimize tool use at the expense of evidence. Inspect repository state, run relevant checks, and reproduce failures when correctness depends on them.
- Do not repeat a tool call unless new evidence makes the repetition useful.
- Prefer targeted reads, searches, diffs, and log slices over loading entire large files or logs.
- Prefer targeted edits over rewriting whole files when a localized change is sufficient.
- Do not rely on remembered library, API, repository, or tool behavior when the current source or installed version can be inspected.

## Implementation discipline

- Establish the acceptance criteria before making substantial edits.
- Read the minimum code needed to identify invariants, call sites, tests, and compatibility constraints.
- Preserve existing behavior outside the requested scope unless a change is required by the task.
- Prefer the smallest coherent change that fully satisfies the requirement.
- Avoid speculative abstractions, unrelated cleanup, broad rewrites, and extra features.
- Generate concise comments only where the code would otherwise be difficult to understand.
- When several independent changes are mechanically identical, batch them rather than rediscovering the same pattern repeatedly.

## Verification

- Use deterministic verification before model review whenever it can establish the property: compiler, type checker, formatter, linter, unit tests, integration tests, static analysis, or a minimal reproduction.
- Run the narrowest relevant check first; broaden only when the change or failure justifies it.
- A green check is evidence only for what that check actually covers.
- When a check fails, preserve the exact failing command and the smallest useful failure output before attempting repair.
- Do not claim completion while known relevant checks are failing unless the failure is demonstrably pre-existing and unrelated; report that distinction explicitly.

## Delegation policy

Read-only agents are read-only by tool list, not by `permissionMode`: sessions launched with `--dangerously-skip-permissions` make subagents ignore their declared `permissionMode`, so any agent that must not write is given no Edit, Write, or Bash tool.

Use `engineering:scout` for narrow file, symbol, definition, or reference discovery when a cheap isolated lookup is sufficient.

Use `engineering:test-triage` to compress large test, compiler, or log output into the smallest causal failure set before giving it to a more expensive model. It has Bash to rerun the failing command; it must not edit.

Use `engineering:mechanical-worker` for repetitive transformations with an explicit pattern and deterministic verification.

Use `engineering:bulk-implementer` for a bounded output-heavy implementation that can be specified without transferring most of the main session context.

Use `engineering:architect` before implementation only for cross-cutting, difficult-to-reverse design decisions whose invariants are not already clear from the task and repository.

Use `engineering:semantic-reviewer` only when important correctness properties are not adequately covered by deterministic checks or the change has material semantic, concurrency, migration, compatibility, or data-integrity risk.

Use `engineering:security-reviewer` when a change touches a trust boundary: authentication, authorization, secrets, external input, file or network access, supply chain, or CI.

Use `engineering:hard-repair` only after a concrete persistent failure remains unresolved by the normal main-session repair loop. Give it the failing command, relevant output, changed files, and already-disproven hypotheses.

The `engineering` plugin provides every agent above plus the process skills `/engineering:implementation-loop`, `/engineering:verification-loop`, `/engineering:change-review`, `/engineering:checkpoint`, and `/engineering:change-eval`.

User-invoked escalations (hidden from the model; invoke by slash command only):
- `/engineering:deep-audit` — Fable at xhigh effort, read-only adversarial audit.
- `/engineering:independent-review` — Opus at high effort, read-only review; a tier above `engineering:semantic-reviewer`.
- `/engineering:docs-check` — Sonnet, narrow authoritative documentation lookup.
- `/engineering:literature-review` — Opus, evidence-driven research synthesis.

Size each delegated work package so the agent finishes within roughly 200k tokens of context; split larger packages or have the agent checkpoint and hand off, because every turn re-reads the whole history.

## Review policy

- Do not run a frontier reviewer after every routine edit.
- Review the changed code and only the directly relevant surrounding definitions and tests.
- Reviewers should report concrete defects, not praise, style commentary, or a general summary.
- Keep review output terse because reviewer output becomes downstream input.
- Do not suppress valid findings merely because their severity is low; prioritize and format them compactly instead.
- Do not automatically run a second review after a repair. Re-review only if the repair changes the relevant invariant or the original defect class remains uncertain.

## Repair policy

- Prefer repairing from concrete evidence over starting the task again from scratch.
- Preserve working parts of the implementation.
- Change one causal hypothesis at a time when diagnosis is uncertain.
- Stop repeating an approach once evidence has falsified it.
- Escalate reasoning only when the remaining uncertainty is genuinely reasoning-limited rather than information-limited.

## Context and cost discipline

- Keep progress narration short. Spend output on code, tool arguments, evidence, and decisions rather than essays about the work.
- Avoid unnecessary model switches inside a live session because model caches are separate.
- Do not invoke a subagent merely to restate context already present in the main conversation.
- Do not pass a subagent the full transcript when a focused task statement, relevant paths, and concrete evidence are sufficient.
- Avoid arbitrary turn limits that can terminate useful work before verification. Use semantic stopping conditions instead.
- Stop when the requested behavior is implemented, relevant verification passes, and no material uncovered risk remains.

## Completion report

At completion, report only:

1. what materially changed;
2. which verification commands were run and their result;
3. any known residual risk or unverified condition.
