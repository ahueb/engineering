# engineering

Evidence-first engineering for Claude Code. One operating policy plus eleven cost-tiered agents and nine process skills that route each job to the cheapest model that can do it, verify with real checks before claiming success, and report what was actually proven. Includes parallel plan execution, adversarial code and plan audits, a production readiness review with hard gates, Playwright browser testing, and narrow research skills for documentation and literature. Works standalone or alongside superpowers.

Everything except settings ships as the `engineering` plugin; the policy also ships inside it, and `install.sh` installs it as a standalone rules file that Claude Code loads every session without a hook.

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
./install.sh --no-official   # do not register or install the claude-plugins-official marketplace/plugins
./install.sh --source ahueb/engineering   # register the GitHub repo as the marketplace instead of this checkout
```

The script validates your `settings.json`, registers the marketplace, installs `engineering@engineering`, merges the recommended settings into `settings.json`, installs the operating policy (as a rules file by default, or `CLAUDE.md` with `--policy-target claude-md`), installs official plugins, and writes the installer marker, in that order; a marketplace failure stops it before anything is written. A file is backed up before any change that would alter it (see Backups below), so an identical rerun leaves no new backup. A plugin you have explicitly disabled stays disabled, except `engineering@engineering` itself, which the installer always enables (see Changed behaviour below). If `engineering` is already registered from a different source, the installer refuses and tells you to remove the old marketplace first. Defaults set: `fable[1m]` (Fable 5.1 with 1M context) at low effort, Sonnet 5 at medium, Concise output style, auto memory on, 16 concurrent subagents, no nested subagents, and a 2% skill-listing budget so every skill keeps its description on 200K-context models (at the 1% default the listing overflows and Claude Code drops descriptions starting with the least-invoked skills).

Flags: `--no-official` (skip registering the official marketplace and installing official plugins; leaves any existing official entries alone), `--purge-official` (also remove previously registered official marketplace/plugin entries from `settings.json`, backed up first; an explicit `false` you set is kept), `--source X` (register `X` — a directory or a GitHub `owner/repo` — as the `engineering` marketplace instead of this checkout), `--settings-mode enforce|defaults` (override the auto-selected merge mode; see the mode table below), `--policy-target rules|claude-md` (install the policy as `~/.claude/rules/engineering-policy.md`, the default, or keep the legacy `~/.claude/CLAUDE.md` layout), `--dry-run` (print the settings diff, drift report, policy action, marketplace action, and plugin actions without writing anything; cannot be combined with `--restore`, which exits 2), `--yes` (assume yes to any confirmation, including legacy-policy migration, without a TTY prompt), `--break-hardlinks` (allow the installer to replace a hard-linked target instead of refusing), `--create-through-dangling` (when `settings.json` is a dangling symlink, create the target through the link instead of refusing; without it the installer exits 4 with "settings.json is a dangling symlink; check out the dotfiles target or pass --create-through-dangling"), `--restore [STAMP]` (restore the given backup, or the latest one, from `~/.claude/backups/engineering/`; accepts `--break-hardlinks` and `--no-outside-cfg`), `--no-outside-cfg` (`--restore` only: refuse every entry whose real target lies outside the config directory instead of restoring it; see Installer rollback and restore below), `--no-rollback` (do not roll this run's own writes back on failure; print the manual restore command instead), `--list-backups` (list available backup stamps and the files each one holds), `-h` (help).

Environment variables: `ENGINEERING_NO_PROMPT=1` declines any interactive confirmation deterministically, the same as running without a TTY (used for the legacy-policy migration prompt); `ENGINEERING_RECOMMENDED=PATH` points the installer at an alternate recommended-settings file whenever it is set, printing "recommendation file overridden by ENGINEERING_RECOMMENDED: <path>" (test and CI use only; the default is `settings.recommended.json` beside `install.sh`). The pointed-to file replaces the whole recommendation, including hooks, `env`, and permissions, so only set this deliberately — a hostile file could grant itself broad settings through this variable. `ENGINEERING_RELEASE=1` is not an installer variable; `release.sh` and `.githooks/pre-push` use it to recognize a release push (see Release below).

Marketplace-only install (no script) also works: `claude plugin marketplace add ahueb/engineering && claude plugin install engineering@engineering`. A SessionStart hook then injects the policy every session until you run `install.sh` to install it as a rules file (or a legacy `CLAUDE.md`, with `--policy-target claude-md`).

### How the policy loads

The plugin's `hooks/session-start.sh` runs on `startup`, `resume`, `clear`, `compact`, and `fork`. The hook is silent when the first line of either `$CFG/rules/engineering-policy.md` or `$CFG/CLAUDE.md` is `# Agent operating policy` (a UTF-8 BOM and CRLF are tolerated); that file is then the source, and Claude Code loads any file under `$CFG/rules/` in every session on its own, without the hook. If that installed copy differs from the policy bundled with the installed plugin version, the hook prints a one-line notice asking you to rerun `install.sh` rather than a second copy. Otherwise the hook prints `context/CLAUDE.md`, which Claude Code adds to the session context. The policy therefore reaches every session exactly once, whichever install path was used, and an outdated copy is announced instead of silently kept.

`install.sh` installs the policy as `$CFG/rules/engineering-policy.md` by default. A legacy `$CFG/CLAUDE.md` whose first line is the policy header is recognised as the installer's own copy: it is offered for migration (confirmed on a TTY, or with `--yes`; declined automatically under `ENGINEERING_NO_PROMPT=1` or with no TTY available) by backing it up, deleting it (a symlink has only the link removed; its target is left alone), and writing the rules file. If migration is declined, the legacy `CLAUDE.md` is instead refreshed in place, and the installer prints the exact command to migrate later. The installer never touches a `CLAUDE.md` that is not its own copy. `--policy-target claude-md` keeps the legacy layout permanently for a given run (backup, replace, skip when identical) instead of migrating. If the run falls back to, or is explicitly told, `--policy-target claude-md` while `rules/engineering-policy.md` is already installed, the installer does not write `CLAUDE.md` and instead prints "rules/engineering-policy.md is already installed; not writing CLAUDE.md (remove the rules file or use --policy-target rules)".

The installer also gates on what the installed plugin version actually supports: it greps the installed cached hook for `rules/engineering-policy.md`, and when that string is absent it falls back to `CLAUDE.md` for the run and prints "installed plugin <version> does not support the rules-file policy; keeping the policy in CLAUDE.md".

### Merge rules

`settings.json` is merged with `settings.recommended.json` the same way Claude Code itself combines settings sources, in this order:

1. A single scalar value: the higher-priority source replaces it.
2. A list (for example `permissions.allow`/`deny`, `sandbox.network.allowedDomains`): the lists are unioned, with duplicates removed.
3. A nested block (for example `env`, `sandbox`, `modelSettings`): merged key by key, recursively.
4. `extraKnownMarketplaces` and `managedMcpServers`: each named entry is replaced whole by name.
5. `fallbackModel`, `modelPicker`, `availableModels`: replaced whole.

### Settings modes

| Mode | Behaviour |
|---|---|
| `enforce` | The recommended value wins at every path above: lists still union, but marketplace/MCP entries, `fallbackModel`, `modelPicker`, and `availableModels` are replaced whole by the recommendation. |
| `defaults` | A recommended value is applied only where the path is absent from your settings; lists still union; a marketplace or MCP entry already present by name is left untouched; `enabledPlugins` gains only missing entries. Every path where your value differs from the recommendation is printed as a drift report, ending with the line `apply the recommended values with: ./install.sh --settings-mode enforce`. |

The mode is chosen automatically unless `--settings-mode` is given: `defaults` once the installer marker `~/.claude/engineering-installer.json` is present from a prior run; `defaults` with a prominent drift report and a first-run notice when the marker is absent but a prior installation is otherwise evident (an enabled `engineering@engineering` or a legacy policy copy) — this covers the first run of a rewritten installer on an existing configuration; `enforce` only on a genuinely first install, where neither signal exists. An explicit `--settings-mode` always wins.

The drift report and the `--dry-run` settings diff both redact sensitive values as `<redacted>`: anything under an `env` block, any key containing `key`, `token`, `secret`, `password`, or `credential`, and `apiKeyHelper`.

### Backups and the marker

Before any write that would change a file, the installer copies it to `~/.claude/backups/engineering/<UTC timestamp>-<pid>/`, alongside a manifest; the newest 5 stamped backups are kept and older ones pruned automatically. `--restore [STAMP]` restores the given backup (or the latest one if omitted); `--list-backups` lists the available stamps and the files each one holds. A run that changes nothing creates no new backup.

`--restore` first takes its own pre-restore backup of every file it is about to overwrite, under a new stamp printed as `pre-restore backup: <dir>`, so any edits made after the backup being restored are still recoverable. It then restores regular files unconditionally. A symlink recorded in the backup that is now missing is recreated only when its recorded target already exists on disk with content identical to what was backed up; otherwise the restore of that entry is refused and nothing is created outside the config directory. Restored file modes are masked to the permission bits only. The manifest's `stored` names are validated as flat filenames before use, in both backup and restore.

Before writing anything, `--restore` prints `outside config dir: <rel> -> <real path>` for every entry whose real target resolves outside the config directory — an intact symlink into a dotfiles checkout is the normal case. By default those entries are restored anyway, so dotfiles-style setups keep working; `--no-outside-cfg` refuses them instead (`refused <rel>: outside config dir`, exit 8 for the refused entries, the rest still restored).

The installer also writes `~/.claude/engineering-installer.json` at the end of every successful run (installer version, timestamp, settings mode used, policy target); this marker is not itself backed up, listed, or restored (it is marked as created only when this run created it, for rollback purposes — see below), and is the durable signal that later runs use to select `defaults` mode by default.

File modes: an existing `settings.json` keeps its current mode across a write; only a `settings.json` that did not exist before the run is newly created at 0600. This means a `settings.json` the CLI created earlier under a permissive umask keeps that mode through the installer — see SECURITY.md.

### Rollback

After the first file a run writes, an unexpected command failure or an explicit exit with code 3-7 rolls that run's writes back automatically: every file the run wrote is restored to what it was before the run (or, if the run created it, removed), and the run then exits with its original code. The scope is exactly what this run wrote or removed, and only if nothing else changed that file or removed-path since — `scripts/safe_write.py mark-written` records the post-write hash of every file the run touches, and rollback compares against it before touching anything; a file changed by something else after the run wrote it is reported as `not rolled back: <rel> changed after this run wrote it` and left alone. The installer marker `engineering-installer.json` is removed on rollback only when this run created it.

Not every non-zero exit is a rollback trigger. Exit 1 refusals (a user-owned policy file the installer would not overwrite, a marketplace refusal, and similar) are deliberate stopping points, not failures, and leave whatever was already written in place. `--dry-run` never writes, so there is nothing to roll back. Exit 11 (a partial run: `engineering@engineering`, `settings.json`, and the policy are installed, but one or more official plugins failed) is not rolled back either — the successful part of the run stays.

`--no-rollback` disables the automatic restore and instead prints the manual command (`./install.sh --restore <stamp>`); the run's partial writes are left as they are. If rollback itself fails, the installer prints the same manual restore command and exits with the run's original exit code. What rollback never removes, by design: the config directory created for this run and its `backups/` tree.

Exit codes 11 and 12: 11 is the partial-official-plugin-failure case above. 12 is never produced by `install.sh` itself — it belongs to `scripts/safe_write.py restore --only-run-files`, which returns it when the given stamp marks no file as written by an installer run; `install.sh`'s own rollback checks that first (`safe_write.py list --stamp <stamp> --written`) and simply does nothing when there is nothing to roll back, so 12 is reachable only by calling `safe_write.py restore --only-run-files` directly.

### What `install.sh` writes

| Target | Action |
|---|---|
| policy | Installed as `rules/engineering-policy.md` by default, or `CLAUDE.md` with `--policy-target claude-md`; a legacy `CLAUDE.md` policy copy is migrated to the rules file (with confirmation) or refreshed in place if migration is declined; a user's own `CLAUDE.md` or rules file is never touched |
| `settings.json` | Merged from `settings.recommended.json` per the merge rules above, in `enforce` or `defaults` mode |
| marketplaces | `engineering` registered from this checkout, or from `--source`; `claude-plugins-official` registered unless `--no-official` |
| plugins | `engineering@engineering` installed at user scope and always enabled; each official plugin installed unless `--no-official` or disabled in your settings; `--purge-official` removes previously registered official entries instead |
| backups | Any file the run would change is copied to `~/.claude/backups/engineering/<stamp>/` first; see Backups above |
| `--dry-run` | Prints the settings diff, drift report (in `defaults` mode), policy action, marketplace action, and plugin actions; writes nothing |

Set `CLAUDE_CONFIG_DIR` to install somewhere other than `~/.claude`, for example to trial the setup in an empty directory first.

## Verify, pin, and roll back

- Every release is a signed tag. Verify before installing from a clone: `git config gpg.ssh.allowedSignersFile .allowed_signers && git tag -v v2.7.1`.
- Pin instead of tracking `main`. Pin the marketplace source to a signed tag with `@ref` (verified 2026-09-12: `claude plugin marketplace add ahueb/engineering@v2.7.1` installs 2.7.1); `claude plugin marketplace update engineering` then follows that tag, not `main`. The plugin-version form `engineering@engineering@<version>` does not pin.

  ```bash
  claude plugin marketplace remove engineering
  claude plugin marketplace add ahueb/engineering@v2.7.1
  claude plugin install engineering@engineering
  ```

  To verify the tag signature yourself, clone, `git config gpg.ssh.allowedSignersFile .allowed_signers && git tag -v v2.7.1`, check out the tag, and register the clone as a directory marketplace instead.

- Roll back a bad release the same way with the previous tag, then restart Claude Code. Stop criterion for a release: any session-start error or a `claude plugin validate --strict` failure on the installed cache; the fix is always a new patch version, never a rewritten one.
- Security reports and support expectations: [SECURITY.md](SECURITY.md). Known residual risks: [docs/risk-register.md](docs/risk-register.md).

## Update

Claude Code copies the plugin into a version-keyed cache and skips `plugin update` when the version is unchanged, so editing this repo changes nothing until the version is bumped.

- Maintainer: `./release.sh prepare patch|minor|major` (or an explicit `x.y.z`) bumps `plugin.json`, folds `CHANGELOG.md`'s `## [Unreleased]` section under a new dated heading, validates with `claude plugin validate --strict`, runs `./ci.sh` (or `./ci.sh --full` when `install.sh`, `ci.sh`, `scripts/`, or `ci/` changed since the previous tag, or when no tag exists), branches `release/vX.Y.Z`, commits `Release engineering X.Y.Z`, pushes, and opens/watches/merges the PR through `gh` — see Release below for what the check and the tag each prove. `release.sh patch|minor|major|x.y.z [--no-commit]` (no subcommand) is the deprecated legacy form: it behaves like `prepare <bump> --no-pr` and prints a deprecation line; `--no-commit` keeps its old meaning of bumping, validating, and running `ci.sh` only, with nothing branched, committed, or pushed.
- Everyone else: `claude plugin update engineering@engineering`, then restart Claude Code.
- Policy changes also need a refreshed installed policy: rerun `./install.sh` (updates the rules file, or `CLAUDE.md` with `--policy-target claude-md`).

## Release

Releases go through a GitHub-required-check-gated PR flow; there is no direct push to `main`, including for the maintainer.

- **`./release.sh prepare patch|minor|major|x.y.z [--no-pr]`.** Runs the version bump, changelog fold, validation, and `ci.sh` tier described above, then branches `release/vX.Y.Z`, commits, and pushes. Unless `--no-pr`, it continues into `pr` (below) automatically. `--no-pr` stops after the push and prints the manual `gh pr create`/`gh pr checks`/`gh pr merge` commands; a missing or unauthenticated `gh` behaves the same way (exit 1), leaving the pushed branch in place.
- **`./release.sh pr X.Y.Z`.** For an already-pushed `release/vX.Y.Z` branch: `gh pr create` (base `main`), `gh pr checks --watch --fail-fast`, `gh pr merge --squash --subject "Release engineering X.Y.Z" --delete-branch`. This is also the rerun path after a `prepare --no-pr` or a failed `pr`: rerun `pr`, never a second `prepare`.
- **`./release.sh tag [X.Y.Z]`.** Fetches `origin/main`, requires its head commit subject to be exactly `Release engineering X.Y.Z` and `plugin.json` at that commit to be `X.Y.Z` (defaults to `origin/main`'s `plugin.json` version), signs and pushes the tag `vX.Y.Z` from `origin/main`, then refreshes the local plugin install.

`ENGINEERING_RELEASE=1` is set by `release.sh` around its own `git push` calls; `.githooks/pre-push` skips its own `ci.sh` run only when `ENGINEERING_RELEASE=1` is set and every pushed ref is a release branch (`refs/heads/release/v*`) or a version tag (`refs/tags/v*`) — GitHub Actions is the gate for those pushes instead.

Two separate proofs, not one: the required `linux` check proves `./ci.sh` passed on a tree identical to `main`'s head (squash-and-merge with `strict: true` keeps the merged tree identical to the checked PR head); the signed tag proves the maintainer released that commit. Commits on `main` are GitHub-signed (from the rebase merge), so `.allowed_signers` verifies tags, not commits. Tag pushes are not gated by any required check (see the risk register, R13). Direct pushes to `main`, including by the maintainer, are rejected by branch protection once the required check is applied (see CI below).

## CI

`.github/workflows/ci.yml` runs three jobs on every pull request to `main`, every push to `main`, and every `v*` tag push. None use secrets or configure credentials; `--full` (which needs an authenticated CLI) never runs in Actions.

- **`linux`** (ubuntu-latest): installs the pinned, signature-verified Claude Code build, installs shellcheck, and runs `./ci.sh` (the default tier). Proves the default tier passes on Linux with a verified CLI binary. This is the required status check for `main`.
- **`macos`** (macos-latest): same install and verification, then prepends a `bash` → `/bin/bash` shim to `PATH` so every script runs under the system's bash 3.2 (asserted in the job log), installs shellcheck and gnupg via Homebrew, and runs `./ci.sh`. Proves bash 3.2 compatibility, which Linux runners (bash 5) cannot.
- **`windows`** (windows-latest): installs the pinned, signature-verified Claude Code build via PowerShell, runs the Python unit tests under `python -X dev`, and runs `bash -n` under Git Bash on the shell scripts. Proves the Python helpers pass their unit tests and the shell scripts are syntactically valid on Windows; it does not run the `ci.sh` scratch-install scenarios there (informational only — see the risk register, R5).

The required check was applied on 2026-09-12 with the command below (the `PATCH .../required_status_checks` endpoint returns 404 until status checks are enabled, so the whole protection object is `PUT`, restating the existing settings; GitHub Actions' app id is `15368`). A direct push to `main` is now rejected with `GH006: Protected branch update failed ... Required status check "linux" is expected`:

```
cat > /tmp/protection.json <<'EOF'
{"required_status_checks": {"strict": true, "checks": [{"context": "linux", "app_id": 15368}]},
 "enforce_admins": true, "required_pull_request_reviews": null, "restrictions": null,
 "required_linear_history": true, "allow_force_pushes": false, "allow_deletions": false}
EOF
gh api -X PUT repos/ahueb/engineering/branches/main/protection --input /tmp/protection.json
```

`macos` becomes a required check only after two consecutive green releases on it.

Locally, CI still has three tiers: `./ci.sh --quick` runs static checks and unit tests only; `./ci.sh` (no flags; what Actions' `linux`/`macos` jobs, `.githooks/pre-push` — enable once per clone with `git config core.hooksPath .githooks` — and `release.sh` normally run) adds every offline scratch-install scenario and the read-only guard table; `./ci.sh --full` adds two scenarios that need network and credentials — the default official-plugin install path, and a rules-file load check via `claude -p --model haiku` — and fails rather than skipping them unless `CI_ALLOW_SKIP=1` is set (`--full` never runs in Actions). Unit tests run under `python3 -X dev` so resource warnings and other dev-mode diagnostics fail the suite. ShellCheck is required; a machine without it fails the lint step unless `CI_ALLOW_SKIP=1` is set. `CI_DOCS_STRICT=1` promotes `ci.sh`'s doc-cross-reference check (README documents every `install.sh` flag/env var and every `release.sh` subcommand) from a skip to a failure. Scratch-install scenarios also cover: a foreign marketplace binding refusal, `--dry-run` against the dangling-symlink and legacy-`CLAUDE.md` states, `--restore` with a backed-up symlink whose recorded target is outside the config directory, a failed plugin install leaving `settings.json` exactly as the CLI left it, a manifest merge across two backups taken in one run, an installed-version probe with a distractor plugin present, a cache fallback that picks the highest semver, installer rollback and `--no-rollback`, restore's outside-config-dir disclosure and `--no-outside-cfg`, mixed-precision stamp ordering, and the `release.sh prepare`/`pr`/`tag` flow against `gh` shims. The interactive-accept branch of the legacy-policy migration prompt is exercised with a pseudo-terminal when Python's `pty` module works on the host; see risk register R11 when that scenario is skipped. Trigger-eval results are recorded in `plugins/engineering/evals/RESULTS.md`; rerun them with the commands in `plugins/engineering/evals/README.md`.

## Evals

Beyond the 20 trigger-quality cases above, two outcome-graded behaviour suites exercise skill *output*, not just whether it fires. Both use `claude plugin eval`; see `plugins/engineering/evals/README.md` for the full invocations.

- **Readiness behaviour** (`behaviour-prr-1`..`-7`): seven `production-readiness-review` scenarios graded on the report's machine-checkable `VERDICT:`/`GATE G<n>:` lines and an `llm` rubric, run with grants that exclude `Edit`/`Write`. Measured (7 cases × 3 runs, sonnet, explicit slash invocation, `--allow-tools Read Grep Glob "Bash(python3 *)"`, cost 9.84 USD): the `VERDICT`/`GATE` regex graders passed on every run for scenarios 1, 2, 3, 5, 6, 7; the `llm` rubric passed 20 of 21 runs (one FAIL on scenario 5). Scenario 4 (a 1% internal canary behind a kill switch) failed on all 3 runs — the skill returned `VERDICT: NOT READY` where the scenario expects `CONDITIONALLY READY`; this is an open finding about the readiness rubric's bounded-canary rule (see risk register R15), not a grader bug.
- **Comment-cleanup behaviour** (`behaviour-comment-cleanup`): asserts protected directive comments survive `comment-cleanup` byte-identical. Measured (3 runs, sonnet, `Skill` granted because the skill is forked, cost 0.58 USD): 3 of 3 runs passed every grader. An earlier batch without the `Skill` grant passed 2 of 3, the miss being the missing grant.

## Requirements

- **Claude Code v2.1.267 or later** to use the plugin; **v2.1.269 or later** to run the trigger evals (`claude plugin eval`). Fable 5.1 resolves from the `fable` alias from v2.1.257; the `effort` frontmatter on models with a pinned default effort (Fable 5, Opus 4.7, Opus 4.8) takes effect from v2.1.267.
- **Model access.** Agents and skills use the `haiku`, `sonnet`, `opus`, and `fable` aliases, so they resolve to your provider's current models. On Amazon Bedrock, Google Vertex, or Microsoft Foundry, pin them with `ANTHROPIC_DEFAULT_HAIKU_MODEL`, `ANTHROPIC_DEFAULT_SONNET_MODEL`, `ANTHROPIC_DEFAULT_OPUS_MODEL`, and `ANTHROPIC_DEFAULT_FABLE_MODEL`.
- **1M context.** Fable and Sonnet 5 have a native 1M window on the API; `fable[1m]` in the recommended settings makes the choice explicit. On subscription plans Fable usage may bill to usage credits depending on plan and seat tier; check the model picker's `Requires usage credits` label. Drop the `[1m]` suffix or set `CLAUDE_CODE_DISABLE_1M_CONTEXT=1` to stay at 200K.
- If your account has no Fable access, set `model` to `opus[1m]` and either change `deep-audit`'s `model` or set `CLAUDE_CODE_SUBAGENT_MODEL=opus` with `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1`, which forces that model onto every subagent and forked skill.
- **bash** for the SessionStart hook. Windows users need Git Bash on `PATH`, or should run `install.sh` so the policy is a rules file and the hook is not needed. On Windows, `install.sh` reports a failed write with "close Claude Code and rerun" if the target file is held open by a running session; MSYS-style symlink resolution is out of scope (see the risk register, R5).

### Tuning

- `maxEffortLevel` caps the highest `effort` value agents and skills may request.
- `skillOverrides` / `skillListingMaxDescChars` control per-skill description length in the listing budget.
- `--plugin-dir ./plugins` runs against this checkout's plugin code without a version bump, for trying edits.
- `claude plugin eval --threshold` can gate the trigger evals in a CI job; `ci.sh` does not run them because each run bills model usage.

## What you get

| Kind | Names |
|---|---|
| Agents | `engineering:scout` (haiku), `engineering:test-triage` (sonnet, low, no Bash), `engineering:mechanical-worker` (sonnet, low), `engineering:bulk-implementer` (sonnet, medium), `engineering:architect` (opus, medium), `engineering:semantic-reviewer` (opus, medium), `engineering:security-reviewer` (opus, medium), `engineering:hard-repair` (opus, high), `engineering:plan-auditor` (opus, high), `engineering:browser-tester` (sonnet, medium, no Bash, has Playwright MCP), `engineering:auditor` (fable, xhigh, Bash guarded by a plugin hook allowlist) |
| Process skills | `/engineering:plan-execution`, `/engineering:implementation-loop`, `verification-loop`, `browser-testing`, `change-review`, `checkpoint`, `change-eval`, `production-readiness-review`, `comment-cleanup` (forked, sonnet, medium, edits comments only) |
| Research skills (forked, no shell) | `docs-check` (sonnet, medium), `literature-review` (opus, medium) |
| User-only escalation | `/engineering:deep-audit` (forks to `engineering:auditor`, fable, xhigh) |

| Agent/skill | Tools |
|---|---|
| `scout`, `architect`, `semantic-reviewer`, `security-reviewer`, `plan-auditor` | read-only by tool list, no shell |
| `test-triage` | read-only by tool list, no Bash (removed: it never reruns anything; refuses a dispatch without captured output or a log path) |
| `browser-tester` | read-only by tool list, no Bash, plus the Playwright MCP tools it needs to drive a browser |
| `docs-check`, `literature-review` | `disallowed-tools` removes Bash, PowerShell, and every edit tool; body says "No shell: use Read, WebFetch, and WebSearch" |
| `deep-audit` (forks to `engineering:auditor`) | Read, Grep, Glob, Bash — the Bash is restricted by the plugin `PreToolUse` hook `hooks/readonly-guard.sh` to an allowlist (`hooks/readonly-allowlist.txt`) keyed to the `engineering:auditor` agent type; every other agent's Bash is unaffected by the hook |
| `bulk-implementer`, `mechanical-worker`, `hard-repair` | full, unguarded shell (implementers) |

Before this release, `test-triage`, `browser-tester`, `deep-audit`, `docs-check`, and `literature-review` all kept Bash and were "read-only" only by instruction. `test-triage`, `browser-tester`, `docs-check`, and `literature-review` no longer have Bash at all. `deep-audit`'s Bash is enforced, not merely instructed: the guard denies any command whose first token is not on the allowlist, and denies redirection, command substitution, backticks, and background `&` outright regardless of the first token. The guard's stated property is narrow: it prevents accidental mutation by the auditor during a normal audit; it is not a sandbox against a hostile repository — obfuscated commands, repository-controlled runners, and interpreters (`bash -c`, `eval`, `env`, `xargs`, `sed`, `awk`) are out of scope, and the allowlist is data that can drift out of sync with the guard's intent. Accepted false-denies (fail-closed, since quotes are not parsed and separators inside them still split the command): `grep 'a;b' f` (the `;` inside the quotes is treated as a command separator, and `b` — not a token on the allowlist — is denied), `git -C d status` (rejected because the allowed-verb check looks at the *second* token, which here is `-C`, not `status`), and `git --no-pager log` (rejected for the same reason: the second token is `--no-pager`).

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
  agents/                         eleven agent definitions
  skills/                         twelve SKILL.md skills; browser-testing bundles a Playwright conventions reference; production-readiness-review bundles references, a probe, and tests
  evals/                          claude plugin eval cases for skill trigger quality
  hooks/                          SessionStart hook and its script
  context/CLAUDE.md               the operating policy
settings.recommended.json         settings merged by install.sh
install.sh                        installer
scripts/                          settings-merge and safe-write/backup/restore helpers used by install.sh
ci/                                fixtures and shims used by ci.sh's scratch-install scenarios
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
rm ~/.claude/rules/engineering-policy.md ~/.claude/engineering-installer.json
```

Then restore `settings.json` (and `CLAUDE.md`, if you used `--policy-target claude-md`) from a backup with `./install.sh --restore` (see `--list-backups` above), or edit them by hand.

## Not included

Credentials, permission allow-lists (machine-specific), history, and project memory.

## License

MIT. See [LICENSE](LICENSE).
