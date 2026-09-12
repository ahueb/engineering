# Security

This plugin runs code on your machine: a SessionStart hook (`plugins/engineering/hooks/session-start.sh`) at every Claude Code session start, `install.sh` when you install, and `repo_probe.py` when the readiness review runs. Treat it like any other software you execute.

## Reporting a vulnerability

Email alan@hueb.org with the subject `engineering plugin security`. Include the version (`claude plugin list`), the file or behaviour affected, and reproduction steps. Do not open a public issue for an unpatched vulnerability.

Expected response: acknowledgement within 7 days; a fix or mitigation for a confirmed issue in the next release, normally within 30 days. This is a single-maintainer project with no paid support; those are intentions, not a service-level commitment.

## Verifying what you install

- Every release is a signed tag `vX.Y.Z` on `main`. Verify with the committed allowed-signers file:

  ```bash
  git config gpg.ssh.allowedSignersFile .allowed_signers
  git tag -v v2.5.1
  ```

- `main` is branch-protected on GitHub: linear history, no force pushes, no deletions, enforced for admins.
- Every push is gated locally by `./ci.sh` through a pre-push hook; there is no server-side CI, so the tag signature is the integrity evidence.
- Pin a version instead of tracking `main` by checking out the signed tag and registering the clone as a directory marketplace (steps in README, "Verify, pin, and roll back"). The `engineering@engineering@<version>` install form resolves to `main` for a GitHub-sourced marketplace and does not pin.

## What the code does and does not do

- Never sends data anywhere. The hook prints a local file; the probe writes JSON to stdout only.
- The probe never prints file contents, never follows symlinks, skips secret-looking file names, and runs `git` with `core.fsmonitor` and `core.hooksPath` disabled so a hostile repository cannot execute commands through it.
- `install.sh` rewrites `~/.claude/CLAUDE.md` and merges `~/.claude/settings.json` after backing them up; it refuses to run if the marketplace cannot be registered or if `settings.json` is unreadable or malformed.

## Supported versions

Only the latest released version receives fixes.
