# Changelog

All notable changes to the `engineering` plugin. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Versions from 2.5.1 onward are signed tags `vX.Y.Z`; earlier versions predate tagging and are unlinked.

## [Unreleased]

## [2.8.0] - 2026-09-12

### Added

- `install.sh` settings merge now supports two modes, `enforce` and `defaults` (`--settings-mode`), auto-selected from whether a prior install is evident so an upgrade never silently overwrites edited settings; a drift report is printed whenever `defaults` leaves a recommended value unapplied, ending with `apply the recommended values with: ./install.sh --settings-mode enforce`.
- `--dry-run` previews the settings diff, drift report, policy action, marketplace action, and plugin actions without writing anything; it cannot be combined with `--restore` (exit 2).
- `--restore [STAMP]` and `--list-backups` restore or list structured backups kept at `~/.claude/backups/engineering/<stamp>/` (newest 5 kept); backups are written immediately before any file the installer is about to change.
- `--create-through-dangling` creates the target of a dangling `settings.json` symlink instead of refusing; without it the installer exits 4 with a message naming the flag.
- The operating policy now installs as a standalone rules file, `~/.claude/rules/engineering-policy.md` (default, `--policy-target rules`), which Claude Code loads every session without the SessionStart hook; `--policy-target claude-md` keeps the legacy `CLAUDE.md` layout. A legacy `CLAUDE.md` policy copy is migrated automatically (with confirmation, or `--yes`; declined deterministically under `ENGINEERING_NO_PROMPT=1` or with no TTY) once the installed plugin version supports the rules file; otherwise the installer falls back to `CLAUDE.md` for that run and says why.
- `--purge-official`, `--break-hardlinks`, and the installer marker `~/.claude/engineering-installer.json` (records installer version, timestamp, settings mode, and policy target; used to select the default settings mode on later runs).
- `scripts/merge_settings.py` and `scripts/safe_write.py`: stdlib-only helpers implementing the settings merge and the write/backup/restore/list operations, each with a unit test suite.
- `ci.sh` gains `--quick` and `--full` tiers alongside the existing default run; `--full` adds network-dependent scenarios and fails rather than silently skipping them unless `CI_ALLOW_SKIP=1`.

### Changed

- Settings merge now mirrors Claude Code's own combination rules exactly: single values replace, lists union with duplicates removed, nested blocks merge key by key, `extraKnownMarketplaces` and `managedMcpServers` entries replace whole by name, and `fallbackModel`/`modelPicker`/`availableModels` replace whole — previously the merge only overwrote scalars and merged objects, with no list union and no whole-entry replacement for marketplaces or MCP servers.
- `--no-official` is no longer destructive: it now only skips registering the official marketplace and installing official plugins, and leaves any existing official marketplace/plugin entries in `settings.json` untouched. The previous destructive behaviour (removing existing official entries) moved to the new, explicitly opt-in `--purge-official` flag.
- An explicit `engineering@engineering: false` opt-out in `settings.json` is no longer preserved: running the installer is treated as explicit consent, so `engineering@engineering` is always forced to `true`. This is a deliberate behaviour change from the previous "preserve any explicit `enabledPlugins` false" rule.
- `release.sh` now runs `./ci.sh --full` instead of the default `./ci.sh` when `install.sh`, `ci.sh`, `scripts/`, or `ci/` changed since the previous tag, or when no tag exists yet.
- File writes to `settings.json` and the policy files go through a symlink- and hard-link-aware, atomic write helper (temp file plus `fsync` and `os.replace`) instead of writing the target path directly.

### Fixed

- The SessionStart hook prints a one-line refresh notice when the installed policy copy differs from the plugin's bundled policy, so a plugin update no longer leaves an outdated policy in place silently.
- `repo_probe.py` counts files above the per-file text cap (1,000,000 bytes) as skipped and reports them under limitations; previously they were dropped without mention.
- `comment-cleanup` now protects machine-read comments (lint and type suppressions, build and codegen directives, tooling markers, test directives, generator-consumed docs) and reverts any comment change that alters formatter, lint, type-check, or test results.
- README and SECURITY pinning guidance: a GitHub marketplace can be pinned to a signed tag with `claude plugin marketplace add ahueb/engineering@vX.Y.Z` (verified); the local-clone path remains for signature verification.
- `ci.sh` requires ShellCheck unless `CI_ALLOW_SKIP=1`.

- The installer now writes through an existing symlinked `settings.json`, `rules/` directory, or `CLAUDE.md` instead of replacing the link with a regular file, and preserves the target's existing file mode.
- A hard-linked `settings.json` or policy file is refused before any write (exit 5) instead of being silently detached from its other links by `os.replace`; `--break-hardlinks` opts back in.
- List-valued settings (for example `permissions.allow`) are now unioned instead of being dropped or fully overwritten by the recommendation.
- `extraKnownMarketplaces` and `managedMcpServers` entries are now replaced whole by name per the merge rules, instead of being merged field-by-field, which previously could leave stale sub-keys mixed with new ones.
- An empty or whitespace-only `settings.json` is now treated as `{}` with a printed notice instead of failing to parse.
- The legacy `CLAUDE.md` write (and the `settings.json` write) is now atomic (temp file, fsync, rename) instead of writing the destination path directly, which previously could leave a partially written file if the process was interrupted mid-write.
- A backup taken later in the same run no longer overwrites an earlier backup's manifest entries wholesale; manifests from multiple backups written during one run are now merged instead of the later write clobbering the earlier one.
- `--restore` no longer recreates a backed-up symlink outside your config directory: a missing symlink is now restored only when its recorded target already exists with content identical to the backup, otherwise that entry is refused instead of creating a file at an attacker-controlled path; `--restore` also now takes its own pre-restore backup, printed as `pre-restore backup: <dir>`, before restoring regular files unconditionally, so edits made after the backup being restored are recoverable instead of silently lost.
- The backup/restore manifest's `stored` filenames are now validated as flat names before use, instead of being trusted as written, closing a path-traversal opening in a hand-edited or corrupted manifest.
- Restored file modes are now masked to permission bits only, instead of applying a raw stored mode value verbatim.
- The drift report and the `--dry-run` settings diff now redact `env` values and any key containing `key`, `token`, `secret`, `password`, or `credential`, plus `apiKeyHelper`, as `<redacted>` instead of printing secret values in plain text.
- `--purge-official` no longer misidentifies plugins the user never opted into through the official path as purgeable, so it removes only entries the installer itself registered as official.
- The installer's `set -E` error trap now propagates into functions and subshells as intended, instead of silently not firing for an error raised inside a function call.
- `-h`/`--help` output is no longer truncated.

## [2.7.2] - 2026-09-12

### Changed

- Trigger evals rerun on the current tree: 20/20 recorded in `evals/RESULTS.md`; risk register R3 back to Mitigated.
- CHANGELOG restructured to Keep a Changelog 1.1.0: Unreleased section, Added/Changed/Removed/Fixed groups, linked version headings for tagged releases.
- Agent descriptions are uniformly third-person verb-led and skill descriptions uniformly imperative verb-led (`scout`, `plan-auditor`, `security-reviewer`, `docs-check`, `literature-review`, `production-readiness-review`, `deep-audit` reworded; trigger terms kept).

## [2.7.1] - 2026-09-12

### Fixed

- `browser-tester` declared an inline `mcpServers` block, which Claude Code ignores for plugin agents; the agent's `mcp__playwright` tool pattern also never matched the official plugin's scoped server. The agent now allows `mcp__plugin_playwright_playwright` (official `playwright` plugin, enabled by `install.sh`) and `mcp__playwright` (a user-configured server). The 2.6.0 claim that it works without the official plugin was wrong.
- Docs audit against current Claude Code documentation: `CLAUDE_CODE_SUBAGENT_MODEL_FORCE` takes `1` and forces `CLAUDE_CODE_SUBAGENT_MODEL`, not a model name; the skill listing drops descriptions of the least-invoked skills, not the last listed; `claude plugin eval` needs v2.1.269; pin and verify examples reference the current tag; `comment-cleanup` listed with the process skills.
- `change-review` now dispatches `security-reviewer` at a trust boundary, as the README already claimed; `docs-check` and `literature-review` state their read-only Bash constraint; readiness review text corrected for `browser-tester`; risk register R3 reopened until the trigger evals are rerun.
- Tag `v2.7.0` was signed after the fact; 2.7.0 had been committed without `release.sh`.

## [2.7.0] - 2026-09-12

### Added

- New process skill `comment-cleanup`: repository-wide comment audit that removes dates, phase, plan, spec, ticket, and history references and rewrites the rest so each comment orients an unfamiliar reader in one concise sentence. Runs forked on Sonnet at medium effort with edit tools but no subagents; comment-only edits; formatter and lint run afterwards.

## [2.6.0] - 2026-09-12

### Added

- New agent `browser-tester` (sonnet, medium): executes one named user journey in a headless browser through a self-declared Playwright MCP server (`mcpServers` frontmatter, so no dependency on the official `playwright` plugin) and returns a fixed evidence block. Bash is read-only by instruction; no edit tools.
- New process skill `browser-testing`: launch-once, oracle-first browser verification with exploratory (`browser-tester`), codified (`@playwright/test` spec), and repair modes; bundles `references/playwright-conventions.md` (locators, web-first assertions, waiting, structure, config, commands, MCP tool map, evidence rules).

### Changed

- `verification-loop`, `implementation-loop`, and `production-readiness-review` route user-facing web changes and critical-journey G2 evidence to `browser-testing`. Policy table and README updated.

## [2.5.4] - 2026-09-12

### Changed

- `docs-check` and `literature-review` are model-invocable: `disable-model-invocation` removed and descriptions rewritten as trigger text. `deep-audit` remains user-only.

## [2.5.3] - 2026-09-12

### Changed

- `production-readiness-review`: per-run instruction load cut from about 10,600 to 8,300 tokens with no gate, dimension, overlay, decision rule, or report field removed. Every definition now lives in one place (SKILL.md); `evidence-protocol.md` folded into SKILL.md; `adversarial-checks.md` merged into each gate's "Defeaters" list in `rubric.md`, plus a closing "Final challenge". Before/after run on the fixture repository: same verdict and gate statuses, more accurate evidence-strength ratings, confidence rule now applied correctly, same turn count and cost.
- Probe: signal path caps 25/10, top-15 suffixes, structured warnings without absolute paths, `truncated_signals`, `--compact`; schema 2.1. Output on this repository 27% smaller.

### Removed

- Prompt audit (Fable 5.1): removed the numeric per-agent output cap and the progress-narration suppressor from the policy; plan-auditor no longer presumes incompleteness; `independent-review` removed as a duplicate of `semantic-reviewer` and `change-review` (`deep-audit` remains the escalation).

### Fixed

- `.allowed_signers` is now actually committed (a stray `.gitignore` had excluded it since 2.5.1); the stray ignore file is removed.

## [2.5.2] - 2026-09-12

### Fixed

- Docs: `engineering@engineering@<version>` does not pin for a GitHub-sourced marketplace; pinning and rollback now documented via signed-tag checkout plus a directory marketplace, verified in a scratch config. All commits on `main` are signed and GitHub enforces signatures.

## [2.5.1] - 2026-09-11

### Added

- Local CI gate `ci.sh` (lint, both manifests under `--strict`, probe tests, frontmatter and cross-reference checks, hook contract, scratch install) wired into `.githooks/pre-push` and `release.sh`. No GitHub Actions or server-side hooks.
- Releases are signed tags `vX.Y.Z`; `.allowed_signers` committed for `git tag -v`. `main` is branch-protected (linear history, no force push or deletion, required signatures, enforced for admins).
- `SECURITY.md`: reporting path, response expectations, verification and pinning instructions.
- `docs/risk-register.md`: residual risks with owners and reassessment triggers.
- Trigger evals: every positive case now scaffolds a fixture repository (`evals/fixture-service.sh`, `case.yaml` per case); readiness skill description covers operational/launch readiness, canary or GA assessment, on-call handover, and adversarial "disprove it is ready" requests. Results (20/20) recorded in `plugins/engineering/evals/RESULTS.md`.

### Changed

- README: verify, pin, and roll back a release; CI section; ownership.

## 2.5.0 - 2026-09-11

### Changed

- `install.sh`: parses and validates `settings.json` before touching `CLAUDE.md`; registers the marketplace before any file write and surfaces the real error; writes a `settings.json.bak-` only when the merged content actually changes; quote-safe opt-out check for config paths containing `'`; documents that `engineering@engineering` is always enabled.
- `release.sh`: parses `--no-commit` in any position; validates the current version is `x.y.z` before bumping; gates the version bump on `claude plugin validate --strict`, restoring the prior version on failure; refuses to run on a working tree with unrelated changes; commits only `plugin.json` and `CHANGELOG.md`.
- SessionStart hook: also fires on `resume`; the policy is considered present only when the first line of `CLAUDE.md` is exactly `# Agent operating policy`, so a copy under a different heading is not mistaken for it.
- `security-reviewer` and `semantic-reviewer` accept a whole-candidate scope (not just a diff) and, having no shell, name the command a claim would need rather than asking to run one.
- `production-readiness-review`: literature refresh — SLSA v1.2 (source track), EU Cyber Resilience Act reporting-obligation overlay, EU AI Act Article 50 transparency duties, CISA 2026 SBOM minimum elements, restore-test recency, named rollback-trigger metrics, SLO ownership and error-budget consequence, CI hardening (token permissions, branch protection, signed releases), and a change-authorization/audit-record requirement where SOC 2 CC8.1 or ISO 27001 A.8.32 applies. E4 now requires independent reproduction under bounded real-production or realistic adverse conditions, cumulative on E3.
- `repo_probe.py`: bounded by `--max-seconds` and `--max-text-bytes`; excludes `.git` gitlinks so submodules are not miscounted; new content-signal keys for CI permissions, signed releases, vulnerability-reporting paths, and dependency automation. Probe tests extended accordingly.

### Fixed

- Policy (`context/CLAUDE.md`): corrects the superpowers mapping (`plan-execution` replaces both `executing-plans` and `subagent-driven-development` and overrides any build/test step in a superpowers prompt file; `dispatching-parallel-agents` work that edits code goes to `bulk-implementer` or `hard-repair`, not `scout`), restates the read-only/no-edit-tools wording precisely, and makes the plan-execution no-test rule explicitly override prompt-file text. `test-triage` moves to `sonnet` at `low` effort.

## 2.4.1 - 2026-09-11

### Changed

- Shorter `production-readiness-review` description.
- `settings.recommended.json` sets `skillListingBudgetFraction` to 0.02: at the 1% default, 200K-context models drop the descriptions of the last skills in the listing, which disables automatic invocation for them.

## 2.4.0 - 2026-09-11

### Added

- `production-readiness-review` skill: read-only, gate-first production readiness audit with hard gates, graded dimensions, domain overlays, adversarial falsification, and a bundled repository probe with tests. Evidence collection fans out to `scout`, `security-reviewer`, and `semantic-reviewer`.
- `evals/`: twenty `claude plugin eval` trigger cases for the readiness skill.

### Changed

- Policy: the readiness review is standalone and never chained into implementation, verification, or plan execution.

## 2.3.0 - 2026-09-11

### Added

- `plan-execution` skill: partitions a plan into disjoint-file packages, fans all of them out to parallel `bulk-implementer` agents with no per-package build or test, verifies once after merge, then audits adversarially.
- `plan-auditor` agent: read-only, `opus` at high effort, proves completeness and correctness of a merged implementation against its plan.

### Changed

- `bulk-implementer` builds and tests only when the parent asks.
- Policy routes superpowers `executing-plans` and `subagent-driven-development` through `plan-execution`.

## 2.2.0 - 2026-09-11

### Changed

- Policy maps superpowers subagent roles onto engineering agents: implementer → `bulk-implementer`, reviewers → `semantic-reviewer` and `security-reviewer`, late fix rounds → `hard-repair`, lookups → `scout`.
- `implementation-loop` invokes `superpowers:test-driven-development` and `superpowers:systematic-debugging` when present, and closes with `verification-loop` and `checkpoint`.
- `verification-loop` invokes `superpowers:verification-before-completion` when present.
- `checkpoint` records the superpowers plan file and completed task numbers when work follows a plan.

## 2.1.0 - 2026-09-11

### Added

- `release.sh` added for version bumps and local plugin refresh.

### Changed

- Agents and skills select models by alias (`haiku`, `sonnet`, `opus`, `fable`) so they resolve on every provider.
- `security-reviewer` runs on `opus` at medium effort; `semantic-reviewer` runs at medium effort.
- SessionStart hook also fires for forked sessions.
- `install.sh --no-official` omits the official plugins from settings; explicit user opt-outs are preserved; `--source` requires a value.
- README documents update flow, model and plan requirements, and the exact read-only guarantees.

## 2.0.0 - 2026-09-11

### Added

- First release of the `engineering` plugin and marketplace: operating policy, eight agents, five process skills, four user-invoked escalation skills, SessionStart policy hook, recommended settings, and `install.sh`.

[Unreleased]: https://github.com/ahueb/engineering/compare/v2.8.0...HEAD
[2.8.0]: https://github.com/ahueb/engineering/compare/v2.7.2...v2.8.0
[2.7.2]: https://github.com/ahueb/engineering/compare/v2.7.1...v2.7.2
[2.7.1]: https://github.com/ahueb/engineering/compare/v2.7.0...v2.7.1
[2.7.0]: https://github.com/ahueb/engineering/compare/v2.6.0...v2.7.0
[2.6.0]: https://github.com/ahueb/engineering/compare/v2.5.4...v2.6.0
[2.5.4]: https://github.com/ahueb/engineering/compare/v2.5.3...v2.5.4
[2.5.3]: https://github.com/ahueb/engineering/compare/v2.5.2...v2.5.3
[2.5.2]: https://github.com/ahueb/engineering/compare/v2.5.1...v2.5.2
[2.5.1]: https://github.com/ahueb/engineering/releases/tag/v2.5.1
