# Security

This plugin runs code on your machine: a SessionStart hook (`plugins/engineering/hooks/session-start.sh`) at every Claude Code session start, `install.sh` when you install, and `repo_probe.py` when the readiness review runs. Treat it like any other software you execute.

## Reporting a vulnerability

Email alan@hueb.org with the subject `engineering plugin security`. Include the version (`claude plugin list`), the file or behaviour affected, and reproduction steps. Do not open a public issue for an unpatched vulnerability.

Expected response: acknowledgement within 7 days; a fix or mitigation for a confirmed issue in the next release, normally within 30 days. This is a single-maintainer project with no paid support; those are intentions, not a service-level commitment.

## Verifying what you install

- Every release is a signed tag `vX.Y.Z` on `main`. Verify with the committed allowed-signers file:

  ```bash
  git config gpg.ssh.allowedSignersFile .allowed_signers
  git tag -v v2.7.1
  ```

- `main` is branch-protected on GitHub: linear history, no force pushes, no deletions, enforced for admins.
- Every push is gated locally by `./ci.sh` through a pre-push hook; there is no server-side CI, so the tag signature is the integrity evidence.
- Pin a version instead of tracking `main` by registering the marketplace at a signed tag (`claude plugin marketplace add ahueb/engineering@vX.Y.Z`), or by checking out the tag and registering the clone as a directory marketplace when you want to verify the signature locally (steps in README, "Verify, pin, and roll back"). The `engineering@engineering@<version>` install form does not pin.

## What the code does and does not do

- Never sends data anywhere. The hook prints a local file; the probe writes JSON to stdout only.
- The probe never prints file contents, never follows symlinks, skips secret-looking file names, and runs `git` with `core.fsmonitor` and `core.hooksPath` disabled so a hostile repository cannot execute commands through it.
- `install.sh` reads `settings.json`, `CLAUDE.md`, and `rules/engineering-policy.md` under your config directory, plus the output of `claude plugin marketplace list --json` and `claude plugin list --json`, to decide what to merge or migrate. It writes `settings.json` (merged with `settings.recommended.json`), the policy as `rules/engineering-policy.md` (or `CLAUDE.md` with `--policy-target claude-md`), and the installer marker `engineering-installer.json`. Before any file it is about to change, it copies that file into `~/.claude/backups/engineering/<stamp>/` (directory mode 0700; the newest 5 stamps are kept). `settings.json` can hold API keys, MCP server credentials, or other secrets you have configured, so treat the backup directory with the same care as `settings.json` itself. The drift report and `--dry-run` diff redact `env` values, any key containing `key`, `token`, `secret`, `password`, or `credential`, and `apiKeyHelper` as `<redacted>` before printing. It refuses to run if the marketplace cannot be registered, if `settings.json` is unreadable or malformed, if a target is a hard-linked file (unless `--break-hardlinks`), or if `settings.json` is a dangling symlink (unless `--create-through-dangling`).
- File permissions: the installer preserves the existing mode of a `settings.json` it did not create; it only sets 0600 on a `settings.json` it creates from nothing during the run. If you created `settings.json` yourself earlier (for example with the Claude Code CLI under a permissive umask), it keeps whatever mode it already had — the installer does not tighten a pre-existing file's permissions. Run `chmod 600 ~/.claude/settings.json` yourself if the file holds secrets and its mode is wider than you want.
- `./install.sh --restore [STAMP]` first takes its own pre-restore backup (under a new stamp) of every file it is about to overwrite, then restores regular files unconditionally from the chosen backup. It validates the backup manifest, including that stored filenames are flat (no path traversal). A backed-up symlink whose target is now missing is recreated only when the recorded target path already exists on disk with content identical to the backup; restore never creates a file outside your config directory, and refuses that entry otherwise. Restored file modes are masked to permission bits only.

## Supported versions

Only the latest released version receives fixes.
