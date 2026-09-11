#!/usr/bin/env bash
# Inject the operating policy only when the user has not installed it as ~/.claude/CLAUDE.md.
# install.sh copies it there; this hook is the fallback for marketplace-only installs.
CFG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
if [ -f "$CFG/CLAUDE.md" ] && grep -q '^# Agent operating policy' "$CFG/CLAUDE.md"; then
  exit 0
fi
cat "$(dirname "$0")/../CLAUDE.md"
