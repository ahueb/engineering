# lathe

Evidence-first engineering for Claude Code. One operating policy, eleven cost-tiered agents, and twelve skills that route each job to the cheapest model that can do it, verify with real checks before claiming success, and report what was actually proven.

## What it adds

- **Process skills:** `/lathe:implementation-loop` and `/lathe:verification-loop` for a change from request to verified result; `/lathe:plan-execution`, which implements a written plan in parallel packages, then runs one integrated build and an adversarial audit; `/lathe:change-review`; `/lathe:browser-testing` with Playwright; `/lathe:production-readiness-review`, a hard-gated go/no-go; `/lathe:comment-cleanup`; `/lathe:checkpoint`; and `/lathe:change-eval`.
- **Research skills:** `/lathe:docs-check` and `/lathe:literature-review`, which run without a shell.
- **User-only escalation:** `/lathe:deep-audit`, a read-only adversarial audit on Opus.
- **Agents:** `scout`, `test-triage`, `mechanical-worker`, `bulk-implementer`, `architect`, `semantic-reviewer`, `security-reviewer`, `plan-auditor`, `browser-tester`, `hard-repair`, and `auditor`, each with the narrowest tools and model its job needs.

## What runs automatically

The plugin has two hooks:

- At session start, `hooks/session-start.sh` adds the bundled operating policy to the session, unless an installed copy of the policy is already at `~/.claude/rules/engineering-policy.md` or `~/.claude/CLAUDE.md`. If that copy is out of date, it prints a one-line notice instead.
- Before each Bash or PowerShell call, `hooks/readonly-guard.sh` limits the `lathe:auditor` agent, which `/lathe:deep-audit` runs, to a read-only command allowlist. Every other agent is unaffected.

## Data and network access

The plugin reads no API key, token, or other credential, ships no MCP server, and makes no network request of its own. The hooks read only the policy files named above, the hook input, and the bundled allowlist. `browser-tester` drives the Playwright MCP server from the official `playwright` plugin when that plugin is enabled; a signed-in journey uses the project's saved login state or a disposable test account you provide in the conversation.

## Requirements

Claude Code, with Bash for the hooks and Python 3 for the read-only guard. Browser testing also needs the official `playwright` plugin and a project with Playwright installed.

## More

The installer, recommended settings, and full documentation are at [github.com/ahueb/lathe](https://github.com/ahueb/lathe). License: MIT.
