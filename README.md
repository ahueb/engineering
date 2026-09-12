# engineering

Portable Claude Code configuration: an evidence-first operating policy (`CLAUDE.md`), eight cost-tiered agents, five process skills, four user-invoked escalation skills, and recommended settings. Everything except `CLAUDE.md` and settings ships as the `engineering` plugin so it can be updated in place.

## Install

```bash
git clone git@github.com:ahueb/engineering.git && cd engineering
./install.sh                 # into ~/.claude, or $CLAUDE_CONFIG_DIR if set
./install.sh --no-official   # do not enable or install the claude-plugins-official plugins
./install.sh --source ahueb/engineering   # register the GitHub repo as the marketplace instead of this checkout
```

The script backs up any existing `CLAUDE.md` and `settings.json`, copies the policy, merges the recommended settings key by key, registers the marketplace, and installs `engineering@engineering`. A plugin you have explicitly disabled stays disabled. Defaults set: `fable[1m]` (Fable 5.1 with 1M context) at low effort, Sonnet 5 at medium, Concise output style, 16 concurrent subagents, no nested subagents.

Marketplace-only install (no script) also works: `claude plugin marketplace add ahueb/engineering && claude plugin install engineering@engineering`. A SessionStart hook then injects the policy until you copy it to `~/.claude/CLAUDE.md`.

## Update

Claude Code copies the plugin into a version-keyed cache and skips `plugin update` when the version is unchanged, so editing this repo changes nothing until the version is bumped.

- Maintainer: `./release.sh patch|minor|major` bumps `plugin.json`, validates, commits, and refreshes the local install.
- Everyone else: `claude plugin update engineering@engineering`.

## Requirements

- **Claude Code v2.1.257 or later** for the `fable` alias and `[1m]` handling used in `settings.recommended.json`.
- **Model access.** Agents and skills use the `haiku`, `sonnet`, `opus`, and `fable` aliases, so they resolve to your provider's current models. On Amazon Bedrock, Google Vertex, or Microsoft Foundry, pin them with `ANTHROPIC_DEFAULT_HAIKU_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_OPUS_MODEL`, and `ANTHROPIC_DEFAULT_FABLE_MODEL`. If your account has no Fable access, set `model` to `opus[1m]` or `opus` after install; `/engineering:deep-audit` then also needs its `model` changed.
- **1M context** is included on Max, Team, and Enterprise, billed to usage credits on Pro, and always on for the API. Drop the `[1m]` suffix or set `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` if you would rather stay at 200K.
- **bash** for the SessionStart hook. Windows users need Git Bash on `PATH`, or should run `install.sh` so the policy is a file and the hook is not needed.

## What you get

| Kind | Names |
|---|---|
| Agents | `engineering:scout` (haiku), `engineering:test-triage` (haiku, has Bash), `engineering:mechanical-worker` (sonnet, low), `engineering:bulk-implementer` (sonnet, medium), `engineering:architect` (opus, medium), `engineering:semantic-reviewer` (opus, medium), `engineering:security-reviewer` (opus, medium), `engineering:hard-repair` (opus, high) |
| Process skills | `/engineering:implementation-loop`, `verification-loop`, `change-review`, `checkpoint`, `change-eval` |
| User-only escalations | `/engineering:deep-audit` (fable, xhigh), `independent-review` (opus, high), `docs-check` (sonnet, medium), `literature-review` (opus, medium) |

`scout`, `architect`, `semantic-reviewer`, and `security-reviewer` have no Edit, Write, or Bash tool, so they cannot modify anything even under `--dangerously-skip-permissions`. `test-triage` keeps Bash to rerun a failing command and is told not to write; that is a prompt-level constraint, not a hard one.

## Working with superpowers

The policy maps superpowers' subagent roles onto engineering agents (implementer → `bulk-implementer`, reviewers → `semantic-reviewer` and `security-reviewer`, late fix rounds → `hard-repair`, lookups → `scout`), and `implementation-loop`, `verification-loop`, and `checkpoint` invoke the matching superpowers skills when they are present. Superpowers is not a dependency; without it every reference is simply skipped.

## Not included

Credentials, permission allow-lists (machine-specific), history, and project memory.

## License

MIT. See [LICENSE](LICENSE).
