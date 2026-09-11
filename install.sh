#!/usr/bin/env bash
# Install the engineering configuration into a Claude Code config directory.
#
#   ./install.sh                 install into ~/.claude (or $CLAUDE_CONFIG_DIR)
#   ./install.sh --no-official   do not enable or install plugins from claude-plugins-official
#   ./install.sh --source URL    register the marketplace from a git URL / owner/repo instead of this checkout
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SOURCE="$HERE"
OFFICIAL=1
while [ $# -gt 0 ]; do
  case "$1" in
    --no-official) OFFICIAL=0 ;;
    --source) [ $# -ge 2 ] || { echo "--source requires a value (owner/repo, git URL, or path)" >&2; exit 2; }; SOURCE="$2"; shift ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
  shift
done

command -v claude >/dev/null || { echo "claude CLI not found on PATH" >&2; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required for the settings merge" >&2; exit 1; }
mkdir -p "$CFG"
STAMP="$(date +%Y%m%d-%H%M%S)"

# 1. CLAUDE.md (back up any existing one; never merge policy text)
if [ -f "$CFG/CLAUDE.md" ] && ! cmp -s "$CFG/CLAUDE.md" "$HERE/plugins/engineering/context/CLAUDE.md"; then
  cp "$CFG/CLAUDE.md" "$CFG/CLAUDE.md.bak-$STAMP"
  echo "backed up existing CLAUDE.md -> CLAUDE.md.bak-$STAMP"
fi
cp "$HERE/plugins/engineering/context/CLAUDE.md" "$CFG/CLAUDE.md"
echo "installed CLAUDE.md"

# 2. settings.json: key-level merge; recommended values win for the keys they define,
#    nested objects (modelSettings, env, enabledPlugins, extraKnownMarketplaces) are merged, not replaced.
#    enabledPlugins is special: a plugin the user already set to false stays false, and with
#    --no-official the claude-plugins-official entries are dropped entirely, because Claude Code
#    auto-installs any enabled official plugin at the next session start.
[ -f "$CFG/settings.json" ] && cp "$CFG/settings.json" "$CFG/settings.json.bak-$STAMP"
python3 - "$CFG/settings.json" "$HERE/settings.recommended.json" "$OFFICIAL" <<'PY'
import json, sys, os
dst, src, official = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
cur = json.load(open(dst)) if os.path.exists(dst) else {}
rec = json.load(open(src))
if not official:
    rec["enabledPlugins"] = {k: v for k, v in rec["enabledPlugins"].items() if not k.endswith("@claude-plugins-official")}
    rec["extraKnownMarketplaces"].pop("claude-plugins-official", None)
def merge(a, b, path=()):
    for k, v in b.items():
        if isinstance(v, dict) and isinstance(a.get(k), dict):
            merge(a[k], v, path + (k,))
        elif path == ("enabledPlugins",) and a.get(k) is False:
            continue  # respect an explicit user opt-out
        else:
            a[k] = v
    return a
merge(cur, rec)
with open(dst, "w") as f:
    json.dump(cur, f, indent=2); f.write("\n")
print("merged settings.json")
PY

# 3. Marketplace + plugin
claude plugin marketplace add "$SOURCE" >/dev/null 2>&1 || claude plugin marketplace update engineering >/dev/null
claude plugin install engineering@engineering --scope user
echo "installed engineering@engineering"

# 4. Official plugins the policy expects
if [ "$OFFICIAL" = 1 ]; then
  claude plugin marketplace add anthropics/claude-plugins-official >/dev/null 2>&1 || true
  for p in superpowers context7 code-review playwright frontend-design claude-code-setup claude-md-management typescript-lsp pyright-lsp rust-analyzer-lsp gopls-lsp; do
    claude plugin install "$p@claude-plugins-official" --scope user >/dev/null && echo "installed $p" || echo "WARN: could not install $p" >&2
  done
fi

echo
echo "Done. Config dir: $CFG"
echo "Verify with:  claude plugin list   and   claude --print '/help' (look for /engineering:* skills)"
