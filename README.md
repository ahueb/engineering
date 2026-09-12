# engineering

Evidence-first engineering for Claude Code. One operating policy plus ten cost-tiered agents and nine process skills that route each job to the cheapest model that can do it, verify with real checks before claiming success, and report what was actually proven. Includes parallel plan execution, adversarial code and plan audits, a production readiness review with hard gates, Playwright browser testing, and narrow research skills for documentation and literature. Works standalone or alongside superpowers.

Everything except settings ships as the `engineering` plugin; the policy (`CLAUDE.md`) also ships inside it and `install.sh` copies it to your config directory.

## Example use cases

- **Ship a feature from a plan fast.** `/engineering:plan-execution docs/plans/checkout.md` splits the plan into disjoint-file packages, implements all of them in parallel on Sonnet, runs one integrated build-and-test pass, then has Opus auditors prove every plan item is complete.
- **Fix a bug with evidence.** `/engineering:implementation-loop` inspects the repo, reproduces the failure, makes the smallest fix, and closes with `verification-loop`, which reports exactly which checks ran, passed, or could not run.
- **Confirm a UI change in a real browser.** `/engineering:browser-testing "add item to cart and see the badge update"` starts the app, dispatches a headless Playwright agent with an explicit pass condition, and returns screenshots, console errors, and failed requests.
- **Decide go or no-go before a release.** `/engineering:production-readiness-review assess this branch for a 5% canary` audits twelve non-compensable gates, tries to falsify every apparent pass, and returns READY, CONDITIONALLY READY, or NOT READY with evidence strength per gate.
- **Review a pull request without noise.** `/engineering:change-review` reports concrete defects with location, failure mechanism, and fix direction, and dispatches `security-reviewer` when the diff touches auth, secrets, or external input.
- **Check one fact that may have changed.** `/engineering:docs-check "does Next.js 16 still support the pages router?"` answers from version-matched official docs with citations, on Sonnet, without editing anything.
- **Make comments orient a stranger.** `/engineering:comment-cleanup` scans every comment in the repo, strips dates, phase and plan references, and history, and rewrites what remains into one concise sentence about the code it annotates.
- **Hand work to the next session.** `/engineering:checkpoint` writes what is done, what failed and why, what was verified, and the next safe step.
- **Escalate only when it matters.** `/engineering:deep-audit` runs a read-only adversarial audit on Fable at extra-high effort, reserved for consequential or hard-to-reverse changes.

## Install

```bash
git clone git@github.com:ahueb/engineering.git && cd engineering
./install.sh                 # into ~/.claude, or $CLAUDE_CONFIG_DIR if set
./install.sh --no-official   # do not enable or install the claude-plugins-official plugins
./install.sh --source ahueb/engineering   # register the GitHub repo as the marketplace instead of this checkout
```

The script validates your `settings.json`, registers the marketplace, copies the policy to `CLAUDE.md`, merges the recommended settings key by key, and installs `engineering@engineering`, in that order; a marketplace failure stops it before anything is written. A file is backed up as `<name>.bak-<timestamp>` only when the install would change it, so an identical rerun leaves no new backups. A plugin you have explicitly disabled stays disabled, except `engineering@engineering` itself, which the installer always enables. `--no-official` also removes previously enabled `claude-plugins-official` entries from `settings.json`, because Claude Code auto-installs any enabled official plugin at the next session start. If `engineering` is already registered from a different source, the installer refuses and tells you to remove the old marketplace first. Defaults set: `fable[1m]` (Fable 5.1 with 1M context) at low effort, Sonnet 5 at medium, Concise output style, auto memory on, 16 concurrent subagents, no nested subagents, and a 2% skill-listing budget so every skill keeps its description on 200K-context models (at the 1% default the listing overflows and Claude Code drops descriptions starting with the least-invoked skills).

Marketplace-only install (no script) also works: `claude plugin marketplace add ahueb/engineering && claude plugin install engineering@engineering`. A SessionStart hook then injects the policy until you copy it to `~/.claude/CLAUDE.md`.

### How the policy loads

The plugin's `hooks/session-start.sh` runs on `startup`, `resume`, `clear`, `compact`, and `fork`. The hook is silent only when the first line of `$CFG/CLAUDE.md` is `# Agent operating policy` (a UTF-8 BOM and CRLF are tolerated); the file is then the source. Otherwise the hook prints `context/CLAUDE.md`, which Claude Code adds to the session context. The policy therefore reaches every session exactly once, whichever install path was used.

### What `install.sh` writes

| Target | Action |
|---|---|
| `CLAUDE.md` | Replaced with `plugins/engineering/context/CLAUDE.md`; a differing previous file is kept as `CLAUDE.md.bak-<timestamp>` |
| `settings.json` | Merged from `settings.recommended.json`; a previous file that the merge changes is kept as `settings.json.bak-<timestamp>`. Scalars are overwritten, objects are merged, and an `enabledPlugins` entry you set to `false` is left alone |
| marketplaces | `engineering` registered from this checkout, or from `--source`; `claude-plugins-official` registered unless `--no-official` |
| plugins | `engineering@engineering` installed at user scope; each official plugin installed unless `--no-official` or disabled in your settings |

Set `CLAUDE_CONFIG_DIR` to install somewhere other than `~/.claude`, for example to trial the setup in an empty directory first.

## Verify, pin, and roll back

- Every release is a signed tag. Verify before installing from a clone: `git config gpg.ssh.allowedSignersFile .allowed_signers && git tag -v v2.7.1`.
- Pin instead of tracking `main`. A GitHub-sourced marketplace always serves the version on `main` (`engineering@engineering@<version>` is accepted but resolves to `main`, verified 2026-09-12), so pin by checking out the signed tag and registering the clone as a directory marketplace:

  ```bash
  git clone https://github.com/ahueb/engineering.git && cd engineering && git checkout v2.7.1
  git tag -v v2.7.1   # after: git config gpg.ssh.allowedSignersFile .allowed_signers
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

- **Claude Code v2.1.267 or later** to use the plugin; **v2.1.269 or later** to run the trigger evals (`claude plugin eval`). Fable 5.1 resolves from the `fable` alias from v2.1.257; the `effort` frontmatter on models with a pinned default effort (Fable 5, Opus 4.7, Opus 4.8) takes effect from v2.1.267.
- **Model access.** Agents and skills use the `haiku`, `sonnet`, `opus`, and `fable` aliases, so they resolve to your provider's current models. On Amazon Bedrock, Google Vertex, or Microsoft Foundry, pin them with `ANTHROPIC_DEFAULT_HAIKU_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_OPUS_MODEL`, and `ANTHROPIC_DEFAULT_FABLE_MODEL`.
- **1M context.** Fable and Sonnet 5 have a native 1M window on the API; `fable[1m]` in the recommended settings makes the choice explicit. On subscription plans Fable usage may bill to usage credits depending on plan and seat tier; check the model picker's `Requires usage credits` label. Drop the `[1m]` suffix or set `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` to stay at 200K.
- If your account has no Fable access, set `model` to `opus[1m]` and either change `deep-audit`'s `model` or set `CLAUDE_CODE_SUBAGENT_MODEL=opus` with `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`, which forces that model onto every subagent and forked skill.
- **bash** for the SessionStart hook. Windows users need Git Bash on `PATH`, or should run `install.sh` so the policy is a file and the hook is not needed.

### Tuning

- `maxEffortLevel` caps the highest `effort` value agents and skills may request.
- `skillOverrides` / `skillListingMaxDescChars` control per-skill description length in the listing budget.
- `--plugin-dir ./plugins` runs against this checkout's plugin code without a version bump, for trying edits.
- `claude plugin eval --threshold` can gate the trigger evals in a CI job; `ci.sh` does not run them because each run bills model usage.

## What you get

| Kind | Names |
|---|---|
| Agents | `engineering:scout` (haiku), `engineering:test-triage` (sonnet, low, has Bash), `engineering:mechanical-worker` (sonnet, low), `engineering:bulk-implementer` (sonnet, medium), `engineering:architect` (opus, medium), `engineering:semantic-reviewer` (opus, medium), `engineering:security-reviewer` (opus, medium), `engineering:hard-repair` (opus, high), `engineering:plan-auditor` (opus, high), `engineering:browser-tester` (sonnet, medium, has Bash and Playwright MCP) |
| Process skills | `/engineering:plan-execution`, `/engineering:implementation-loop`, `verification-loop`, `browser-testing`, `change-review`, `checkpoint`, `change-eval`, `production-readiness-review`, `comment-cleanup` (forked, sonnet, medium, edits comments only) |
| Research skills (forked, read-only) | `docs-check` (sonnet, medium), `literature-review` (opus, medium) |
| User-only escalation | `/engineering:deep-audit` (fable, xhigh) |

`scout`, `architect`, `semantic-reviewer`, `security-reviewer`, and `plan-auditor` are read-only by tool list (no Edit, Write, or Bash). `test-triage` and `browser-tester` keep Bash and are told not to write; that is a prompt-level constraint. `deep-audit`, `docs-check`, and `literature-review` have no edit tools by frontmatter and keep Bash for non-mutating commands by instruction.

## Executing plans

`/engineering:plan-execution` is the fast path for a written plan. It partitions the plan into packages that own disjoint files and share explicit interfaces, dispatches every package to a parallel `bulk-implementer` in one batch with building and testing forbidden, merges the results, runs one integrated build-and-test pass, and then has `plan-auditor` and `semantic-reviewer` adversarially check the merged result against the plan for completeness and correctness. The policy routes superpowers' `executing-plans` and `subagent-driven-development` through this flow.

## Browser testing

`/engineering:browser-testing` is the only path through which the plugin drives a browser. It finds the app's own launch path (`playwright.config` `webServer`, package scripts, compose files), starts the app once, and requires an explicit oracle for every journey before anything is clicked. Exploratory runs dispatch `engineering:browser-tester`, which uses the Playwright MCP server from the official `playwright` plugin (enabled by `install.sh`) or a user-configured MCP server named `playwright`; plugin agents cannot bundle their own MCP server, Claude Code ignores `mcpServers` in a plugin agent. It returns a fixed evidence block: result, steps executed, oracle evidence, console errors, same-origin network failures, artifact paths, blockers. It never edits files. Journeys that will be rerun are codified as `@playwright/test` specs under the conventions in `skills/browser-testing/references/playwright-conventions.md` (user-facing locators, web-first assertions, no fixed sleeps, no assertion loosening to hide a defect, three-run flake rule) and run with `npx playwright test`. `verification-loop` and `implementation-loop` route user-facing web changes here; the readiness review may use one `browser-tester` dispatch per critical journey as G2 evidence.

Requirements: the official `playwright` plugin enabled (or a `playwright` MCP server in your own config), Node with `npx`, and Playwright browsers installed (`npx playwright install --with-deps chromium`; the conventions reference has the agent ask before installing).

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
  agents/                         ten agent definitions
  skills/                         twelve SKILL.md skills; browser-testing bundles a Playwright conventions reference; production-readiness-review bundles references, a probe, and tests
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
