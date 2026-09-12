# Changelog

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
