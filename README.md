# engineering

Portable Claude Code configuration: an evidence-first operating policy (`CLAUDE.md`), eight cost-tiered agents, five process skills, four user-invoked escalation skills, and recommended settings. Everything except `CLAUDE.md` and settings ships as the `engineering` plugin so it can be updated in place.

## Install

```bash
git clone git@github.com:ahueb/engineering.git && cd engineering
./install.sh            # into ~/.claude, or $CLAUDE_CONFIG_DIR if set
./install.sh --no-official   # skip the claude-plugins-official plugins
```

The script backs up any existing `CLAUDE.md` and `settings.json`, copies the policy, merges the recommended settings key by key, registers this checkout as a marketplace, and installs `engineering@engineering`. Defaults set: Fable 5.1 with 1M context (`claude-fable-5-1[1m]`) at low effort, Sonnet 5 at medium, Concise output style, 16 concurrent subagents, no nested subagents.

Marketplace-only install (no script) also works: `claude plugin marketplace add ahueb/engineering && claude plugin install engineering@engineering`. A SessionStart hook then injects the policy until you copy it to `~/.claude/CLAUDE.md`.

## What you get

| Kind | Names |
|---|---|
| Agents | `engineering:scout` (Haiku), `engineering:test-triage` (Haiku), `engineering:mechanical-worker` (Sonnet), `engineering:bulk-implementer` (Sonnet), `engineering:architect` (Opus), `engineering:semantic-reviewer` (Opus), `engineering:hard-repair` (Opus), `engineering:security-reviewer` (inherit) |
| Process skills | `/engineering:implementation-loop`, `verification-loop`, `change-review`, `checkpoint`, `change-eval` |
| User-only escalations | `/engineering:deep-audit` (Fable xhigh), `independent-review` (Opus high), `docs-check` (Sonnet), `literature-review` (Opus) |

Read-only agents are read-only by tool list (no Edit, Write, or Bash), so the guarantee holds even under `--dangerously-skip-permissions`.

## Not included

Credentials, permission allow-lists (machine-specific), history, and project memory.

## License

MIT. See [LICENSE](LICENSE).
