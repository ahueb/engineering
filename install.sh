#!/usr/bin/env bash
# Install the engineering configuration into a Claude Code config directory.
#
#   ./install.sh                 install into ~/.claude (or $CLAUDE_CONFIG_DIR)
#   ./install.sh --no-official   do not enable or install plugins from claude-plugins-official
#                                (also removes previously enabled official entries from settings.json)
#   ./install.sh --source URL    register the marketplace from a git URL / owner/repo instead of this checkout
#
# engineering@engineering is always installed and enabled; explicit opt-outs are honored only
# for claude-plugins-official plugins.
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
STAMP="$(date +%Y%m%d-%H%M%S)-$$"

# Merge $1 (current settings.json, may not exist) with $2 (recommended settings) per the
# --no-official / enabledPlugins rules, validating both inputs before anything is written.
# Writes the merged document to stdout; callers decide whether/where to write it.
merge_settings() {
  python3 - "$1" "$2" "$3" <<'PY'
import json, sys, os
dst, src, official = sys.argv[1], sys.argv[2], sys.argv[3] == "1"
if os.path.exists(dst):
    try:
        with open(dst) as f:
            cur = json.load(f)
    except OSError as exc:
        print(f"settings.json could not be read: {exc}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError:
        print("settings.json is not a JSON object; fix or remove it and rerun", file=sys.stderr)
        sys.exit(1)
    if not isinstance(cur, dict):
        print("settings.json is not a JSON object; fix or remove it and rerun", file=sys.stderr)
        sys.exit(1)
else:
    cur = {}
rec = json.load(open(src))
if not official:
    # Drop official entries from the recommendation AND from the current file: Claude Code
    # auto-installs every enabled official plugin at the next session start, so leaving a
    # previously enabled entry in place would defeat --no-official. Explicit false stays.
    rec["enabledPlugins"] = {k: v for k, v in rec["enabledPlugins"].items() if not k.endswith("@claude-plugins-official")}
    rec["extraKnownMarketplaces"].pop("claude-plugins-official", None)
    ep = cur.get("enabledPlugins")
    if isinstance(ep, dict):
        for k in [k for k, v in ep.items() if k.endswith("@claude-plugins-official") and v is not False]:
            del ep[k]
    km = cur.get("extraKnownMarketplaces")
    if isinstance(km, dict):
        km.pop("claude-plugins-official", None)
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
json.dump(cur, sys.stdout, indent=2)
sys.stdout.write("\n")
PY
}

# Parse and validate before writing anything: a broken settings.json must fail here, before
# anything is registered or written. The real merge runs later, after marketplace registration
# has added its own entries to settings.json.
merge_settings "$CFG/settings.json" "$HERE/settings.recommended.json" "$OFFICIAL" >/dev/null || exit 1

# 1. Marketplace registration (before any file writes, so a failure here leaves nothing changed).
#    If `add` fails because 'engineering' is already registered, the existing binding must point
#    at $SOURCE; otherwise refuse, so a stale or foreign binding is never silently installed from.
registered_source() {
  # Prints the location recorded for marketplace 'engineering' (the part inside the parentheses
  # of the CLI's "Source: Kind (location)" line, or the whole value if there are none).
  # Never fails: an empty result means "not registered or unparseable".
  local out
  out="$(claude plugin marketplace list 2>/dev/null || true)"
  printf '%s\n' "$out" | python3 -c '
import re, sys
name = None
found = ""
for line in sys.stdin:
    if not line.strip():
        name = None; continue
    m = re.match(r"^\s{0,4}(?:[^\w\s]\s+)?([A-Za-z0-9_.-]+)\s*$", line)
    if m:
        name = m.group(1); continue
    m = re.match(r"^\s*Source:\s*(.*\S)\s*$", line)
    if m and name == "engineering" and not found:
        v = m.group(1)
        inner = re.search(r"\(([^()]*)\)\s*$", v)
        found = inner.group(1) if inner else v
print(found)
' || true
}
MARKETPLACE_ERR="$(claude plugin marketplace add "$SOURCE" 2>&1 >/dev/null)" && MARKETPLACE_STATUS=0 || MARKETPLACE_STATUS=$?
if [ "$MARKETPLACE_STATUS" -ne 0 ]; then
  REG="$(registered_source || true)"
  if [ -z "$REG" ]; then
    printf '%s\n' "$MARKETPLACE_ERR" >&2
    exit 1
  fi
  WANT_LOGICAL="$SOURCE"; WANT_PHYSICAL="$SOURCE"
  if [ -d "$SOURCE" ]; then
    WANT_LOGICAL="$(cd "$SOURCE" && pwd)"
    WANT_PHYSICAL="$(cd "$SOURCE" && pwd -P)"
  fi
  REG_TRIMMED="${REG%/}"
  if [ "$REG_TRIMMED" = "${WANT_LOGICAL%/}" ] || [ "$REG_TRIMMED" = "${WANT_PHYSICAL%/}" ]; then
    claude plugin marketplace update engineering >/dev/null
  else
    echo "marketplace 'engineering' is registered from '$REG', not '$SOURCE'; run 'claude plugin marketplace remove engineering' first to rebind it" >&2
    exit 1
  fi
fi

# 2. Compute the settings merge now (registration may have added marketplace entries), so a
#    merge failure aborts before CLAUDE.md is touched.
MERGED_SETTINGS="$(merge_settings "$CFG/settings.json" "$HERE/settings.recommended.json" "$OFFICIAL")" || exit 1

# 3. CLAUDE.md (back up any existing one; never merge policy text)
if [ -f "$CFG/CLAUDE.md" ] && ! cmp -s "$CFG/CLAUDE.md" "$HERE/plugins/engineering/context/CLAUDE.md"; then
  cp "$CFG/CLAUDE.md" "$CFG/CLAUDE.md.bak-$STAMP"
  echo "backed up existing CLAUDE.md -> CLAUDE.md.bak-$STAMP"
fi
cp "$HERE/plugins/engineering/context/CLAUDE.md" "$CFG/CLAUDE.md"
echo "installed CLAUDE.md"

# 4. settings.json: key-level merge; recommended values win for the keys they define,
#    nested objects (modelSettings, env, enabledPlugins, extraKnownMarketplaces) are merged, not replaced.
#    enabledPlugins is special: a plugin the user already set to false stays false, and with
#    --no-official the claude-plugins-official entries are dropped entirely, because Claude Code
#    auto-installs any enabled official plugin at the next session start.
#    Only back up and rewrite the file if the merged content actually differs.
if [ ! -f "$CFG/settings.json" ] || ! printf '%s\n' "$MERGED_SETTINGS" | cmp -s - "$CFG/settings.json"; then
  if [ -f "$CFG/settings.json" ]; then
    cp "$CFG/settings.json" "$CFG/settings.json.bak-$STAMP"
    echo "backed up existing settings.json -> settings.json.bak-$STAMP"
  fi
  TMP_SETTINGS="$(mktemp "$CFG/settings.json.tmp-XXXXXX")"
  trap 'rm -f "$TMP_SETTINGS"' EXIT
  printf '%s\n' "$MERGED_SETTINGS" > "$TMP_SETTINGS"
  chmod 0644 "$TMP_SETTINGS"
  mv -f "$TMP_SETTINGS" "$CFG/settings.json"
  trap - EXIT
fi
echo "merged settings.json"

# 5. Plugin install
claude plugin install engineering@engineering --scope user
echo "installed engineering@engineering"

# 6. Official plugins the policy expects
if [ "$OFFICIAL" = 1 ]; then
  claude plugin marketplace add anthropics/claude-plugins-official >/dev/null 2>&1 || true
  # `claude plugin install` flips enabledPlugins to true, so skip anything the user set to false.
  for p in superpowers context7 code-review playwright frontend-design claude-code-setup claude-md-management typescript-lsp pyright-lsp rust-analyzer-lsp gopls-lsp; do
    if python3 - "$CFG/settings.json" "$p@claude-plugins-official" <<'PY'
import json, sys
path, key = sys.argv[1], sys.argv[2]
sys.exit(0 if json.load(open(path)).get('enabledPlugins', {}).get(key) is False else 1)
PY
    then
      echo "skipped $p (disabled in your settings)"; continue
    fi
    claude plugin install "$p@claude-plugins-official" --scope user >/dev/null && echo "installed $p" || echo "WARN: could not install $p" >&2
  done
fi

echo
echo "Done. Config dir: $CFG"
echo "Verify with:  claude plugin list   and   claude --print '/help' (look for /engineering:* skills)"
