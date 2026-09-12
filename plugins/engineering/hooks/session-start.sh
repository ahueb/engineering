#!/usr/bin/env bash
# Inject the operating policy only when the user has not installed it as ~/.claude/CLAUDE.md.
# install.sh copies it there; this hook is the fallback for marketplace-only installs.
# The check is first-line only: a policy copied under a different heading is injected
# again, and a user file that merely contains the heading elsewhere is not treated as the policy.
# A UTF-8 BOM and a CRLF line ending on that first line are tolerated.
CFG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
first="$(head -n 1 "$CFG/CLAUDE.md" 2>/dev/null | tr -d '\r')"
first="${first#$'\xef\xbb\xbf'}"
if [ "$first" = "# Agent operating policy" ]; then
  exit 0
fi
cat "$(dirname "$0")/../context/CLAUDE.md"
