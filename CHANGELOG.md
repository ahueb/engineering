# Changelog

All notable changes to the `lathe` plugin (named `engineering` before 3.0.0). The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html). Versions from 2.5.1 onward are signed tags `vX.Y.Z`; earlier versions predate tagging and are unlinked.

## [Unreleased]

### Changed

- The plugin's source folder moved from `plugins/engineering/` to `plugins/lathe/`, and the marketplace entry's `source` is `./plugins/lathe`. Installed copies are unaffected apart from the version; the plugin directory listing's source path is now `plugins/lathe`.

## [3.0.0] - 2026-10-04

### Changed

- **Breaking:** the plugin is renamed from `engineering` to `lathe`, because the Claude plugin directory already lists an unrelated plugin named `engineering`. Skills are now `/lathe:<skill>`, agent types `lathe:<agent>`, and the install id `lathe@engineering`. The marketplace, the repository, the policy file `rules/engineering-policy.md`, the installer marker, the backups directory, and the `ENGINEERING_*` variables keep their names. The read-only guard keys on `lathe:auditor`; CI fails if the guard or `deep-audit` names another auditor, or if a document other than this changelog still names a pre-rename `engineering:` skill or agent.
- `install.sh` uninstalls an installed `engineering@engineering` once `lathe@engineering` is installed, and `--dry-run` says it would; a failed uninstall is a warning that prints the manual command. The settings merge drops `engineering@engineering` from `enabledPlugins`, and that entry still counts as a prior install when the settings mode is chosen.
- The repository is renamed from `ahueb/engineering` to `ahueb/lathe`; links, the pinning examples, and `release.sh`'s compare links use the new name, and `install.sh` treats a marketplace registered from `ahueb/engineering` as the same source as `ahueb/lathe` instead of refusing it as bound elsewhere.
- Hook commands use the form the official plugins use, `bash "${CLAUDE_PLUGIN_ROOT}/hooks/<script>.sh"`, without the `shell` key.
- `browser-testing` runs Playwright as `npx --no playwright ...`, so npx never downloads and runs a Playwright the project does not have, and asks the user before `playwright install`. A signed-in journey starts from the project's saved login state or a disposable test account the user provides, never from credentials read from environment variables or files.

### Added

- `assets/icon.png`, a 512x512 icon set as the plugin's `icon`; CI checks that it is a 512x512 PNG inside the plugin.
- README sections "Upgrading from the `engineering` plugin" and "Credentials and data access".
- CI scenario S39: the rename migration, including the dry-run report and a failed uninstall.

## [2.13.1] - 2026-10-03

### Changed

- `mechanical-worker` runs at `medium` effort instead of `low`, runs its check as its own command after the edits, retries a check a permission rule denied once as a single plain `python3` command, and says which check could not run instead of reporting the change done. In a measured rename task the tests actually ran in 9 of 12 runs, against 0 of 9 with the previous text at `low`, at the same cost per run.
- README's Tuning section states how agent `effort` frontmatter, `CLAUDE_CODE_EFFORT_LEVEL`, `maxEffortLevel`, and `modelSettings` interact on Opus 5.5 and Sonnet 5.5.

### Added

- An Effort measurements section in `plugins/engineering/evals/RESULTS.md`: `bulk-implementer` and `architect` stay at `medium` because `high` showed no clear gain; `mechanical-worker` moves to `medium`.

## [2.13.0] - 2026-10-03

### Changed

- `security-reviewer` traces outward from the change to callers and config-defined entry points, deployment, and network exposure before it looks for vulnerabilities, marks facts observed or assumed, and marks settings the repository cannot show as undetermined. It looks for implicitly applied controls and refutes each candidate with a located control, rates severity from reach, attacker position, and impact (no CVSS numbers), and returns EXPOSURE, FINDINGS (or NO_FINDINGS), and UNDETERMINED, plus CONTROLS for a whole-candidate review. It reads the new exposure reference for CI, container, cloud, network-service, agent-tool, and shared-host surfaces.
- `change-review`, `implementation-loop`, and `plan-execution` also dispatch `security-reviewer` for listener, deployment, privilege, CI, and agent-tool configuration changes and pass known deployment and exposure facts, marked as supplied rather than verified; `change-review` waits for the reviewer and writes one report that carries its UNDETERMINED items and the exposure facts behind each finding; `production-readiness-review` passes the target exposure and environment boundary; the policy's delegation row matches.

### Added

- `plugins/engineering/references/security-exposure.md` and `security-source-basis.md`.
- `behaviour-security-1` through `-5`: change-review cases grading detection (public route to shell command, Redis published on all interfaces, `pull_request_target` with secrets) and restraint (operator-only caller, authorization applied by a blueprint hook and scoped base class).
- 2026-10-04 rows in `plugins/engineering/evals/RESULTS.md`: on the final graders the security suite passes every grader 3/3 on the evidence, against the 2.12.0 reviewer's 0/3 on case 1's deployment evidence and 2/3 on case 4's undetermined token setting; `comment-guidance-change-review` passes 3/3; the readiness suite passes scenarios 1-3 and 5-8 3/3, and scenario 4's `rubric-4` is equally noisy on both trees.

## [2.12.0] - 2026-10-03

### Changed

- The readiness probe no longer runs filter drivers that the reviewed repository's own config defines: before `git status` it blanks the `clean`, `smudge`, and `process` commands of every driver defined outside system and global config, read through git's own config sequence so includes and conditional includes resolve as they do for `git status`; it disables lazy fetching and skips status in a partial clone; it ignores replace refs and compares file content rather than stat data a shipped index could forge; it skips status when the index marks a present file assume-unchanged or skip-worktree or when git's work tree does not contain the scan root; it never looks inside a submodule's work tree while still reporting a submodule checked out at another commit; and it reports status as not collected, with a reason, when a driver cannot be blanked or status fails (risk register R20, now mitigated). It also reports an unstaged change on the first status line with its own code and an unborn HEAD as null. The probe's JSON schema is 2.2: `git` gains `status` and `status_skip_reason`, and `dirty` and the status counts are null when status was not collected. `SECURITY.md` says to sanitize any other untrusted checkout with `git clone --no-local`.
- `release.sh pr` waits up to 5 minutes for GitHub to report the PR's checks before watching them, instead of failing with "no checks reported" right after creating the PR, and exits 1 with the manual commands if none appear. `release.sh tag` checks the installed plugin version after `claude plugin update` and, if it is not the tagged version, exits 1 with the steps to sync local `main` and update again, instead of always printing "local install updated"; the steps start by checking for uncommitted work, which their `git reset --hard` would discard.
- `production-readiness-review` gives every material gap its own row in a gap table; lists CONDITIONALLY READY pre-launch checks in a table that says why each cannot be evidenced before deployment; names what is not a pre-launch check (group membership and access rights in the access system, RBAC committed in the repository, on-call rosters and paging tests, image attestation and registry digests, staging drills, configuration in the repository) and says to evidence it, rate its gate UNKNOWN, or, if the exposure does not need it, accept the gap with a control; requires nothing but the pre-launch checks before a bounded exposure starts, so any other action required first makes its gate UNKNOWN and the verdict NOT READY; and records each applicable domain overlay in G12's row.
- `bulk-implementer` reads `comment-guidance.md` before writing or rewriting any documentation, docstring, or contract text, and C09 adds that new documentation states only what the code or the authorized contract establishes.
- `plan-auditor` counts each top-level plan item once in its `PLAN ITEMS:` line.
- The readiness eval suite's documented invocation grants the six hardened read-only git forms the skill uses instead of `Bash(git *)`, says these rules are not a read-only boundary, and raises its cost cap to 16 USD.
- `tests-ran` (`comment-guidance-implementation`, `-plan`, `-repair`) requires the result, passing or failing, of the Bash call that ran `-m unittest`, with at least one test, so printing a stored log no longer satisfies it; `no-worker-test-command` matches test, lint, and commit commands only where a command starts (after any variable assignments, `env`, `time`, `nice`, `timeout`, or interpreter options), so `which pytest` no longer fires it and `pytest>log` does; `comment-guidance-doc-plan`'s `plan-items-format` accepts a quoted, listed, or emphasized `PLAN ITEMS: 2 total` line.
- Readiness scenario 4's fixture adds the on-call group's production rights to stop the canary, the window's on-call rota, and the image attestation's verification; scenario 5's fixture adds the customer auth, alerting, pinned image, and dated restore drill its prompt now names; scenario 6's `rubric-5` names the high-availability claim it rates in a shorter criterion.

### Added

- `behaviour-comment-cleanup-reliance` (B09): `comment-cleanup` must keep and report, not rewrite, an unenforced thread-safety comment that a caller and a test rely on.
- `prelaunch-table` on `behaviour-prr-4`: a CONDITIONALLY READY report must contain the pre-launch table.
- `scripts/eval_recheck.py --include-passes --grader GLOB`, to recheck the judgments the harness passed as well; its prompt no longer tells the judge which verdict it is rechecking.
- 2026-10-03 rows in `plugins/engineering/evals/RESULTS.md` for these changes: all eight readiness scenarios pass 3/3 on the evidence, every comment-guidance case passes at least 2/3, and both trigger suites fire on 30/30 positive and 0/30 negative runs.

## [2.11.0] - 2026-10-03

### Changed

- `SECURITY.md` no longer says a hostile repository cannot execute commands through the readiness probe: its git hardening stops hooks and fsmonitor, not repository-configured filter drivers (risk register R20). The readiness skill limits further git commands to `rev-parse`, `ls-tree`, `cat-file -t/-s/-p`, and `diff-tree --no-textconv --no-ext-diff`, and says to review an untrusted local checkout in a disposable environment.
- `comment-cleanup` rewrites an unenforced behavioral guarantee in readable code (thread-safety, ordering, atomicity, idempotency, exactly-once) to what the code does and what callers must do, instead of deferring it, when no caller, test, or specification relies on the guarantee; if one does, it defers and reports the conflict, and Defer stays for claims whose evidence is out of reach. Its description now names check, review, or audit for accuracy, staleness, or drift.
- `verification-loop`, `implementation-loop`, `plan-execution`, and the `hard-repair` agent treat a permission rule's denial of one command form (not a user's rejection) as not denying every form: they retry once as one plain command (no redirect, pipe, or chain; Python as `python3` on POSIX systems) and copy required output into a file from the tool result. `plan-execution`'s post-verification `plan-auditor` pass is required and reported.
- `production-readiness-review` gives every material gap a disposition (blocks the exposure, or acceptable with a named control once blockers close) on every verdict, including NOT READY; resolves every UNKNOWN gate before choosing CONDITIONALLY READY, which may depend only on pre-launch checks of production state that exists after deployment, before any canary traffic, and cannot be evidenced earlier; and runs its probe as its own call, with further `git` commands run separately, without `-C`, with the probe's hardening, and limited to commands that run no repository-configured filter or diff driver.
- `change-review` dispatches `security-reviewer` on every trust-boundary change however small, says so in the report, and drops any finding or note whose only basis is cosmetic formatting or whitespace that changes no behavior.
- The recommended session model is `opus[1m]` (Opus 5.5) at `xhigh` effort, replacing `fable[1m]` at `low`; the per-model effort entries move from `claude-fable-5-1` (`low`) and `claude-sonnet-5` (`medium`) to `claude-opus-5-5` (`xhigh`) and `claude-sonnet-5-5` (`medium`).
- `auditor` (and so `/engineering:deep-audit`) runs on `opus` instead of `fable`, still at `xhigh`.
- `scout` runs on `sonnet` at `low` effort instead of `haiku`.
- Every `claude plugin eval` case pinned to `claude-sonnet-5` is pinned to `claude-sonnet-5-5`, and `ci.sh --full`'s rules-file load scenario (S21) calls `claude -p --model sonnet --effort low` instead of `--model haiku`.
- `install.sh` requires Claude Code 2.1.284 or later (was 2.1.267), the first version whose `opus` and `sonnet` aliases resolve to Opus 5.5 and Sonnet 5.5; CI's pinned Claude Code moves from 2.1.269 to 2.1.284 so its scratch installs still pass that check.
- Every multi-bullet `llm` rubric in the eval cases is split into one grader per bullet (`rubric`, `rubric-2`, ...), because the eval judge returned FAIL on whole rubrics whose every bullet it passed when judged alone (`comment-guidance-review-only`, `behaviour-prr-6`).
- `comment-guidance-review-only` drops its `no-bash` grader, which counted refused calls to a tool the run never had, and its no-change bullet now forbids claiming any edit or proposing executable-code changes while allowing the suggested comment wording its prompt permits.
- `comment-guidance-plan`'s `doc-contract-preserved` judges `docs/window_contract.md` against PLAN.md's interface stated inline, and `comment-guidance-implementation`'s unrelated-comments criterion states the file's pre-change comments inline, since the judge sees only the changed file; `comment-guidance-repair`'s documentation bullet names the module docstring, and `behaviour-prr-3`'s `rubric-5` states the gaps it refers to.
- Readiness scenario 4 is now a properly bounded 1% internal canary that expects CONDITIONALLY READY (its fixture has a wired, per-track kill switch, SSO-only routing with strict mTLS, canary orders written to `orders` as stable writes them and recorded in a new `canary_orders` table, so the orders schema is unchanged; a canary commit that adds only canary objects and the canary route at weight 0 until the window opens; corp-gateway's SSO policy in the repository; a real lockfile, a consistent release history, and dates relative to the day it is built), and scenario 5's prompt names its exposure (GA to all customers).
- `comment-guidance-mechanical`'s hardware-sentence ground truth (F-BUFFER-HARDWARE) covers the hardware wording only; "our message buffer" may become "our message queue".
- `comment-guidance-plan` checks worker conduct with `bulk-implementer-instructed` (two dispatches carry the no-build/no-test instruction) and `no-worker-test-command` (a full-trace regex over subagent Bash calls for a fixed list of test, build, lint, and commit invocations), replacing `no-worker-test-execution`, whose judge could not see the dispatch.
- Readiness scenario 5's `rubric-4` asks for a blocker-or-acceptable call with a reason for each AI-specific gap, so a justified all-blockers report passes; it previously failed reports that gave every gap its own blocking reason.
- `comment-guidance-plan`'s `bulk-implementer-instructed` accepts "Do NOT build" and "Don't build" as well as "Do not build".
- `behaviour-prr-4`'s `gate` grader accepts only `GATE G5: PASS` (a canary's deployment gate cannot be N/A), and `comment-guidance-doc-plan`'s `no-plan-complete` also catches `PLAN_COMPLETE` at the start of a line when it is bold, backticked, indented, quoted, a list item, or a heading, or is followed by the coverage line.
- Mechanical criteria in `comment-guidance-doc-plan`, `-mechanical`, `-repair`, `behaviour-prr-4`, and `behaviour-comment-cleanup` are regex graders, and a duplicate `behaviour-prr-7` bullet is dropped.
- `plugins/engineering/evals/README.md` runs each read case in its own invocation so only `comment-guidance-change-review` gets `Bash(git *)`, and documents what `tool_used`, the judge, and prefix Bash grants actually do.

### Added

- A `repo-evidence` regex grader on `behaviour-prr-1`..`-8`: the report must cite one of the paths its scenario's fixture creates, so an audit of an empty workspace no longer passes.
- Regex graders for mechanical criteria: `gate-lines` and `gate-evidence` on `behaviour-prr-1` (12 `GATE` lines; an E-level on each rated gate row) replace its first rubric bullet, and `hardware-sentence-unchanged` on `comment-guidance-mechanical` replaces the bullet that kept the UART hardware sentence; the remaining `prose-renamed` grader states that sentence as the rename's one exception.
- The readiness behaviour suite's documented invocation grants `Bash(git *)`, so the skill can tie HEAD to the tagged release with hardened git calls.
- `/evals/results/` in `.gitignore`, for results written when the repository root is the eval target.
- `cleanup-trigger-01`..`-10` and `cleanup-no-trigger-01`..`-10`: trigger-quality cases for `comment-cleanup`, scaffolded with the comment-guidance review fixture.
- `probe-ran` on every readiness scenario and `tests-ran` on `comment-guidance-implementation`, `-plan`, and `-repair`: trace regexes over tool results (the probe's JSON output; unittest's "Ran N tests" line, where a `Read` or a numbered `Grep` of a stored log does not count).
- `rubric-4` on `behaviour-prr-4`: a CONDITIONALLY READY report may depend only on pre-launch checks of production state, each with an owner and closing evidence.
- `no-conditional-over-unknown` on `behaviour-prr-4`: a CONDITIONALLY READY report fails if any gate line is UNKNOWN, because the skill defines a gate UNKNOWN as material evidence missing and makes a material unknown NOT READY.
- Results for the comment-guidance baseline-vs-candidate comparison in `docs/change-eval/comment-guidance-2026-09.md` (2026-10-03): accepted as a three-run screen, with B01, B05, and B02 (skill invocation) improved, B06-B08, I01, I03, and I04 unchanged, I02 passing on the candidate, B03 inconclusive because every baseline run stopped at its denied command, and B04 mixed (completed where the baseline stopped; one contract document adds a guarantee).
- Readiness scenario 8: the original scenario-4 canary proposal, whose kill switch is never wired in, expecting NOT READY with G5 FAIL.
- `scripts/eval_recheck.py`, which replays failed `llm` graders with a judge that must give reasons and reports a failed judge call as NEEDS REVIEW, with unit tests run by `ci.sh` and on the Windows CI job.
- Risk register entries R16–R19 for measured eval findings (R16, R17, and R19 since closed; R15 open; R18 partially mitigated) and R20 for the readiness probe's `git status`, which can run a filter driver the reviewed repository's own configuration defines, and 2026-10-02/03 rows in `plugins/engineering/evals/RESULTS.md`.

## [2.10.0] - 2026-09-16

### Changed

- The global policy gains a "Comments and docstrings" section and drops the "concise comments only where hard to understand" sentence.
- `comment-cleanup` is rewritten to preserve the semantic content of existing comments and docstrings, adds an audit-only mode, and removes the sentence-count quota, history-stripping behavior, and formatter-scope broadening.
- Documentation obligations are integrated into `implementation-loop`, `verification-loop`, `plan-execution`, `change-review`, `checkpoint`, and `production-readiness-review`, and into eight agents.
- `plan-auditor`'s completion rule is now artifact-aware.

### Added

- The canonical comment-guidance reference and its source basis under `plugins/engineering/skills/comment-cleanup/references/`.
- `scripts/comment_guidance_checks.py`, a standard-library structure/artifacts checker, with unit tests in `scripts/tests/test_comment_guidance_checks.py`.
- `plugins/engineering/evals/comment-guidance-support/`: fixture builder, fixture data, and manifest shared by the new comment-guidance eval cases.
- Seven new `claude plugin eval` cases (`comment-guidance-review-only`, `comment-guidance-implementation`, `comment-guidance-plan`, `comment-guidance-change-review`, `comment-guidance-mechanical`, `comment-guidance-repair`, `comment-guidance-doc-plan`) and a strengthened `behaviour-comment-cleanup` case with file-content graders.
- `docs/change-eval/comment-guidance-2026-09.md`, an evaluation protocol with results recorded as `NOT_RUN`.
- CI integration of the new checker, its unit tests, and the structure check on Linux, macOS, and Windows.

### Fixed

- `session-start.sh`'s opening comment described the policy-injection fallback backwards.
- `production-readiness-review/SKILL.md` said `browser-tester` has Bash.

## [2.9.1] - 2026-09-12

### Fixed

- CI runner-only failures in the 2.9.0 tree, found by the first Actions run on `main` (run 34713026146): `ci.sh`'s doc cross-reference scan was a heredoc inside `$( )` whose text contains `)`, which bash 3.2 cannot parse (the `macos` job); the release and pre-push scenarios built their scratch repository with `git clone` of the checkout, which fails on the runner's shallow checkout, and now use `git archive` and report the underlying error (the `linux` job); `scripts/ci/install-claude.ps1` counted primary keys from a separate `gpg --list-keys` call that produced a different count on Windows, and now counts them from the same `--fingerprint` output it checks the fingerprint in, naming the count on failure (the `windows` job).
- Three `safe_write` unit tests compared a disclosed path against the unresolved temp path and failed on macOS, where the temp directory is itself a symlink; `ci.sh` now prints the failing test names when the unit-test step fails. `scripts/ci/install-claude.ps1` hands gpg (the MSYS build from Git for Windows, which reads a Windows path as relative) every path in POSIX form (`/c/Users/...`) and keeps gpg's stderr for its failure message; the earlier Windows failures were an empty keyring caused by that path form, not a key problem. The `windows` unit-test step, running for the first time, showed eight symlink and replace-open-file tests failing on Windows semantics that are out of scope (risk register R5); they are now skipped on Windows, and `merge_settings.py` writes its JSON as UTF-8 regardless of the console code page (its non-ASCII round trip failed under cp1252).
- The documented branch-protection command used `PATCH .../required_status_checks`, which returns 404 until status checks are enabled; the docs now give the `PUT .../protection` form that was actually used.

- `release.sh pr` used `gh pr merge --rebase`, which GitHub refuses on `main` because the branch requires signed commits and GitHub cannot sign the commits a rebase merge rewrites (`Base branch requires signed commits. Rebase merges cannot be automatically signed`); it now squash-merges with the subject `Release engineering X.Y.Z`, which is what `release.sh tag` checks.

### Notes

- 2.9.0 reached `main` by a direct push made while the required status check was being applied (the documented `PATCH` command had failed silently), before the protection existed, and was never tagged. The first release through the PR flow with the required check in force is the next one.

## [2.9.0] - 2026-09-12

### Added

- `.github/workflows/ci.yml`: `linux`, `macos`, and `windows` jobs on every PR to `main`, push to `main`, and `v*` tag push, each installing Claude Code at the version pinned in `scripts/ci/claude-version.txt` and verified against a vendored Anthropic release key (fingerprint `31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE`) and the release manifest's SHA256 before running `./ci.sh` (or, on `windows`, the Python unit tests and a shell syntax pass); `linux` is the required status check on `main`, applied via `scripts/ci/README.md`'s documented `gh api` command.
- `install.sh` rollback: after the first file a run writes, an unexpected failure or an explicit exit 3-7 restores every file the run wrote or removed (and nobody else changed since) and exits with the original code; `--no-rollback` disables it and prints the manual restore command instead. `scripts/safe_write.py mark-written` records the post-write hash of every file an installer run actually writes or removes; `restore --only-run-files` uses it to scope a rollback and to refuse (exit 12) a stamp that marks nothing as written by an installer run.
- `install.sh --restore` prints `outside config dir: <rel> -> <real path>` for every backed-up entry whose real target resolves outside the config directory, before writing anything; `--no-outside-cfg` refuses those entries (exit 8) instead of restoring through them.
- Exit code 11: a run that installs `engineering@engineering`, `settings.json`, and the policy successfully but has one or more official plugins fail to install now says so and exits 11, instead of finishing silently as if nothing had failed.
- `release.sh prepare <bump> [--no-pr]`, `release.sh pr X.Y.Z`, and `release.sh tag [X.Y.Z]`: a PR-based release flow that opens, watches, and squash-merges a `release/vX.Y.Z` branch through `gh` before tagging, so every released commit has passed the required GitHub Actions check on a tree identical to what was merged.
- `plugins/engineering/agents/auditor.md`: the plugin agent `deep-audit` now forks to, running Read/Grep/Glob/Bash at Fable/xhigh with no worktree isolation; its Bash is restricted by the new plugin `PreToolUse` hook `plugins/engineering/hooks/readonly-guard.sh` (matcher `Bash|PowerShell`, keyed to `agent_type` `engineering:auditor`) against `plugins/engineering/hooks/readonly-allowlist.txt`, a read-only-command allowlist.
- `scripts/ci/install-claude.sh`, `scripts/ci/install-claude.ps1`, `scripts/ci/claude-version.txt`, `scripts/ci/anthropic-release-key.asc`, `.github/CODEOWNERS`.

### Changed

- Microsecond install/pre-restore stamps (`YYYYMMDDTHHMMSS.ffffffZ-<pid>`, bash 3.2 lacking `date` microseconds so the value is generated in Python); the previous one-second form is still accepted and orders correctly against the new form even within the same second.
- `test-triage` and `browser-tester` no longer have Bash at all (previously read-only by instruction only); `test-triage`'s instructions now say it never reruns anything and refuses a dispatch without captured output or a log path.
- `docs-check` and `literature-review` gain `disallowed-tools: Bash, PowerShell, Edit, Write, NotebookEdit, Agent, Skill, Artifact` (previously Bash was available and excluded only by instruction); their bodies now read "No shell: use Read, WebFetch, and WebSearch."
- `plugins/engineering/skills/production-readiness-review/references/output-template.md`: the report now begins with a machine-checkable `VERDICT: READY|CONDITIONALLY READY|NOT READY` line and one `GATE G<n>: PASS|FAIL|UNKNOWN|N/A` line per gate, replacing the human-only `**Verdict:**` line, so the two representations of the verdict cannot disagree.
- `main` now requires the `linux` status check and rejects direct pushes of unchecked commits (including from the maintainer); releases go through `release.sh prepare`/`pr`/`tag` instead of a direct commit-and-tag on `main`. `.githooks/pre-push` skips its own `ci.sh` run only for a release push (`ENGINEERING_RELEASE=1` and every pushed ref is a release branch or version tag).

### Fixed

- `readonly-guard.sh` (found by the pre-release adversarial audit, all with `ci.sh` guard-table rows): quoting and backslash escapes bypassed the allowlist's argument checks (`sort a "-o" b`), so each simple command is now tokenised with shell quoting rules and any `$` or backslash is denied outright; `find -fprint0`, `rg --pre`/`--pre-glob`/`--hostname-bin`, and `file -C` were allowed write or execute paths; the guard failed open when `python3` was missing, the input was not JSON, or `tool_input` had no `command` field, and now fails closed for `engineering:auditor` only. `ci.sh` feeds the guard a recorded real PreToolUse payload (`ci/fixtures/pretooluse-payload.json`) instead of a hand-built one.
- `scripts/ci/install-claude.sh`/`.ps1`: no longer execute the unverified `claude.ai/install.sh`/`.ps1` before any check; the binary named in the signature-verified manifest is downloaded directly and its SHA256 and size verified before it is placed on `PATH`; the signature check requires a `VALIDSIG` bound to the pinned fingerprint and exactly one imported key; the installed version is asserted. `actions/checkout` is pinned by commit SHA with `persist-credentials: false`.
- `scripts/safe_write.py`: a restore could create a file and parent directories outside the config directory through a dangling symlink (now refused); a file under a symlinked parent directory outside the config directory could never be restored (now restored over an existing path and disclosed); a run's own backup stamp could be pruned by five pre-existing future-dated stamps (now protected).
- `install.sh` rollback no longer deletes the installer marker unconditionally; the marker is removed by the same changed-since-written check as every other created file. `.githooks/pre-push` no longer skips `ci.sh` on an empty ref list or a ref deletion. `release.sh pr` removes its temporary PR body on every failure path after the PR is created.
- `evals/change-eval/plan-execution/run.sh` used GNU-only `date +%s.%N` and interpolated `--budget-usd` into Python source; `lib/summarize.py`'s cost rule was two-sided (a cheaper variant counted as out of bounds).
- `release.sh`'s `EXIT` trap dereferenced `ORIG_MANIFEST`/`ORIG_CHANGELOG`/`CI_LOG` after `do_prepare` had already returned; they are no longer `local`, so the trap no longer fails under `set -u` after a successful release.

### Evaluation results

- Readiness behaviour suite (`behaviour-prr-1`..`-7`, 7 cases × 3 runs, sonnet, explicit slash invocation, cost 9.84 USD): `VERDICT`/`GATE` regex graders passed on every run for scenarios 1, 2, 3, 5, 6, 7; the `llm` rubric passed 20 of 21 runs (one FAIL on scenario 5). Scenario 4 (1% internal canary behind a kill switch) returned `VERDICT: NOT READY` on all 3 runs where the scenario expects `CONDITIONALLY READY` (open finding, see risk register R15).
- Comment-cleanup behaviour case: a first batch of 3 runs (0.48 USD) passed 2 of 3 because the tool grants omitted `Skill`, which a forked skill needs; with `Skill` granted, 3 of 3 runs passed every grader (0.58 USD).
- Benchmark (`evals/change-eval/plan-execution/`, 3 fixtures × 2 variants × 3 runs, 12.51 USD): **no decision** under the pre-registered rule — one fixture's within-cell cost spread exceeded 20% and the other two pairs were incomplete because the bounded-check variant skipped subagent fan-out in 3 of 9 runs (the current variant in 1 of 9); the only failing-tests run was a bounded-check run without fan-out. Full record in `docs/change-eval/plan-execution-2026-09.md`. The `plan-execution` skill itself is unchanged in this release.
- CI matrix (spike run 34706890297 on the pre-hardening tree): `linux` green in about 2 minutes on the default tier with the verified installer; `macos` green under `GNU bash 3.2.57` with the same tier; `windows` failed on a PowerShell fingerprint-pattern bug, fixed in this tree and proven by the release PR's checks. `windows` runs unit tests and shell syntax only and is informational, not a required check.

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

[Unreleased]: https://github.com/ahueb/lathe/compare/v3.0.0...HEAD
[3.0.0]: https://github.com/ahueb/lathe/compare/v2.13.1...v3.0.0
[2.13.1]: https://github.com/ahueb/lathe/compare/v2.13.0...v2.13.1
[2.13.0]: https://github.com/ahueb/lathe/compare/v2.12.0...v2.13.0
[2.12.0]: https://github.com/ahueb/lathe/compare/v2.11.0...v2.12.0
[2.11.0]: https://github.com/ahueb/lathe/compare/v2.10.0...v2.11.0
[2.10.0]: https://github.com/ahueb/lathe/compare/v2.9.1...v2.10.0
[2.9.1]: https://github.com/ahueb/lathe/compare/v2.9.0...v2.9.1
[2.9.0]: https://github.com/ahueb/lathe/compare/v2.8.0...v2.9.0
[2.8.0]: https://github.com/ahueb/lathe/compare/v2.7.2...v2.8.0
[2.7.2]: https://github.com/ahueb/lathe/compare/v2.7.1...v2.7.2
[2.7.1]: https://github.com/ahueb/lathe/compare/v2.7.0...v2.7.1
[2.7.0]: https://github.com/ahueb/lathe/compare/v2.6.0...v2.7.0
[2.6.0]: https://github.com/ahueb/lathe/compare/v2.5.4...v2.6.0
[2.5.4]: https://github.com/ahueb/lathe/compare/v2.5.3...v2.5.4
[2.5.3]: https://github.com/ahueb/lathe/compare/v2.5.2...v2.5.3
[2.5.2]: https://github.com/ahueb/lathe/compare/v2.5.1...v2.5.2
[2.5.1]: https://github.com/ahueb/lathe/releases/tag/v2.5.1
