#!/usr/bin/env bash
# Install the engineering configuration into a Claude Code config directory.
#
# Usage:
#   ./install.sh [flags]
#
# Flags:
#   --no-official              Do not register the official marketplace or install/keep
#                               official-marketplace plugins. Leaves any previously enabled
#                               official plugin entries and the official marketplace alone.
#   --purge-official            Remove official-marketplace plugin entries and the official
#                               marketplace binding from settings.json (backed up first).
#                               Destructive: an explicit `false` entry is kept, everything
#                               else naming @claude-plugins-official is deleted. Implies no
#                               official plugins are (re)installed this run.
#   --source X                 Register the 'engineering' marketplace from X (a directory,
#                               owner/repo, or git URL) instead of this checkout.
#   --settings-mode enforce|defaults
#                               Force the settings-merge mode instead of auto-selecting it
#                               (see the settings-modes note at the end of this help).
#                               Always wins over auto-selection.
#   --policy-target rules|claude-md
#                               Where the policy lives: rules/engineering-policy.md (default)
#                               or the legacy ~/.claude/CLAUDE.md. `claude-md` behaves as the
#                               installer always has: backup, replace, first-line guard.
#   --dry-run                   Preview every action (settings diff, drift report, policy
#                               action, marketplace action, predicted marketplace entry,
#                               chosen mode) without writing, registering, or installing
#                               anything. Exits 0.
#   --yes                       Assume "yes" to the legacy-policy migration prompt; also
#                               skips the interactive /dev/tty prompt entirely.
#   --break-hardlinks           Allow writing through a hard-linked settings.json or policy
#                               file (os.replace would otherwise detach the link silently).
#   --create-through-dangling   Allow writing through a dangling settings.json symlink,
#                               creating the link's target. Without it a dangling
#                               settings.json symlink stops the run with exit 4, because the
#                               intended target (usually a dotfiles checkout) is missing.
#   --restore [STAMP]           Restore the most recent backup, or STAMP if given, then exit.
#                               Delegates to scripts/safe_write.py restore. Accepts
#                               --break-hardlinks.
#   --list-backups               List backup stamps and their files, then exit.
#   -h, --help                  Show this help and exit.
#
# Environment:
#   ENGINEERING_NO_PROMPT=1     Deterministically decline the legacy-policy migration prompt
#                               (no /dev/tty is opened). The legacy CLAUDE.md is still
#                               refreshed in place.
#   ENGINEERING_RECOMMENDED=PATH
#                               Test-only override of the recommendation file used for the
#                               settings merge (default: settings.recommended.json beside this
#                               script).
#
# engineering@engineering is always installed and enabled: running this installer is an
# explicit choice, so an existing `enabledPlugins["engineering@engineering"] = false` is
# overwritten to true (by `claude plugin install` and reasserted by the settings merge).
# Explicit opt-outs are honored only for @claude-plugins-official plugins.
#
# Exit codes:
#   0  success (including a no-op run, --dry-run, --list-backups, and a clean --restore)
#   1  general failure: marketplace registration/refusal, plugin install failure, a
#      user-owned policy file that would be refused, or an unparseable marketplace listing
#   2  usage error (bad or missing flag value)
#   3  settings.json (or the post-install settings.json) could not be merged
#   4  a write target is a directory, FIFO, or socket (from scripts/safe_write.py), or
#      settings.json is a dangling symlink and --create-through-dangling was not given
#   5  a write target is hard-linked and --break-hardlinks was not given
#   6  a write failed and its temp file was removed (from scripts/safe_write.py)
#   7  Windows: the target file is open elsewhere; close Claude Code and rerun
#   8  --restore: one or more files were refused (see scripts/safe_write.py restore)
#   9  --restore: no backups found or the manifest is invalid
#
# Settings modes: "enforce" makes every recommended value win; "defaults" only fills in
# absent paths and reports drift. The mode is auto-selected once in preflight from
# $CFG/engineering-installer.json (present -> defaults), otherwise from evidence of a prior
# install (enabledPlugins["engineering@engineering"] present, or a legacy CLAUDE.md policy
# copy -> defaults with a first-run notice), otherwise enforce. --settings-mode always wins.
set -Eeuo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CFG="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
POLICY_SRC="$HERE/plugins/engineering/context/CLAUDE.md"

# ---- flag/env parsing (step 1) --------------------------------------------------------

OFFICIAL=1
PURGE_OFFICIAL=0
SOURCE_FLAG=""
SETTINGS_MODE_FLAG=""
POLICY_TARGET="rules"
DRY_RUN=0
YES=0
BREAK_HARDLINKS=0
CREATE_THROUGH_DANGLING=0
RESTORE_MODE=0
RESTORE_STAMP=""
LIST_BACKUPS=0

print_help() {
  sed -n '/^# Usage:/,/^set -Eeuo pipefail$/p' "$HERE/install.sh" | sed '$d' | sed 's/^# \{0,1\}//'
}

while [ $# -gt 0 ]; do
  case "$1" in
    --no-official) OFFICIAL=0 ;;
    --purge-official) PURGE_OFFICIAL=1 ;;
    --source)
      [ $# -ge 2 ] || { echo "--source requires a value (owner/repo, git URL, or path)" >&2; exit 2; }
      SOURCE_FLAG="$2"; shift ;;
    --settings-mode)
      [ $# -ge 2 ] || { echo "--settings-mode requires enforce or defaults" >&2; exit 2; }
      case "$2" in
        enforce|defaults) SETTINGS_MODE_FLAG="$2" ;;
        *) echo "--settings-mode must be enforce or defaults" >&2; exit 2 ;;
      esac
      shift ;;
    --policy-target)
      [ $# -ge 2 ] || { echo "--policy-target requires rules or claude-md" >&2; exit 2; }
      case "$2" in
        rules|claude-md) POLICY_TARGET="$2" ;;
        *) echo "--policy-target must be rules or claude-md" >&2; exit 2 ;;
      esac
      shift ;;
    --dry-run) DRY_RUN=1 ;;
    --yes) YES=1 ;;
    --break-hardlinks) BREAK_HARDLINKS=1 ;;
    --create-through-dangling) CREATE_THROUGH_DANGLING=1 ;;
    --restore)
      RESTORE_MODE=1
      if [ $# -ge 2 ]; then
        case "$2" in
          --*) : ;;
          *) RESTORE_STAMP="$2"; shift ;;
        esac
      fi
      ;;
    --list-backups) LIST_BACKUPS=1 ;;
    -h|--help) print_help; exit 0 ;;
    *) echo "unknown flag: $1" >&2; exit 2 ;;
  esac
  shift
done

if [ "$DRY_RUN" -eq 1 ] && [ "$RESTORE_MODE" -eq 1 ]; then
  echo "--dry-run cannot be combined with --restore" >&2
  exit 2
fi

SOURCE="${SOURCE_FLAG:-$HERE}"
# Recorded before any CLI call: a settings.json the CLI creates during this run is still "new"
# for mode purposes and is tightened to 0600 after the merge is written.
if [ -e "$CFG/settings.json" ] || [ -L "$CFG/settings.json" ]; then SETTINGS_PREEXISTED=1; else SETTINGS_PREEXISTED=0; fi
if [ -d "$CFG" ]; then CFG_PREEXISTED=1; else CFG_PREEXISTED=0; fi

# --restore / --list-backups delegate to safe_write.py and exit immediately.
if [ "$LIST_BACKUPS" -eq 1 ]; then
  python3 "$HERE/scripts/safe_write.py" list --cfg "$CFG"
  exit 0
fi
if [ "$RESTORE_MODE" -eq 1 ]; then
  set -- restore --cfg "$CFG"
  [ -n "$RESTORE_STAMP" ] && set -- "$@" --stamp "$RESTORE_STAMP"
  [ "$BREAK_HARDLINKS" -eq 1 ] && set -- "$@" --break-hardlinks
  python3 "$HERE/scripts/safe_write.py" "$@"
  exit $?
fi

OFFICIAL_FLAGS=""
[ "$OFFICIAL" -eq 0 ] && OFFICIAL_FLAGS="$OFFICIAL_FLAGS --no-official"
[ "$PURGE_OFFICIAL" -eq 1 ] && OFFICIAL_FLAGS="$OFFICIAL_FLAGS --purge-official"

# ---- helpers ----------------------------------------------------------------------------

# Bash-3.2-safe dotted-triplet numeric version compare: version_ge HAVE WANT
version_ge() {
  local have="$1" want="$2"
  local h1 h2 h3 w1 w2 w3
  local IFS=.
  set -- $have
  h1="${1:-0}"; h2="${2:-0}"; h3="${3:-0}"
  set -- $want
  w1="${1:-0}"; w2="${2:-0}"; w3="${3:-0}"
  if [ "$h1" -gt "$w1" ]; then return 0; fi
  if [ "$h1" -lt "$w1" ]; then return 1; fi
  if [ "$h2" -gt "$w2" ]; then return 0; fi
  if [ "$h2" -lt "$w2" ]; then return 1; fi
  [ "$h3" -ge "$w3" ]
}

# True (exit 0) when $1 exists and its first line (BOM/CR tolerant) is the policy header.
is_ours_claude_md() {
  local f="$1"
  [ -f "$f" ] || return 1
  python3 -c '
import sys
try:
    with open(sys.argv[1], "rb") as fh:
        data = fh.read()
except OSError:
    sys.exit(1)
if data[:3] == b"\xef\xbb\xbf":
    data = data[3:]
first = data.split(b"\n", 1)[0].rstrip(b"\r")
sys.exit(0 if first == b"# Agent operating policy" else 1)
' "$f"
}

check_dir_writable() {
  python3 -c '
import os, sys
p = os.path.realpath(sys.argv[1])
while not os.path.isdir(p):
    parent = os.path.dirname(p)
    if parent == p:
        sys.exit(1)
    p = parent
sys.exit(0 if os.access(p, os.W_OK) else 1)
' "$1"
}

check_file_dir_writable() {
  python3 -c '
import os, sys
d = os.path.dirname(os.path.realpath(sys.argv[1]))
p = d if d else "/"
while not os.path.isdir(p):
    parent = os.path.dirname(p)
    if parent == p:
        sys.exit(1)
    p = parent
sys.exit(0 if os.access(p, os.W_OK) else 1)
' "$1"
}

precheck_hardlink() {
  local target="$1"
  [ "$BREAK_HARDLINKS" -eq 1 ] && return 0
  local out rc=0
  out="$(python3 "$HERE/scripts/safe_write.py" check --target "$target" 2>&1)" || rc=$?
  if [ "$rc" -ne 0 ]; then
    printf '%s\n' "$out" >&2
    exit "$rc"
  fi
}

sw_write() {
  # sw_write TARGET FROM DEFAULT_MODE
  set -- write --target "$1" --from "$2" --default-mode "$3" --cfg "$CFG"
  [ "$BREAK_HARDLINKS" -eq 1 ] && set -- "$@" --break-hardlinks
  [ "$CREATE_THROUGH_DANGLING" -eq 1 ] && set -- "$@" --create-through-dangling
  python3 "$HERE/scripts/safe_write.py" "$@"
}

# Files skipped this run (unchanged or refused), reported in the Summary block.
SKIPPED=""
note_skip() {
  if [ -n "$SKIPPED" ]; then
    SKIPPED="$SKIPPED
$1"
  else
    SKIPPED="$1"
  fi
}

STAMP="$(date -u +%Y%m%dT%H%M%SZ)-$$"
BACKED_UP=0
BACKUP_DIR=""
INSTALLER_VERSION=""

take_backup() {
  # take_backup PATH... ; skips missing paths; reuses this run's stamp so every backup
  # taken during the run lands in the same directory.
  local dir
  dir="$(python3 "$HERE/scripts/safe_write.py" backup --cfg "$CFG" --stamp "$STAMP" --version "$INSTALLER_VERSION" "$@")"
  if [ -n "$dir" ]; then
    BACKUP_DIR="$dir"
    BACKED_UP=1
  fi
}

on_err() {
  local ec=$?
  # With errtrace the trap also runs inside command substitutions; only the top-level
  # invocation prints the hint, so a failing $(...) does not duplicate it.
  if [ "${BASH_SUBSHELL:-0}" -eq 0 ] && [ "$BACKED_UP" -eq 1 ]; then
    echo "backup: $BACKUP_DIR" >&2
    echo "restore with: ./install.sh --restore $STAMP" >&2
  fi
  exit "$ec"
}
trap on_err ERR

# ---- step 2: preconditions (write nothing) ----------------------------------------------

command -v python3 >/dev/null 2>&1 || { echo "python3 is required for the settings merge" >&2; exit 1; }
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)' >/dev/null 2>&1; then
  echo "python3 >= 3.8 is required (found: $(python3 -c 'import platform; print(platform.python_version())' 2>/dev/null || echo unknown))" >&2
  exit 1
fi
command -v claude >/dev/null 2>&1 || { echo "claude CLI not found on PATH" >&2; exit 1; }
CLAUDE_VERSION_RAW="$(claude --version 2>/dev/null || true)"
CLAUDE_VERSION="$(printf '%s\n' "$CLAUDE_VERSION_RAW" | sed -n 's/^[^0-9]*\([0-9][0-9]*\.[0-9][0-9]*\.[0-9][0-9]*\).*/\1/p' | head -n1)"
if [ -z "$CLAUDE_VERSION" ] || ! version_ge "$CLAUDE_VERSION" "2.1.267"; then
  echo "claude CLI ${CLAUDE_VERSION:-version could not be determined} found; this installer requires >= 2.1.267" >&2
  exit 1
fi

MARKETPLACE_JSON="$(claude plugin marketplace list --json 2>/dev/null || true)"
if ! printf '%s' "$MARKETPLACE_JSON" | python3 -c 'import json,sys; json.load(sys.stdin)' >/dev/null 2>&1; then
  echo "cannot verify the existing 'engineering' marketplace binding" >&2
  exit 1
fi


[ -f "$HERE/scripts/merge_settings.py" ] || { echo "internal error: scripts/merge_settings.py is missing" >&2; exit 1; }
[ -f "$HERE/scripts/safe_write.py" ] || { echo "internal error: scripts/safe_write.py is missing" >&2; exit 1; }

# Validate settings.json before any CLI call that could rewrite it (marketplace add and
# plugin install both write the file): an unusable file must stop the run here, exit 3.
RECOMMENDED="${ENGINEERING_RECOMMENDED:-$HERE/settings.recommended.json}"
if [ -n "${ENGINEERING_RECOMMENDED:-}" ]; then
  echo "recommendation file overridden by ENGINEERING_RECOMMENDED: $RECOMMENDED"
fi
SETTINGS_VALIDATE_RC=0
python3 "$HERE/scripts/merge_settings.py" --current "$CFG/settings.json" --recommended "$RECOMMENDED" --mode enforce --check >/dev/null || SETTINGS_VALIDATE_RC=$?
case "$SETTINGS_VALIDATE_RC" in
  0|10) ;;
  *) exit "$SETTINGS_VALIDATE_RC" ;;
esac

check_dir_writable "$CFG" || { echo "$CFG is not writable" >&2; exit 1; }
check_file_dir_writable "$CFG/settings.json" || { echo "the directory containing $CFG/settings.json is not writable" >&2; exit 1; }

if [ -e "$CFG/rules" ] && [ ! -d "$CFG/rules" ]; then
  echo "$CFG/rules exists and is not a directory; move it aside and rerun" >&2
  exit 1
fi

if [ -L "$CFG/settings.json" ] && [ ! -e "$CFG/settings.json" ] && [ "$CREATE_THROUGH_DANGLING" -eq 0 ]; then
  echo "settings.json is a dangling symlink; check out the dotfiles target or pass --create-through-dangling" >&2
  exit 4
fi

# Precheck only what this run may actually write: settings.json always, and a policy file
# only when it exists and is ours (a user-owned policy file is never written).
precheck_hardlink "$CFG/settings.json"
if is_ours_claude_md "$CFG/rules/engineering-policy.md"; then
  precheck_hardlink "$CFG/rules/engineering-policy.md"
fi
if is_ours_claude_md "$CFG/CLAUDE.md"; then
  precheck_hardlink "$CFG/CLAUDE.md"
fi

INSTALLER_VERSION="$(python3 -c '
import json, sys
try:
    print(json.load(open(sys.argv[1])).get("version", ""))
except Exception:
    print("")
' "$HERE/plugins/engineering/.claude-plugin/plugin.json" 2>/dev/null || true)"

# ---- step 3: preflight (read-only): mode, policy state, marketplace comparison ----------

# Policy state classification: none / ours-in-rules / ours-in-claude-md / user-rules-file / user-claude-md
RULES_TARGET="$CFG/rules/engineering-policy.md"
CLAUDE_TARGET="$CFG/CLAUDE.md"
if [ -f "$RULES_TARGET" ] || [ -L "$RULES_TARGET" ]; then
  if is_ours_claude_md "$RULES_TARGET"; then
    # Both ours: the legacy copy still loads, so this is a pending migration, not a no-op.
    if is_ours_claude_md "$CLAUDE_TARGET"; then POLICY_STATE="ours-in-claude-md"; else POLICY_STATE="ours-in-rules"; fi
  else
    POLICY_STATE="user-rules-file"
  fi
elif [ -f "$CLAUDE_TARGET" ] || [ -L "$CLAUDE_TARGET" ]; then
  if is_ours_claude_md "$CLAUDE_TARGET"; then POLICY_STATE="ours-in-claude-md"; else POLICY_STATE="user-claude-md"; fi
else
  POLICY_STATE="none"
fi

# Mode selection (decision 3), once.
MODE_REASON=""
if [ -n "$SETTINGS_MODE_FLAG" ]; then
  SETTINGS_MODE="$SETTINGS_MODE_FLAG"
  MODE_REASON="explicit --settings-mode"
elif [ -f "$CFG/engineering-installer.json" ]; then
  SETTINGS_MODE="defaults"
  MODE_REASON="installer marker present"
else
  PRIOR=0
  if [ -f "$CFG/settings.json" ]; then
    if python3 -c '
import json, sys
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    sys.exit(1)
sys.exit(0 if isinstance(d, dict) and "engineering@engineering" in d.get("enabledPlugins", {}) else 1)
' "$CFG/settings.json" 2>/dev/null; then
      PRIOR=1
    fi
  fi
  [ "$POLICY_STATE" = "ours-in-claude-md" ] && PRIOR=1
  if [ "$PRIOR" -eq 1 ]; then
    SETTINGS_MODE="defaults"
    MODE_REASON="first run of this installer on an existing configuration; run with --settings-mode enforce to apply the recommended values"
  else
    SETTINGS_MODE="enforce"
    MODE_REASON="no prior installation evidence found"
  fi
fi

# Marketplace source normalisation/comparison (decision 8).
marketplace_predict_json() {
  python3 -c '
import json, os, re, sys
source = sys.argv[1]
def predict(source):
    if os.path.isdir(source):
        return {"source": "directory", "path": os.path.realpath(source)}
    m = re.match(r"^git@github\.com:([^/]+)/(.+?)(\.git)?$", source)
    if m:
        return {"source": "github", "repo": "%s/%s" % (m.group(1), m.group(2))}
    m = re.match(r"^https?://github\.com/([^/]+)/([^/]+?)(\.git)?/?$", source)
    if m:
        return {"source": "github", "repo": "%s/%s" % (m.group(1), m.group(2))}
    m = re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", source)
    if m:
        return {"source": "github", "repo": source}
    s = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", source)
    s = re.sub(r"\.git$", "", s).rstrip("/")
    return {"source": "git", "path": s}
print(json.dumps({"source": predict(source)}))
' "$1"
}

marketplace_compare() {
  # marketplace_compare SOURCE < MARKETPLACE_JSON ; prints MATCH / ABSENT / "FOREIGN <json>" / UNPARSEABLE
  python3 -c '
import json, os, re, sys

def canon_github(owner, repo):
    repo = re.sub(r"\.git$", "", repo)
    return ("github", ("%s/%s" % (owner, repo)).lower())

def canon_git_url(s):
    s = re.sub(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", "", s)
    s = re.sub(r"\.git$", "", s).rstrip("/")
    parts = s.split("/", 1)
    parts[0] = parts[0].lower()
    return ("git", "/".join(parts))

def canon_requested(source):
    if os.path.isdir(source):
        return [("directory", os.path.abspath(source)), ("directory", os.path.realpath(source))]
    m = re.match(r"^git@github\.com:([^/]+)/(.+?)(\.git)?$", source)
    if m:
        return [canon_github(m.group(1), m.group(2))]
    m = re.match(r"^https?://github\.com/([^/]+)/([^/]+?)(\.git)?/?$", source)
    if m:
        return [canon_github(m.group(1), m.group(2))]
    m = re.match(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", source)
    if m:
        owner, repo = source.split("/", 1)
        return [canon_github(owner, repo)]
    return [canon_git_url(source)]

def canon_registered(entry):
    kind = entry.get("source")
    if kind == "github":
        repo = entry.get("repo", "")
        if "/" in repo:
            owner, r = repo.split("/", 1)
            return canon_github(owner, r)
        return ("github", repo.lower())
    if kind == "directory":
        p = entry.get("path", "") or entry.get("installLocation", "")
        try:
            return ("directory", os.path.realpath(p))
        except Exception:
            return ("directory", p)
    val = entry.get("repo") or entry.get("path") or ""
    return canon_git_url(val)

try:
    source = sys.argv[1]
    data = json.load(sys.stdin)
    entry = None
    for e in data:
        if e.get("name") == "engineering":
            entry = e
            break
    if entry is None:
        print("ABSENT")
        sys.exit(0)
    reg = canon_registered(entry)
    for form in canon_requested(source):
        if form == reg:
            print("MATCH")
            sys.exit(0)
    print("FOREIGN " + json.dumps(entry))
except Exception:
    print("UNPARSEABLE")
' "$1"
}

PREDICTED_ENTRY_JSON="$(marketplace_predict_json "$SOURCE")"
MARKETPLACE_CMP="$(printf '%s' "$MARKETPLACE_JSON" | marketplace_compare "$SOURCE")"

# ---- step 4: --dry-run preview -----------------------------------------------------------

if [ "$DRY_RUN" -eq 1 ]; then
  echo "mode: $SETTINGS_MODE ($MODE_REASON)"
  echo
  echo "settings.json diff:"
  DRIFT_TMP="$(mktemp)"
  python3 "$HERE/scripts/merge_settings.py" --current "$CFG/settings.json" --recommended "$RECOMMENDED" --mode "$SETTINGS_MODE" $OFFICIAL_FLAGS --diff --drift-report 2>"$DRIFT_TMP" || true
  if [ -s "$DRIFT_TMP" ]; then
    echo "drift report:"
    sed 's/^/  /' "$DRIFT_TMP"
    if [ "$SETTINGS_MODE" = "defaults" ]; then
      echo "apply the recommended values with: ./install.sh --settings-mode enforce"
    fi
  fi
  rm -f "$DRIFT_TMP"
  echo
  echo "policy action:"
  case "$POLICY_STATE" in
    none)
      if [ "$POLICY_TARGET" = "rules" ]; then echo "  would write rules/engineering-policy.md"; else echo "  would write CLAUDE.md"; fi ;;
    ours-in-claude-md)
      if [ "$POLICY_TARGET" = "rules" ]; then
        echo "  would prompt to migrate legacy CLAUDE.md to rules/engineering-policy.md (or refresh CLAUDE.md in place if declined/non-interactive)"
      else
        echo "  would refresh CLAUDE.md if changed"
      fi ;;
    ours-in-rules) echo "  would refresh rules/engineering-policy.md if changed" ;;
    user-claude-md) echo "  CLAUDE.md is not managed by this installer; would leave it untouched" ;;
    user-rules-file) echo "  rules/engineering-policy.md is not managed by this installer; would refuse to overwrite it" ;;
  esac
  echo
  echo "marketplace action:"
  case "$MARKETPLACE_CMP" in
    ABSENT) echo "  would register marketplace 'engineering' from '$SOURCE'" ;;
    MATCH) echo "  would update marketplace 'engineering' (already bound to '$SOURCE')" ;;
    FOREIGN*) echo "  marketplace 'engineering' is bound elsewhere; would refuse" ;;
    *) echo "  cannot verify the existing 'engineering' marketplace binding" ;;
  esac
  echo "predicted marketplace entry:"
  printf '%s\n' "$PREDICTED_ENTRY_JSON"
  echo
  echo "plugin actions:"
  echo "  engineering@engineering is always installed and enabled"
  if [ "$OFFICIAL" -eq 1 ] && [ "$PURGE_OFFICIAL" -eq 0 ]; then
    echo "  would register the official marketplace and install its plugins not disabled in your settings"
  elif [ "$PURGE_OFFICIAL" -eq 1 ]; then
    echo "  would purge official-marketplace entries from settings.json"
  else
    echo "  --no-official: official marketplace/plugins left alone"
  fi
  exit 0
fi

# ---- step 5: running-session warning (decision 11; best effort, never fatal) -----------

if command -v pgrep >/dev/null 2>&1 && command -v id >/dev/null 2>&1; then
  if pgrep -u "$(id -u)" -f 'claude-code/cli\.js|(^|/)claude( |$)' >/dev/null 2>&1; then
    echo "note: a running Claude Code session was detected; it may write settings.json at the same time. Writes here are atomic and backed up, so a conflicting write is recoverable with --restore." >&2
  fi
fi

# ---- step 6: marketplace add/update, refusing a foreign binding -------------------------

case "$MARKETPLACE_CMP" in
  ABSENT)
    claude plugin marketplace add "$SOURCE"
    echo "registered marketplace 'engineering' from '$SOURCE'"
    ;;
  MATCH)
    claude plugin marketplace update engineering >/dev/null || true
    echo "marketplace 'engineering' already bound to '$SOURCE'"
    ;;
  FOREIGN*)
    echo "marketplace 'engineering' is registered elsewhere, not '$SOURCE'; run 'claude plugin marketplace remove engineering' first to rebind it (${MARKETPLACE_CMP#FOREIGN })" >&2
    exit 1
    ;;
  *)
    echo "cannot verify the existing 'engineering' marketplace binding" >&2
    exit 1
    ;;
esac

# ---- step 7: recompute the merge after registration (validation only; not written) -----

python3 "$HERE/scripts/merge_settings.py" --current "$CFG/settings.json" --recommended "$RECOMMENDED" --mode "$SETTINGS_MODE" $OFFICIAL_FLAGS >/dev/null

# ---- step 8: plugin install, then the decision-1 policy-target gate --------------------

claude plugin install engineering@engineering --scope user
echo "installed engineering@engineering"

INSTALLED_VERSION="$(claude plugin list --json 2>/dev/null | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(1)
if isinstance(data, dict):
    for key in ("plugins", "installed", "entries"):
        if isinstance(data.get(key), list):
            data = data[key]
            break
if not isinstance(data, list):
    sys.exit(1)
for e in data:
    if not isinstance(e, dict):
        continue
    market = ""
    for key in ("marketplace", "marketplaceName", "marketplace_name"):
        val = e.get(key)
        if isinstance(val, str) and val:
            market = val
            break
    match = False
    for key in ("id", "name"):
        ident = e.get(key)
        if not isinstance(ident, str):
            continue
        if ident == "engineering@engineering":
            match = True
        elif ident == "engineering" and market in ("", "engineering"):
            match = True
    if match:
        v = e.get("version")
        if isinstance(v, str) and v:
            print(v)
            sys.exit(0)
sys.exit(1)
' 2>/dev/null || true)"

if [ -z "$INSTALLED_VERSION" ]; then
  CACHE_BASE="$CFG/plugins/cache/engineering/engineering"
  if [ -d "$CACHE_BASE" ]; then
    INSTALLED_VERSION="$(python3 -c '
import glob, json, os, re, sys
base = sys.argv[1]
best = ""
best_key = None
for d in sorted(glob.glob(os.path.join(base, "*"))):
    name = os.path.basename(d)
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", name)
    if not m or not os.path.isdir(d):
        continue
    pj = os.path.join(d, ".claude-plugin", "plugin.json")
    if not os.path.isfile(pj):
        continue
    try:
        json.load(open(pj))
    except Exception:
        continue
    key = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    if best_key is None or key > best_key:
        best_key = key
        best = name
print(best)
' "$CACHE_BASE" 2>/dev/null || true)"
  fi
fi

# The gate is the installed hook's capability, not a version number: the cached hook must
# check rules/engineering-policy.md, otherwise a rules-file policy would load twice.
installed_hook_supports_rules() {
  local hook="$CFG/plugins/cache/engineering/engineering/$INSTALLED_VERSION/hooks/session-start.sh"
  [ -f "$hook" ] && grep -q 'rules/engineering-policy.md' "$hook"
}
if [ -n "$INSTALLED_VERSION" ]; then
  if [ "$POLICY_TARGET" = "rules" ] && ! installed_hook_supports_rules; then
    POLICY_TARGET="claude-md"
    echo "installed plugin $INSTALLED_VERSION does not support the rules-file policy; keeping the policy in CLAUDE.md"
  fi
else
  if [ "$POLICY_TARGET" = "rules" ]; then
    POLICY_TARGET="claude-md"
    echo "could not determine the installed engineering plugin version; keeping the policy in CLAUDE.md" >&2
  fi
fi

# A config directory that did not exist before this run was created by the CLI during
# marketplace registration; it holds settings.json and backups, so it is made private.
if [ "$CFG_PREEXISTED" -eq 0 ] && [ -d "$CFG" ]; then
  python3 -c 'import os, sys; os.chmod(os.path.realpath(sys.argv[1]), 0o700)' "$CFG"
fi

# ---- step 9: settings merge on the post-install file ------------------------------------

# First write of the run: create $CFG (private) if nothing above it created it already.
if [ ! -d "$CFG" ]; then
  mkdir -p "$(dirname "$CFG")"
  mkdir -m 0700 "$CFG"
fi

DRIFT_REPORT_TEXT=""
if [ "$SETTINGS_MODE" = "defaults" ]; then
  DRIFT_REPORT_TEXT="$(python3 "$HERE/scripts/merge_settings.py" --current "$CFG/settings.json" --recommended "$RECOMMENDED" --mode "$SETTINGS_MODE" $OFFICIAL_FLAGS --drift-report 2>&1 >/dev/null)" || true
fi

MERGE_CHECK_RC=0
python3 "$HERE/scripts/merge_settings.py" --current "$CFG/settings.json" --recommended "$RECOMMENDED" --mode "$SETTINGS_MODE" $OFFICIAL_FLAGS --check || MERGE_CHECK_RC=$?
case "$MERGE_CHECK_RC" in
  0)
    echo "settings.json: unchanged"
    note_skip "settings.json: unchanged"
    ;;
  10)
    take_backup "$CFG/settings.json"
    TMP_SETTINGS="$(mktemp)"
    python3 "$HERE/scripts/merge_settings.py" --current "$CFG/settings.json" --recommended "$RECOMMENDED" --mode "$SETTINGS_MODE" $OFFICIAL_FLAGS > "$TMP_SETTINGS"
    sw_write "$CFG/settings.json" "$TMP_SETTINGS" 0600
    rm -f "$TMP_SETTINGS"
    if [ "$SETTINGS_PREEXISTED" -eq 0 ]; then
      python3 -c 'import os, sys; os.chmod(os.path.realpath(sys.argv[1]), 0o600)' "$CFG/settings.json"
    fi
    echo "wrote settings.json"
    ;;
  *)
    echo "settings.json could not be merged (exit $MERGE_CHECK_RC); aborting without further changes" >&2
    exit "$MERGE_CHECK_RC"
    ;;
esac

# ---- step 10: policy (decisions 1, 2) ----------------------------------------------------

write_policy_claude_md() {
  local target="$CFG/CLAUDE.md"
  if [ -f "$target" ] || [ -L "$target" ]; then
    if ! is_ours_claude_md "$target"; then
      echo "CLAUDE.md exists and is not managed by this installer; leaving it untouched" >&2
      note_skip "CLAUDE.md: not managed by this installer; left untouched"
      return 0
    fi
    if cmp -s "$target" "$POLICY_SRC" 2>/dev/null; then
      echo "CLAUDE.md: unchanged"
      note_skip "CLAUDE.md: unchanged"
      return 0
    fi
    take_backup "$target"
  fi
  sw_write "$target" "$POLICY_SRC" 0644
  echo "wrote CLAUDE.md"
}

write_policy_rules() {
  local target="$RULES_TARGET"
  if [ -f "$target" ] || [ -L "$target" ]; then
    if ! is_ours_claude_md "$target"; then
      echo "rules/engineering-policy.md exists and is not managed by this installer; refusing to overwrite it" >&2
      exit 1
    fi
    if cmp -s "$target" "$POLICY_SRC" 2>/dev/null; then
      echo "rules/engineering-policy.md: unchanged"
      note_skip "rules/engineering-policy.md: unchanged"
      return 0
    fi
    take_backup "$target"
  fi
  sw_write "$target" "$POLICY_SRC" 0644
  echo "wrote rules/engineering-policy.md"
}

migrate_or_refresh_legacy() {
  local target="$CLAUDE_TARGET"
  local confirmed=0
  if [ "$YES" -eq 1 ]; then
    confirmed=1
  elif [ -n "${ENGINEERING_NO_PROMPT:-}" ]; then
    confirmed=0
  else
    if exec 3<>/dev/tty 2>/dev/null; then
      printf 'Migrate the existing ~/.claude/CLAUDE.md policy to ~/.claude/rules/engineering-policy.md? [y/N] ' >&3
      ans=""
      read -r ans <&3 || ans=""
      exec 3<&- 3>&- 2>/dev/null || true
      case "$ans" in
        y|Y|yes|YES) confirmed=1 ;;
        *) confirmed=0 ;;
      esac
    fi
  fi

  if [ "$confirmed" -eq 1 ]; then
    take_backup "$target"
    if [ -L "$target" ]; then
      rm -f "$target"
      echo "removed the CLAUDE.md symlink (its target was left in place)"
    else
      rm -f "$target"
    fi
    echo "migrated legacy CLAUDE.md policy to rules/engineering-policy.md"
    MIGRATED=1
  else
    if is_ours_claude_md "$RULES_TARGET"; then
      echo "rules/engineering-policy.md is already installed; not refreshing CLAUDE.md (remove one copy or run ./install.sh --yes to migrate)"
      note_skip "CLAUDE.md: rules/engineering-policy.md is already installed"
    else
      write_policy_claude_md
    fi
    echo "policy left in CLAUDE.md; migrate later: ./install.sh --yes"
    MIGRATED=0
    POLICY_TARGET="claude-md"
  fi
}

MIGRATED=0
if [ "$POLICY_TARGET" = "claude-md" ]; then
  # A rules-file policy already installed would load twice if CLAUDE.md carried it too.
  if is_ours_claude_md "$RULES_TARGET"; then
    echo "rules/engineering-policy.md is already installed; not writing CLAUDE.md (remove the rules file or use --policy-target rules)"
    note_skip "CLAUDE.md: rules/engineering-policy.md is already installed"
  else
    write_policy_claude_md
  fi
else
  if is_ours_claude_md "$CLAUDE_TARGET"; then
    migrate_or_refresh_legacy
    if [ "$MIGRATED" -eq 1 ]; then
      write_policy_rules
    fi
  else
    write_policy_rules
  fi
fi

# ---- step 11: official marketplace and plugins (unless --no-official/--purge-official) --

if [ "$OFFICIAL" -eq 1 ] && [ "$PURGE_OFFICIAL" -eq 0 ]; then
  claude plugin marketplace add anthropics/claude-plugins-official >/dev/null 2>&1 || true
  for p in superpowers context7 code-review playwright frontend-design claude-code-setup claude-md-management typescript-lsp pyright-lsp rust-analyzer-lsp gopls-lsp; do
    if python3 -c '
import json, sys
path, key = sys.argv[1], sys.argv[2]
try:
    d = json.load(open(path))
except Exception:
    sys.exit(1)
sys.exit(0 if d.get("enabledPlugins", {}).get(key) is False else 1)
' "$CFG/settings.json" "$p@claude-plugins-official"; then
      echo "skipped $p (disabled in your settings)"
      continue
    fi
    if claude plugin install "$p@claude-plugins-official" --scope user >/dev/null; then
      echo "installed $p"
    else
      echo "WARN: could not install $p" >&2
    fi
  done
fi

# ---- step 12: installer marker + summary -------------------------------------------------

TIMESTAMP="$(python3 -c 'import datetime; print(datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))')"
MARKER_JSON="$(python3 -c '
import json, sys
print(json.dumps({
    "schema": 1,
    "installer_version": sys.argv[1],
    "timestamp": sys.argv[2],
    "settings_mode": sys.argv[3],
    "policy_target": sys.argv[4],
}, indent=2))
' "$INSTALLER_VERSION" "$TIMESTAMP" "$SETTINGS_MODE" "$POLICY_TARGET")"
TMP_MARKER="$(mktemp)"
printf '%s\n' "$MARKER_JSON" > "$TMP_MARKER"
sw_write "$CFG/engineering-installer.json" "$TMP_MARKER" 0600 >/dev/null
rm -f "$TMP_MARKER"

echo
echo "Summary:"
echo "  config dir: $CFG"
echo "  mode: $SETTINGS_MODE ($MODE_REASON)"
echo "  policy target: $POLICY_TARGET"
if [ -n "$DRIFT_REPORT_TEXT" ]; then
  echo "  drift report ($SETTINGS_MODE mode):"
  printf '%s\n' "$DRIFT_REPORT_TEXT" | sed 's/^/    /'
  echo "apply the recommended values with: ./install.sh --settings-mode enforce"
fi
if [ -n "$SKIPPED" ]; then
  echo "  skipped:"
  printf '%s\n' "$SKIPPED" | sed 's/^/    /'
fi
if [ "$BACKED_UP" -eq 1 ]; then
  echo "  backup: $BACKUP_DIR"
  echo "  restore with: ./install.sh --restore $STAMP"
fi
echo
echo "Verify with:  claude plugin list   and   claude --print '/help' (look for /engineering:* skills)"
echo "restart Claude Code if a session was already running, so it picks up the new policy and hook."
