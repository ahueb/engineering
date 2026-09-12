# Risk register

Owner for every item: alan@hueb.org unless stated. Reassess at each minor release or when the trigger fires.

| ID | Risk | Status | Mitigation / compensating control | Trigger to reassess |
|---|---|---|---|---|
| R1 | Distribution channel: consumers who track `main` get whatever is pushed; a compromised maintainer account ships a hook into every session | Mitigated | Branch protection (linear history, no force push or deletion, admins enforced); signed tags per release; `.allowed_signers` committed; pin-by-version documented | Signing key registered on GitHub and required signatures enabled on `main` (2026-09-12); reassess if the signing key rotates |
| R2 | No server-side CI: a push that skips the pre-push hook (`--no-verify`, or a clone without `core.hooksPath`) is unverified | Accepted | `release.sh` runs `ci.sh` before tagging; SECURITY.md states the tag signature is the integrity evidence | Second maintainer joins; or a CI runner is acceptable |
| R3 | Model-facing behaviour (skill triggering, agent conduct) is checked only by the 20 trigger evals, which grade tool invocation, not output quality, at one run per case | Mitigated | 20/20 recorded in `plugins/engineering/evals/RESULTS.md` (2026-09-12, scaffolded); all skills are user-invocable by slash command regardless of trigger quality | Claude Code changes the skill listing budget or description handling; a new model becomes default |
| R4 | Single maintainer: recovery, release, and marketplace knowledge held by one person | Accepted | README and `release.sh` document the full release path; repo is public and forkable; MIT licence | A second contributor with push access |
| R5 | Hook portability: verified on Linux bash 5.2 only; macOS bash 3.2 and Windows Git Bash unverified | Accepted | `install.sh` makes the hook unnecessary (policy becomes a file); hook failure is non-fatal to the session | First macOS or Windows user report |
| R6 | Claude Code version drift: `fable` alias, `[1m]`, `effort` frontmatter, skill listing budget changed across 2.1.173–2.1.267 | Accepted | README pins minimum 2.1.267 and names the behaviours that depend on it | Any Claude Code changelog entry touching aliases, effort, plugins, or hooks |
| R7 | Consumer rollback relies on `claude plugin install engineering@engineering@<version>`; tested only for the version currently on `main` | Open | Documented in README; every release is tagged so the version is a git ref | Verify after the first release that an older pinned version resolves from a tag |
| R8 | `--no-official` deletes previously enabled official-plugin entries from the user's settings | Accepted | Documented in README and the script header; a backup is written before the change | User report of surprise |
| R9 | EU Cyber Resilience Act applicability assumed out of scope (non-commercial open source) | Open | None needed while non-commercial | Any monetisation or bundling into a commercial product |
