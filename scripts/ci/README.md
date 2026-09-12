# CI helper scripts

Supports `.github/workflows/ci.yml`. Three jobs, each installing Claude Code
at a pinned, signature-verified version and then running a deterministic
check:

- **linux** (ubuntu-latest): installs the pinned Claude Code build via
  `install-claude.sh`, installs shellcheck, and runs `./ci.sh` (the default
  local tier). Proves the default tier passes on Linux with a verified CLI
  binary. This is the required status check for `main`.
- **macos** (macos-latest): same install and verification, then prepends a
  shim directory (a `bash` symlink to `/bin/bash`) to `PATH` so every
  `#!/usr/bin/env bash` script in `./ci.sh` runs under the system's bash 3.2,
  asserts `bash --version` reports 3.2 in the job log, installs shellcheck
  and gnupg via Homebrew, and runs `./ci.sh`. Proves the scripts are bash
  3.2 compatible, which Linux runners (bash 5) cannot prove.
- **windows** (windows-latest): installs the pinned Claude Code build via
  `install-claude.ps1` (PowerShell, gpg from Git for Windows), runs
  `python -X dev -m unittest scripts.tests.test_merge_settings
  scripts.tests.test_safe_write`, and runs `bash -n` under Git Bash on
  `install.sh`, `release.sh`, `ci.sh`, and
  `plugins/engineering/hooks/session-start.sh`. Proves the Python helpers
  pass their unit tests under Python's dev-mode checks and that the shell
  scripts are at least syntactically valid on Windows; it does not run the
  scratch/`ci.sh` scenarios on Windows.

None of the jobs use secrets or configure credentials; `--full` (which
requires an authenticated CLI) never runs in Actions. Every job checks
out the repo with `actions/checkout` pinned to a commit SHA (not a
mutable tag) and `persist-credentials: false`, so the job never retains
a token that could push back to the repo.

## The version pin

`claude-version.txt` holds the exact Claude Code CLI version installed and
verified by `install-claude.sh` / `install-claude.ps1`. Both scripts:

1. import the vendored Anthropic release key
   (`anthropic-release-key.asc`) into a throwaway keyring, assert it is
   the only primary key imported, and check its fingerprint against the
   value hardcoded in the script (`$FPR` / `$Fpr`);
2. download that version's `manifest.json` and `manifest.json.sig` and
   verify the signature against the imported key, requiring a `VALIDSIG`
   status line bound to that same pinned fingerprint;
3. download the binary named in the verified manifest's platform entry
   directly from the release host (no convenience installer is executed)
   and verify its SHA256 checksum and byte size against the manifest
   before the binary is placed on disk or run; only then is it moved
   into `~/.local/bin` (or `%USERPROFILE%\.local\bin` on Windows) and
   its `--version` output checked against the pin.

Any mismatch (key count, fingerprint, signature binding, checksum, size,
or reported version) fails the job.

### Bumping the pinned version

1. Update `scripts/ci/claude-version.txt` to the new version string (no
   trailing whitespace beyond a single newline).
2. If Anthropic has rotated the release signing key, replace
   `scripts/ci/anthropic-release-key.asc` and update the fingerprint
   constant (`FPR` in `install-claude.sh`, `$Fpr` in `install-claude.ps1`)
   to match; record the new fingerprint and how it was verified in
   `SECURITY.md`.
3. Push a branch and let the three jobs verify the new pin before merging.

## Applying branch protection

Applied 2026-09-12. The `PATCH .../required_status_checks` endpoint returns 404 until
status checks are enabled, so the whole protection object is `PUT`, restating the
existing settings (GitHub Actions' app id is `15368`):

```
cat > /tmp/protection.json <<'EOF'
{"required_status_checks": {"strict": true, "checks": [{"context": "linux", "app_id": 15368}]},
 "enforce_admins": true, "required_pull_request_reviews": null, "restrictions": null,
 "required_linear_history": true, "allow_force_pushes": false, "allow_deletions": false}
EOF
gh api -X PUT repos/ahueb/engineering/branches/main/protection --input /tmp/protection.json
```

`macos` becomes a required check only after two consecutive green releases
on it.
