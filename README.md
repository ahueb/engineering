# engineering

Portable Claude Code configuration: an evidence-first operating policy (`CLAUDE.md`), nine cost-tiered agents, seven process skills, three user-invoked escalation skills, and recommended settings. Everything except settings ships as the `engineering` plugin; the policy also ships inside it and `install.sh` copies it to `CLAUDE.md`.

## Install

```bash
git clone git@github.com:ahueb/engineering.git && cd engineering
./install.sh                 # into ~/.claude, or $CLAUDE_CONFIG_DIR if set
./install.sh --no-official   # do not enable or install the claude-plugins-official plugins
./install.sh --source ahueb/engineering   # register the GitHub repo as the marketplace instead of this checkout
```

The script validates your `settings.json`, registers the marketplace, copies the policy to `CLAUDE.md`, merges the recommended settings key by key, and installs `engineering@engineering`, in that order; a marketplace failure stops it before anything is written. A file is backed up as `<name>.bak-<timestamp>` only when the install would change it, so an identical rerun leaves no new backups. A plugin you have explicitly disabled stays disabled, except `engineering@engineering` itself, which the installer always enables. `--no-official` also removes previously enabled `claude-plugins-official` entries from `settings.json`, because Claude Code auto-installs any enabled official plugin at the next session start. If `engineering` is already registered from a different source, the installer refuses and tells you to remove the old marketplace first. Defaults set: `fable[1m]` (Fable 5.1 with 1M context) at low effort, Sonnet 5 at medium, Concise output style, 16 concurrent subagents, no nested subagents, and a 2% skill-listing budget so every skill keeps its description on 200K-context models.

Marketplace-only install (no script) also works: `claude plugin marketplace add ahueb/engineering && claude plugin install engineering@engineering`. A SessionStart hook then injects the policy until you copy it to `~/.claude/CLAUDE.md`.

### How the policy loads

The plugin's `hooks/session-start.sh` runs on `startup`, `resume`, `clear`, `compact`, and `fork`. The hook is silent only when the first line of `$CFG/CLAUDE.md` is exactly `# Agent operating policy`; the file is then the source. Otherwise the hook prints `context/CLAUDE.md`, which Claude Code adds to the session context. The policy therefore reaches every session exactly once, whichever install path was used.

### What `install.sh` writes

| Target | Action |
|---|---|
| `CLAUDE.md` | Replaced with `plugins/engineering/context/CLAUDE.md`; a differing previous file is kept as `CLAUDE.md.bak-<timestamp>` |
| `settings.json` | Merged from `settings.recommended.json`; a previous file that the merge changes is kept as `settings.json.bak-<timestamp>`. Scalars are overwritten, objects are merged, and an `enabledPlugins` entry you set to `false` is left alone |
| marketplaces | `engineering` registered from this checkout, or from `--source`; `claude-plugins-official` registered unless `--no-official` |
| plugins | `engineering@engineering` installed at user scope; each official plugin installed unless `--no-official` or disabled in your settings |

Set `CLAUDE_CONFIG_DIR` to install somewhere other than `~/.claude`, for example to trial the setup in an empty directory first.

## Verify, pin, and roll back

- Every release is a signed tag. Verify before installing from a clone: `git config gpg.ssh.allowedSignersFile .allowed_signers && git tag -v v2.5.1`.
- Pin instead of tracking `main`. A GitHub-sourced marketplace always serves the version on `main` (`engineering@engineering@<version>` is accepted but resolves to `main`, verified 2026-09-12), so pin by checking out the signed tag and registering the clone as a directory marketplace:

  ```bash
  git clone https://github.com/ahueb/engineering.git && cd engineering && git checkout v2.5.1
  git tag -v v2.5.1   # after: git config gpg.ssh.allowedSignersFile .allowed_signers
  claude plugin marketplace remove engineering; claude plugin marketplace add "$PWD"
  claude plugin install engineering@engineering
  ```

- Roll back a bad release the same way with the previous tag, then restart Claude Code. Stop criterion for a release: any session-start error or a `claude plugin validate --strict` failure on the installed cache; the fix is always a new patch version, never a rewritten one.
- Security reports and support expectations: [SECURITY.md](SECURITY.md). Known residual risks: [docs/risk-register.md](docs/risk-register.md).

## Update

Claude Code copies the plugin into a version-keyed cache and skips `plugin update` when the version is unchanged, so editing this repo changes nothing until the version is bumped.

- Maintainer: `./release.sh patch|minor|major` (or an explicit `2.3.0`) bumps `plugin.json`, validates with `claude plugin validate --strict`, runs `./ci.sh`, commits, creates the signed tag `vX.Y.Z`, and refreshes the local install. Add `--no-commit` (in any position) to bump and refresh without committing. Push with `git push && git push --tags`. `release.sh` refuses to run on a working tree with unrelated changes, restores the version if validation fails, and commits only `plugin.json` and `CHANGELOG.md`.
- Everyone else: `claude plugin update engineering@engineering`, then restart Claude Code.
- Policy changes also need a fresh `~/.claude/CLAUDE.md`: rerun `./install.sh`, or copy `plugins/engineering/context/CLAUDE.md` over it.

## CI

There is no GitHub Actions workflow and no server-side hook. `./ci.sh` is the whole gate: shell lint, both manifests under `--strict`, probe unit tests, frontmatter and cross-reference checks, the hook contract, and a scratch-directory install. It runs on every push through `.githooks/pre-push` (enable once per clone with `git config core.hooksPath .githooks`) and inside `release.sh`. `./ci.sh --quick` skips the scratch install. Trigger-eval results are recorded in `plugins/engineering/evals/RESULTS.md`; rerun them with the commands in `plugins/engineering/evals/README.md`.

## Requirements

- **Claude Code v2.1.267 or later.** Fable 5.1 resolves from the `fable` alias from v2.1.257; the `effort` frontmatter on Fable and Opus 4.7+ models takes effect from v2.1.267.
- **Model access.** Agents and skills use the `haiku`, `sonnet`, `opus`, and `fable` aliases, so they resolve to your provider's current models. On Amazon Bedrock, Google Vertex, or Microsoft Foundry, pin them with `ANTHROPIC_DEFAULT_HAIKU_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_OPUS_MODEL`, and `ANTHROPIC_DEFAULT_FABLE_MODEL`.
- **1M context** is on by default for Fable and Sonnet 5 on the API. On subscription plans Fable usage may bill to usage credits depending on plan and seat tier; check the model picker's `Requires usage credits` label. Drop the `[1m]` suffix or set `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` to stay at 200K.
- If your account has no Fable access, set `model` to `opus[1m]`, set `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=opus` or change `deep-audit`'s `model`.
- **bash** for the SessionStart hook. Windows users need Git Bash on `PATH`, or should run `install.sh` so the policy is a file and the hook is not needed.

### Tuning

- `maxEffortLevel` caps the highest `effort` value agents and skills may request.
- `skillOverrides` / `skillListingMaxDescChars` control per-skill description length in the listing budget.
- `--plugin-dir ./plugins` runs against this checkout's plugin code without a version bump, for trying edits.
- `claude plugin eval --threshold` gates the trigger evals in CI.

## What you get

| Kind | Names |
|---|---|
| Agents | `engineering:scout` (haiku), `engineering:test-triage` (sonnet, low, has Bash), `engineering:mechanical-worker` (sonnet, low), `engineering:bulk-implementer` (sonnet, medium), `engineering:architect` (opus, medium), `engineering:semantic-reviewer` (opus, medium), `engineering:security-reviewer` (opus, medium), `engineering:hard-repair` (opus, high), `engineering:plan-auditor` (opus, high) |
| Process skills | `/engineering:plan-execution`, `/engineering:implementation-loop`, `verification-loop`, `change-review`, `checkpoint`, `change-eval`, `production-readiness-review` |
| User-only escalations | `/engineering:deep-audit` (fable, xhigh), `docs-check` (sonnet, medium), `literature-review` (opus, medium) |

`scout`, `architect`, `semantic-reviewer`, `security-reviewer`, and `plan-auditor` are read-only by tool list (no Edit, Write, or Bash). `test-triage` and `deep-audit` keep Bash for non-mutating commands and are told not to write; that is a prompt-level constraint.

## Executing plans

`/engineering:plan-execution` is the fast path for a written plan. It partitions the plan into packages that own disjoint files and share explicit interfaces, dispatches every package to a parallel `bulk-implementer` in one batch with building and testing forbidden, merges the results, runs one integrated build-and-test pass, and then has `plan-auditor` and `semantic-reviewer` adversarially check the merged result against the plan for completeness and correctness. The policy routes superpowers' `executing-plans` and `subagent-driven-development` through this flow.

## Production readiness review

`/engineering:production-readiness-review` judges whether a repository or release candidate is ready for a specific production exposure. It is read-only and evidence-first: 12 non-compensable hard gates, 13 graded readiness dimensions, separate readiness-state and evidence-strength axes, domain overlays, and an adversarial pass that tries to falsify every apparent pass before the verdict of READY, CONDITIONALLY READY, or NOT READY. Repository absence never proves an operational fact; on-call, restore drills, live SLOs, and production configuration are marked unknown unless directly evidenced.

The skill runs inline so it keeps the conversation's release context, and fans evidence collection out to `scout`, `security-reviewer`, and `semantic-reviewer`. Claude invokes it on readiness questions; `/engineering:production-readiness-review assess this branch for a 5% canary` invokes it directly. It is never run automatically by the other skills.

A bundled probe emits read-only repository discovery as JSON, with no file contents or secret values:

```bash
python3 plugins/engineering/skills/production-readiness-review/scripts/repo_probe.py /path/to/repo
python3 -m unittest plugins/engineering/skills/production-readiness-review/tests/test_repo_probe.py
```

Trigger-quality evals live in `plugins/engineering/evals/`; see its README.

## Working with superpowers

The policy maps superpowers' subagent roles onto engineering agents (implementer → `bulk-implementer`, reviewers → `semantic-reviewer` and `security-reviewer`, late fix rounds → `hard-repair`, lookups → `scout`), and `implementation-loop` and `verification-loop` invoke the matching superpowers skills when present; `checkpoint` records the superpowers plan file and completed task numbers. `dispatching-parallel-agents` work that edits code maps to `bulk-implementer` or `hard-repair`, not `scout`. Superpowers is not a dependency; without it every reference is simply skipped.

## Repository layout

```
.claude-plugin/marketplace.json   marketplace manifest; lists the engineering plugin
plugins/engineering/
  .claude-plugin/plugin.json      plugin manifest and version
  agents/                         nine agent definitions
  skills/                         ten SKILL.md skills; production-readiness-review bundles references, a probe, and tests
  evals/                          claude plugin eval cases for skill trigger quality
  hooks/                          SessionStart hook and its script
  context/CLAUDE.md               the operating policy
settings.recommended.json         settings merged by install.sh
install.sh                        installer
release.sh                        version bump, ci, signed tag, local refresh
ci.sh                             local CI gate (also run by the pre-push hook)
.githooks/pre-push                runs ci.sh before every push
SECURITY.md                       reporting path and verification steps
.allowed_signers                  SSH key that signs release tags
docs/risk-register.md             known residual risks and their owners
CHANGELOG.md                      release notes per version
```

## Uninstall

```bash
claude plugin uninstall engineering@engineering
claude plugin marketplace remove engineering
```

Then restore `CLAUDE.md` and `settings.json` from the `.bak-<timestamp>` files the installer left in your config directory (written only when an install changed the file), or edit them by hand.

## Not included

Credentials, permission allow-lists (machine-specific), history, and project memory.

## License

MIT. See [LICENSE](LICENSE).
