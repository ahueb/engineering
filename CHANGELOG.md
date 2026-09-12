# Changelog

## 2.5.1 — 2026-09-11

- Local CI gate `ci.sh` (lint, both manifests under `--strict`, probe tests, frontmatter and cross-reference checks, hook contract, scratch install) wired into `.githooks/pre-push` and `release.sh`. No GitHub Actions or server-side hooks.
- Releases are signed tags `vX.Y.Z`; `.allowed_signers` committed for `git tag -v`. `main` is branch-protected (linear history, no force push or deletion, required signatures, enforced for admins).
- `SECURITY.md`: reporting path, response expectations, verification and pinning instructions.
- `docs/risk-register.md`: residual risks with owners and reassessment triggers.
- README: verify, pin, and roll back a release; CI section; ownership.
- Trigger evals: every positive case now scaffolds a fixture repository (`evals/fixture-service.sh`, `case.yaml` per case); readiness skill description covers operational/launch readiness, canary or GA assessment, on-call handover, and adversarial "disprove it is ready" requests. Results (20/20) recorded in `plugins/engineering/evals/RESULTS.md`.

## 2.5.0 — 2026-09-11

- `install.sh`: parses and validates `settings.json` before touching `CLAUDE.md`; registers the marketplace before any file write and surfaces the real error; writes a `settings.json.bak-` only when the merged content actually changes; quote-safe opt-out check for config paths containing `'`; documents that `engineering@engineering` is always enabled.
- `release.sh`: parses `--no-commit` in any position; validates the current version is `x.y.z` before bumping; gates the version bump on `claude plugin validate --strict`, restoring the prior version on failure; refuses to run on a working tree with unrelated changes; commits only `plugin.json` and `CHANGELOG.md`.
- SessionStart hook: also fires on `resume`; the policy is considered present only when the first line of `CLAUDE.md` is exactly `# Agent operating policy`, so a copy under a different heading is not mistaken for it.
- Policy (`context/CLAUDE.md`): corrects the superpowers mapping (`plan-execution` replaces both `executing-plans` and `subagent-driven-development` and overrides any build/test step in a superpowers prompt file; `dispatching-parallel-agents` work that edits code goes to `bulk-implementer` or `hard-repair`, not `scout`), restates the read-only/no-edit-tools wording precisely, and makes the plan-execution no-test rule explicitly override prompt-file text. `test-triage` moves to `sonnet` at `low` effort.
- `security-reviewer` and `semantic-reviewer` accept a whole-candidate scope (not just a diff) and, having no shell, name the command a claim would need rather than asking to run one.
- `production-readiness-review`: literature refresh — SLSA v1.2 (source track), EU Cyber Resilience Act reporting-obligation overlay, EU AI Act Article 50 transparency duties, CISA 2026 SBOM minimum elements, restore-test recency, named rollback-trigger metrics, SLO ownership and error-budget consequence, CI hardening (token permissions, branch protection, signed releases), and a change-authorization/audit-record requirement where SOC 2 CC8.1 or ISO 27001 A.8.32 applies. E4 now requires independent reproduction under bounded real-production or realistic adverse conditions, cumulative on E3.
- `repo_probe.py`: bounded by `--max-seconds` and `--max-text-bytes`; excludes `.git` gitlinks so submodules are not miscounted; new content-signal keys for CI permissions, signed releases, vulnerability-reporting paths, and dependency automation. Probe tests extended accordingly.

## 2.4.1 — 2026-09-11

- Shorter `production-readiness-review` description.
- `settings.recommended.json` sets `skillListingBudgetFraction` to 0.02: at the 1% default, 200K-context models drop the descriptions of the last skills in the listing, which disables automatic invocation for them.

## 2.4.0 — 2026-09-11

- `production-readiness-review` skill: read-only, gate-first production readiness audit with hard gates, graded dimensions, domain overlays, adversarial falsification, and a bundled repository probe with tests. Evidence collection fans out to `scout`, `security-reviewer`, and `semantic-reviewer`.
- `evals/`: twenty `claude plugin eval` trigger cases for the readiness skill.
- Policy: the readiness review is standalone and never chained into implementation, verification, or plan execution.

## 2.3.0 — 2026-09-11

- `plan-execution` skill: partitions a plan into disjoint-file packages, fans all of them out to parallel `bulk-implementer` agents with no per-package build or test, verifies once after merge, then audits adversarially.
- `plan-auditor` agent: read-only, `opus` at high effort, proves completeness and correctness of a merged implementation against its plan.
- `bulk-implementer` builds and tests only when the parent asks.
- Policy routes superpowers `executing-plans` and `subagent-driven-development` through `plan-execution`.

## 2.2.0 — 2026-09-11

- Policy maps superpowers subagent roles onto engineering agents: implementer → `bulk-implementer`, reviewers → `semantic-reviewer` and `security-reviewer`, late fix rounds → `hard-repair`, lookups → `scout`.
- `implementation-loop` invokes `superpowers:test-driven-development` and `superpowers:systematic-debugging` when present, and closes with `verification-loop` and `checkpoint`.
- `verification-loop` invokes `superpowers:verification-before-completion` when present.
- `checkpoint` records the superpowers plan file and completed task numbers when work follows a plan.

## 2.1.0 — 2026-09-11

- Agents and skills select models by alias (`haiku`, `sonnet`, `opus`, `fable`) so they resolve on every provider.
- `security-reviewer` runs on `opus` at medium effort; `semantic-reviewer` runs at medium effort.
- SessionStart hook also fires for forked sessions.
- `install.sh --no-official` omits the official plugins from settings; explicit user opt-outs are preserved; `--source` requires a value.
- `release.sh` added for version bumps and local plugin refresh.
- README documents update flow, model and plan requirements, and the exact read-only guarantees.

## 2.0.0 — 2026-09-11

- First release of the `engineering` plugin and marketplace: operating policy, eight agents, five process skills, four user-invoked escalation skills, SessionStart policy hook, recommended settings, and `install.sh`.
