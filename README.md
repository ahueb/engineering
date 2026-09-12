# engineering

Portable Claude Code configuration: an evidence-first operating policy (`CLAUDE.md`), nine cost-tiered agents, six process skills, four user-invoked escalation skills, and recommended settings. Everything except `CLAUDE.md` and settings ships as the `engineering` plugin so it can be updated in place.

## Install

```bash
git clone git@github.com:ahueb/engineering.git && cd engineering
./install.sh                 # into ~/.claude, or $CLAUDE_CONFIG_DIR if set
./install.sh --no-official   # do not enable or install the claude-plugins-official plugins
./install.sh --source ahueb/engineering   # register the GitHub repo as the marketplace instead of this checkout
```

The script backs up any existing `CLAUDE.md` and `settings.json`, copies the policy, merges the recommended settings key by key, registers the marketplace, and installs `engineering@engineering`. A plugin you have explicitly disabled stays disabled. Defaults set: `fable[1m]` (Fable 5.1 with 1M context) at low effort, Sonnet 5 at medium, Concise output style, 16 concurrent subagents, no nested subagents.

Marketplace-only install (no script) also works: `claude plugin marketplace add ahueb/engineering && claude plugin install engineering@engineering`. A SessionStart hook then injects the policy until you copy it to `~/.claude/CLAUDE.md`.

### How the policy loads

The plugin's `hooks/session-start.sh` runs on `startup`, `clear`, `compact`, and `fork`. If `CLAUDE.md` in the config directory begins with `# Agent operating policy`, the hook exits silently and the file is the source. Otherwise the hook prints `context/CLAUDE.md`, which Claude Code adds to the session context. The policy therefore reaches every session exactly once, whichever install path was used.

### What `install.sh` writes

| Target | Action |
|---|---|
| `CLAUDE.md` | Replaced with `plugins/engineering/context/CLAUDE.md`; the previous file is kept as `CLAUDE.md.bak-<timestamp>` |
| `settings.json` | Merged from `settings.recommended.json`; the previous file is kept as `settings.json.bak-<timestamp>`. Scalars are overwritten, objects are merged, and an `enabledPlugins` entry you set to `false` is left alone |
| marketplaces | `engineering` registered from this checkout, or from `--source`; `claude-plugins-official` registered unless `--no-official` |
| plugins | `engineering@engineering` installed at user scope; each official plugin installed unless `--no-official` or disabled in your settings |

Set `CLAUDE_CONFIG_DIR` to install somewhere other than `~/.claude`, for example to trial the setup in an empty directory first.

## Update

Claude Code copies the plugin into a version-keyed cache and skips `plugin update` when the version is unchanged, so editing this repo changes nothing until the version is bumped.

- Maintainer: `./release.sh patch|minor|major` (or an explicit `2.3.0`) bumps `plugin.json`, validates with `claude plugin validate --strict`, commits, and refreshes the local install. Add `--no-commit` to bump and refresh without committing. Push afterwards.
- Everyone else: `claude plugin update engineering@engineering`, then restart Claude Code.
- Policy changes also need a fresh `~/.claude/CLAUDE.md`: rerun `./install.sh`, or copy `plugins/engineering/context/CLAUDE.md` over it.

## Requirements

- **Claude Code v2.1.257 or later** for the `fable` alias and `[1m]` handling used in `settings.recommended.json`.
- **Model access.** Agents and skills use the `haiku`, `sonnet`, `opus`, and `fable` aliases, so they resolve to your provider's current models. On Amazon Bedrock, Google Vertex, or Microsoft Foundry, pin them with `ANTHROPIC_DEFAULT_HAIKU_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_OPUS_MODEL`, and `ANTHROPIC_DEFAULT_FABLE_MODEL`. If your account has no Fable access, set `model` to `opus[1m]` or `opus` after install; `/engineering:deep-audit` then also needs its `model` changed.
- **1M context** is included on Max, Team, and Enterprise, billed to usage credits on Pro, and always on for the API. Drop the `[1m]` suffix or set `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` if you would rather stay at 200K.
- **bash** for the SessionStart hook. Windows users need Git Bash on `PATH`, or should run `install.sh` so the policy is a file and the hook is not needed.

## What you get

| Kind | Names |
|---|---|
| Agents | `engineering:scout` (haiku), `engineering:test-triage` (haiku, has Bash), `engineering:mechanical-worker` (sonnet, low), `engineering:bulk-implementer` (sonnet, medium), `engineering:architect` (opus, medium), `engineering:semantic-reviewer` (opus, medium), `engineering:security-reviewer` (opus, medium), `engineering:hard-repair` (opus, high), `engineering:plan-auditor` (opus, high) |
| Process skills | `/engineering:plan-execution`, `/engineering:implementation-loop`, `verification-loop`, `change-review`, `checkpoint`, `change-eval` |
| User-only escalations | `/engineering:deep-audit` (fable, xhigh), `independent-review` (opus, high), `docs-check` (sonnet, medium), `literature-review` (opus, medium) |

`scout`, `architect`, `semantic-reviewer`, `security-reviewer`, and `plan-auditor` have no Edit, Write, or Bash tool, so they cannot modify anything even under `--dangerously-skip-permissions`. `test-triage` keeps Bash to rerun a failing command and is told not to write; that is a prompt-level constraint, not a hard one.

## Executing plans

`/engineering:plan-execution` is the fast path for a written plan. It partitions the plan into packages that own disjoint files and share explicit interfaces, dispatches every package to a parallel `bulk-implementer` in one batch with building and testing forbidden, merges the results, runs one integrated build-and-test pass, and then has `plan-auditor` and `semantic-reviewer` adversarially check the merged result against the plan for completeness and correctness. The policy routes superpowers' `executing-plans` and `subagent-driven-development` through this flow.

## Working with superpowers

The policy maps superpowers' subagent roles onto engineering agents (implementer → `bulk-implementer`, reviewers → `semantic-reviewer` and `security-reviewer`, late fix rounds → `hard-repair`, lookups → `scout`), and `implementation-loop`, `verification-loop`, and `checkpoint` invoke the matching superpowers skills when they are present. Superpowers is not a dependency; without it every reference is simply skipped.

## Repository layout

```
.claude-plugin/marketplace.json   marketplace manifest; lists the engineering plugin
plugins/engineering/
  .claude-plugin/plugin.json      plugin manifest and version
  agents/                         nine agent definitions
  skills/                         ten SKILL.md skills
  hooks/                          SessionStart hook and its script
  context/CLAUDE.md               the operating policy
settings.recommended.json         settings merged by install.sh
install.sh                        installer
release.sh                        version bump and local refresh
CHANGELOG.md                      release notes per version
```

## Uninstall

```bash
claude plugin uninstall engineering@engineering
claude plugin marketplace remove engineering
```

Then restore `CLAUDE.md` and `settings.json` from the `.bak-<timestamp>` files the installer left in your config directory, or edit them by hand.

## Not included

Credentials, permission allow-lists (machine-specific), history, and project memory.

## License

MIT. See [LICENSE](LICENSE).
