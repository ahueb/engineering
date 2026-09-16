#!/usr/bin/env bash
# Inject the plugin-bundled operating policy as a fallback, used only when neither
# recognized installed copy exists: not the rules file $CFG/rules/engineering-policy.md
# (install.sh >= 2.8.0) and not the legacy $CFG/CLAUDE.md copy (older install.sh, or
# --policy-target claude-md). This hook covers marketplace-only installs and sessions
# started before a migration completes.
# When an installed copy does exist but is stale, this hook prints a one-line refresh
# notice instead of injecting anything.
# The check is first-line only: a policy copied under a different heading is
# injected again, and a user file that merely contains the heading elsewhere is
# not treated as the policy. An installed copy that is out of date yields a
# one-line refresh notice, never a duplicate policy.
# A UTF-8 BOM and a CRLF line ending on that first line are tolerated.
CFG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"

# Only a regular file is read: a directory, FIFO, or device at either location
# would otherwise block or hang session start.
first_line() {
  [ -f "$1" ] || return 1
  head -n 1 "$1" 2>/dev/null | tr -d '\r'
}

check() {
  f="$(first_line "$1")"
  f="${f#$'\xef\xbb\xbf'}"
  [ "$f" = "# Agent operating policy" ]
}

BUNDLED="$(dirname "$0")/../context/CLAUDE.md"

# An installed copy suppresses injection. When it differs from the policy bundled
# with this plugin version, print a one-line notice instead of a second copy, so
# the policy never loads twice and the user learns to rerun install.sh.
installed() {
  if cmp -s "$1" "$BUNDLED"; then
    exit 0
  fi
  echo "engineering: installed policy $1 differs from the plugin's bundled policy; rerun install.sh to refresh it."
  exit 0
}

if check "$CFG/rules/engineering-policy.md"; then
  installed "$CFG/rules/engineering-policy.md"
fi
if check "$CFG/CLAUDE.md"; then
  installed "$CFG/CLAUDE.md"
fi
cat "$BUNDLED"
