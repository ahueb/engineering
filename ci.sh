#!/usr/bin/env bash
# Local CI gate. Runs before every push (see .githooks/pre-push) and inside release.sh.
# No GitHub Actions or server-side hooks are used: this script is the only gate.
#
#   ./ci.sh --quick    static checks and unit tests only
#   ./ci.sh            (default) adds every offline scratch-install scenario; this is
#                       what .githooks/pre-push and release.sh normally run
#   ./ci.sh --full     adds the two network scenarios (default official-plugin install,
#                       rules-file load via `claude -p --model haiku`); fails (exit 1)
#                       rather than skipping a scenario it cannot run (no credentials at
#                       $HOME/.claude/.credentials.json, no network) unless CI_ALLOW_SKIP=1
#   ./ci.sh -h          show this help
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN="$HERE/plugins/engineering"
PRR="$PLUGIN/skills/production-readiness-review"

# ---- flag parsing ------------------------------------------------------------------------

TIER="default"
for arg in "$@"; do
  case "$arg" in
    --quick) TIER="quick" ;;
    --full) TIER="full" ;;
    -h|--help)
      sed -n '2,14p' "$HERE/ci.sh" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "unknown flag: $arg" >&2
      echo "usage: $0 [--quick|--full] [-h]" >&2
      exit 2
      ;;
  esac
done

fail=0
step() { printf '\n== %s\n' "$1"; }
ok() { echo "   ok: $1"; }
bad() { echo "   FAIL: $1" >&2; fail=1; }

for tool in bash python3 claude; do
  command -v "$tool" >/dev/null || { echo "$tool is required" >&2; exit 1; }
done

step "shell syntax and lint"
# bash -n only parses its *first* file argument, so every file gets its own run.
syntax_ok=1
for f in "$HERE/install.sh" "$HERE/release.sh" "$HERE/ci.sh" "$PLUGIN/hooks/session-start.sh"; do
  bash -n "$f" || { syntax_ok=0; echo "   bash -n failed: $f" >&2; }
done
[ "$syntax_ok" = 1 ] && ok "bash -n" || bad "bash -n"
if command -v shellcheck >/dev/null; then
  shellcheck -S warning "$HERE/install.sh" "$HERE/release.sh" "$HERE/ci.sh" "$PLUGIN/hooks/session-start.sh" && ok "shellcheck" || bad "shellcheck"
elif [ "${CI_ALLOW_SKIP:-0}" = "1" ]; then
  echo "   skip: shellcheck not installed (CI_ALLOW_SKIP=1)"
else
  bad "shellcheck is not installed; install it or set CI_ALLOW_SKIP=1"
fi

step "plugin and marketplace manifests"
claude plugin validate "$PLUGIN" --strict >/dev/null && ok "plugin validate --strict" || bad "plugin validate --strict"
claude plugin validate "$HERE" --strict >/dev/null && ok "marketplace validate --strict" || bad "marketplace validate --strict"
python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$PLUGIN/hooks/hooks.json" && ok "hooks.json is JSON" || bad "hooks.json is JSON"
python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$HERE/settings.recommended.json" && ok "settings.recommended.json is JSON" || bad "settings.recommended.json is JSON"

step "probe"
python3 -W error -m py_compile "$PRR/scripts/repo_probe.py" && ok "py_compile" || bad "py_compile"
python3 -X dev -m unittest "$PRR/tests/test_repo_probe.py" >/dev/null 2>&1 && ok "unit tests" || bad "unit tests"
rm -rf "$PRR/tests/__pycache__" "$PRR/scripts/__pycache__"

step "scripts unit tests (merge_settings, safe_write)"
(cd "$HERE" && python3 -W error -m py_compile scripts/merge_settings.py scripts/safe_write.py) && ok "py_compile" || bad "py_compile"
(cd "$HERE" && python3 -X dev -m unittest scripts.tests.test_merge_settings scripts.tests.test_safe_write >/dev/null 2>&1) && ok "unit tests" || bad "unit tests"
rm -rf "$HERE/scripts/__pycache__" "$HERE/scripts/tests/__pycache__"

step "frontmatter, policy, and cross-references"
python3 - "$PLUGIN" "$HERE" <<'PY' && ok "frontmatter and references" || bad "frontmatter and references"
import glob, re, sys, os
plugin, root = sys.argv[1], sys.argv[2]
problems = []
names = set()
for f in glob.glob(f"{plugin}/agents/*.md") + glob.glob(f"{plugin}/skills/*/SKILL.md"):
    t = open(f).read()
    m = re.match(r"^---\n(.*?)\n---\n", t, re.S)
    if not m:
        problems.append(f"{f}: no frontmatter"); continue
    fm = dict(l.split(":", 1) for l in m.group(1).splitlines() if ":" in l)
    n, d = fm.get("name", "").strip(), fm.get("description", "").strip()
    names.add(n)
    if not n or len(n) > 64 or not re.fullmatch(r"[a-z0-9-]+", n): problems.append(f"{f}: bad name {n!r}")
    if not d or len(d) > 1024: problems.append(f"{f}: description length {len(d)}")
    if "effort" in fm and fm["effort"].strip() not in ("low", "medium", "high", "xhigh", "max"): problems.append(f"{f}: effort {fm['effort']!r}")
policy = open(f"{plugin}/context/CLAUDE.md").read()
if not policy.startswith("# Agent operating policy\n"): problems.append("policy first line changed")
if policy.count("\n") > 120: problems.append(f"policy is {policy.count(chr(10))} lines")
scan = [f"{root}/README.md", f"{root}/CHANGELOG.md", f"{plugin}/context/CLAUDE.md"] + glob.glob(f"{plugin}/skills/*/SKILL.md") + glob.glob(f"{plugin}/agents/*.md")
for f in scan:
    for ref in set(re.findall(r"engineering:([a-z-]+)", open(f).read())):
        if ref not in names: problems.append(f"{f}: unknown reference engineering:{ref}")
for p in problems: print("   " + p)
sys.exit(1 if problems else 0)
PY

step "doc cross-reference (install.sh flags/env vs README; forbidden phrasing)"
python3 - "$HERE/install.sh" "$HERE/README.md" "$HERE/SECURITY.md" "$HERE/CHANGELOG.md" "$HERE/docs/risk-register.md" <<'PY' && ok "doc cross-reference" || bad "doc cross-reference"
import re, sys
install_sh, readme, security, changelog, riskreg = sys.argv[1:6]
text = open(install_sh, encoding="utf-8").read()
flags = set(re.findall(r'^\s{4,}(--[a-zA-Z0-9-]+)(?:\|[^)]*)?\)', text, re.M))
flags.discard("--help")
envs = ["ENGINEERING_NO_PROMPT", "ENGINEERING_RECOMMENDED"]
readme_text = open(readme, encoding="utf-8").read()
problems = []
if not flags:
    problems.append("no --flags found in install.sh's case parser (regex broke?)")
for f in sorted(flags):
    if f not in readme_text:
        problems.append(f"README.md missing flag {f}")
for e in envs:
    if e not in readme_text:
        problems.append(f"README.md missing env var {e}")
forbidden = [".bak-<timestamp>", "copies it to `CLAUDE.md`"]
for path in (readme, security, changelog, riskreg):
    t = open(path, encoding="utf-8").read()
    for phrase in forbidden:
        if phrase in t:
            problems.append(f"{path}: contains forbidden phrase {phrase!r}")
for p in problems:
    print("   " + p)
sys.exit(1 if problems else 0)
PY

# hook contract begin
step "hook contract"
HOOK_OUTER_PLAIN="$(mktemp -d)"
HOOK_OUTER_SPACE="$(mktemp -d)"
for tmp in "$HOOK_OUTER_PLAIN" "$HOOK_OUTER_SPACE/has space"; do
  mkdir -p "$tmp"

  rm -rf "$tmp/CLAUDE.md" "$tmp/rules"
  mkdir -p "$tmp/rules"
  cp "$PLUGIN/context/CLAUDE.md" "$tmp/rules/engineering-policy.md"
  [ -z "$(CLAUDE_CONFIG_DIR="$tmp" bash "$PLUGIN/hooks/session-start.sh")" ] && ok "silent when rules file installed ($tmp)" || bad "hook not silent when rules file installed ($tmp)"

  rm -rf "$tmp/CLAUDE.md" "$tmp/rules"
  cp "$PLUGIN/context/CLAUDE.md" "$tmp/CLAUDE.md"
  [ -z "$(CLAUDE_CONFIG_DIR="$tmp" bash "$PLUGIN/hooks/session-start.sh")" ] && ok "silent when legacy CLAUDE.md installed ($tmp)" || bad "hook not silent when legacy CLAUDE.md installed ($tmp)"

  mkdir -p "$tmp/rules"
  cp "$PLUGIN/context/CLAUDE.md" "$tmp/rules/engineering-policy.md"
  [ -z "$(CLAUDE_CONFIG_DIR="$tmp" bash "$PLUGIN/hooks/session-start.sh")" ] && ok "silent when both present ($tmp)" || bad "hook not silent when both present ($tmp)"

  # An installed copy whose content is out of date yields a one-line notice, not a second policy.
  rm -rf "$tmp/CLAUDE.md" "$tmp/rules"; mkdir -p "$tmp/rules"
  printf '# Agent operating policy\n\nold text\n' > "$tmp/rules/engineering-policy.md"
  stale_out="$(CLAUDE_CONFIG_DIR="$tmp" bash "$PLUGIN/hooks/session-start.sh")"
  case "$stale_out" in
    "engineering: installed policy "*"differs from the plugin's bundled policy"*) [ "$(printf '%s\n' "$stale_out" | wc -l)" -eq 1 ] && ok "one-line notice when the installed policy is stale ($tmp)" || bad "stale-policy notice is not one line ($tmp)" ;;
    *) bad "no stale-policy notice, or the policy was injected twice ($tmp)" ;;
  esac

  rm -rf "$tmp/CLAUDE.md" "$tmp/rules"
  [ "$(CLAUDE_CONFIG_DIR="$tmp" bash "$PLUGIN/hooks/session-start.sh" | head -1)" = "# Agent operating policy" ] && ok "injects when neither present ($tmp)" || bad "hook does not inject when neither present ($tmp)"

  printf '# other\n# Agent operating policy\n' > "$tmp/CLAUDE.md"
  [ "$(CLAUDE_CONFIG_DIR="$tmp" bash "$PLUGIN/hooks/session-start.sh" | head -1)" = "# Agent operating policy" ] && ok "injects when header not on first line ($tmp)" || bad "hook does not inject when header not on first line ($tmp)"
  rm -f "$tmp/CLAUDE.md"

  # A directory or FIFO at either policy location must not block session start.
  rm -rf "$tmp/CLAUDE.md" "$tmp/rules"
  mkdir -p "$tmp/rules/engineering-policy.md"
  hook_guard_run() {
    if command -v timeout >/dev/null 2>&1; then
      CLAUDE_CONFIG_DIR="$tmp" timeout 10 bash "$PLUGIN/hooks/session-start.sh" | head -1
    else
      CLAUDE_CONFIG_DIR="$tmp" bash "$PLUGIN/hooks/session-start.sh" | head -1
    fi
  }
  [ "$(hook_guard_run)" = "# Agent operating policy" ] && ok "injects when rules path is a directory ($tmp)" || bad "hook mishandles a directory at the rules path ($tmp)"
  if command -v mkfifo >/dev/null 2>&1; then
    rm -rf "$tmp/CLAUDE.md" "$tmp/rules"
    mkfifo "$tmp/CLAUDE.md"
    [ "$(hook_guard_run)" = "# Agent operating policy" ] && ok "injects when CLAUDE.md is a FIFO ($tmp)" || bad "hook blocks or mishandles a FIFO at CLAUDE.md ($tmp)"
    rm -f "$tmp/CLAUDE.md"
  else
    echo "   skip: mkfifo not available"
  fi

  rm -rf "$tmp"
done
rm -rf "$HOOK_OUTER_PLAIN" "$HOOK_OUTER_SPACE"
# hook contract end

# ============================================================================================
# Installer behavioural scenarios (default and --full tiers). Every scenario runs in a fresh
# CLAUDE_CONFIG_DIR, passes --yes unless it tests the prompt, and uninstalls
# engineering@engineering from that config at the end (best effort). Assertions on
# settings.json use python3 -c structural checks, never byte compares.
# ============================================================================================

new_cfg() { mktemp -d; }

install_in() {
  # install_in CFG [ARGS...]
  local cfg="$1"; shift
  CLAUDE_CONFIG_DIR="$cfg" "$HERE/install.sh" "$@"
}

run_capture() {
  # run_capture CFG [ARGS...] -> sets OUT (combined stdout+stderr) and RC
  local cfg="$1"; shift
  if OUT="$(CLAUDE_CONFIG_DIR="$cfg" "$HERE/install.sh" "$@" 2>&1)"; then
    RC=0
  else
    RC=$?
  fi
}

uninstall_in() {
  local cfg="$1"
  CLAUDE_CONFIG_DIR="$cfg" claude plugin uninstall engineering@engineering >/dev/null 2>&1 || true
}

shim_bin() {
  # shim_bin SHIM_PATH NAME -> prints a fresh directory containing NAME -> SHIM_PATH
  local shim="$1" name="$2" d
  d="$(mktemp -d)"
  ln -s "$shim" "$d/$name"
  printf '%s\n' "$d"
}

policy_src() { printf '%s\n' "$PLUGIN/context/CLAUDE.md"; }

sha256_of() {
  # portable: macOS has no sha256sum
  python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"
}

stamp_with() {
  # stamp_with CFG REL -> newest backup stamp whose manifest lists REL ("" if none)
  python3 -c '
import glob, json, os, sys
cfg, rel = sys.argv[1], sys.argv[2]
best = ""
for d in sorted(glob.glob(os.path.join(cfg, "backups", "engineering", "*"))):
    m = os.path.join(d, "manifest.json")
    if not os.path.isfile(m):
        continue
    try:
        data = json.load(open(m))
    except Exception:
        continue
    if any(isinstance(f, dict) and f.get("rel") == rel for f in data.get("files", [])):
        best = os.path.basename(d)
print(best)
' "$1" "$2"
}

count_stamps() {
  [ -d "$1/backups/engineering" ] || { echo 0; return 0; }
  find "$1/backups/engineering" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l | tr -d ' '
}

marketplace_has_engineering() {
  # marketplace_has_engineering CFG -> 0 when an 'engineering' marketplace is registered
  local listing
  listing="$(CLAUDE_CONFIG_DIR="$1" claude plugin marketplace list --json 2>/dev/null || true)"
  printf '%s' "$listing" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
except Exception:
    sys.exit(1)
if isinstance(data, dict):
    data = data.get("marketplaces", [])
sys.exit(0 if any(isinstance(e, dict) and e.get("name") == "engineering" for e in data) else 1)
'
}

network_available() {
  if command -v curl >/dev/null 2>&1; then
    curl -fsS --max-time 5 -o /dev/null https://github.com 2>/dev/null && return 0
    return 1
  fi
  python3 -c '
import socket, sys
try:
    socket.create_connection(("github.com", 443), timeout=5).close()
except OSError:
    sys.exit(1)
' 2>/dev/null
}

FULL_RAN=""

# ---- S1: invalid JSON --------------------------------------------------------------------
s01() {
  step "S1: invalid JSON settings.json is rejected, nothing written"
  local cfg; cfg="$(new_cfg)"
  printf '{not valid json' > "$cfg/settings.json" || bad "S1: setup failed"
  run_capture "$cfg" --yes --no-official
  [ "$RC" -eq 3 ] && ok "S1: install rejected invalid JSON (rc=3)" || bad "S1: expected exit 3, got $RC"
  case "$OUT" in *"invalid JSON"*) ok "S1: error names invalid JSON" ;; *) bad "S1: error message missing 'invalid JSON'" ;; esac
  [ ! -e "$cfg/CLAUDE.md" ] && [ ! -e "$cfg/rules/engineering-policy.md" ] && ok "S1: no policy file written" || bad "S1: a policy file was written"
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S2: empty / whitespace-only settings.json -----------------------------------------
s02() {
  step "S2: empty and whitespace-only settings.json treated as {}"
  local cfg; cfg="$(new_cfg)"
  : > "$cfg/settings.json"
  run_capture "$cfg" --yes --no-official
  [ "$RC" -eq 0 ] && ok "S2: empty file install succeeded" || bad "S2: empty file install failed (rc=$RC): $OUT"
  case "$OUT" in *"treating as {}"*) ok "S2: empty-file notice printed" ;; *) bad "S2: empty-file notice missing" ;; esac
  python3 -c '
import json, sys
d = json.load(open(sys.argv[1] + "/settings.json"))
assert d["enabledPlugins"]["engineering@engineering"] is True
' "$cfg" && ok "S2: settings merged" || bad "S2: settings not merged"
  uninstall_in "$cfg"; rm -rf "$cfg"

  cfg="$(new_cfg)"
  printf '   \n\t\n' > "$cfg/settings.json" || bad "S2: setup failed"
  run_capture "$cfg" --yes --no-official
  [ "$RC" -eq 0 ] && ok "S2: whitespace-only file install succeeded" || bad "S2: whitespace-only file install failed (rc=$RC): $OUT"
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S3: null / array / scalar top level -------------------------------------------------
s03() {
  step "S3: null, array, scalar settings.json produce typed messages"
  local cfg
  for pair in 'null:null' '[]:array' '"x":string'; do
    local content="${pair%%:*}" typename="${pair##*:}"
    cfg="$(new_cfg)"
    printf '%s' "$content" > "$cfg/settings.json" || bad "S3: setup failed"
    run_capture "$cfg" --yes --no-official
    [ "$RC" -eq 3 ] && ok "S3: rejected top-level $typename (rc=3)" || bad "S3: expected exit 3 for $typename, got $RC"
    case "$OUT" in *"top level is $typename"*) ok "S3: message names top-level $typename" ;; *) bad "S3: message missing 'top level is $typename': $OUT" ;; esac
    [ ! -e "$cfg/CLAUDE.md" ] && [ ! -e "$cfg/rules/engineering-policy.md" ] && ok "S3: nothing written ($typename)" || bad "S3: a policy file was written ($typename)"
    uninstall_in "$cfg"; rm -rf "$cfg"
  done
}

# ---- S4: fresh install --------------------------------------------------------------------
s04() {
  step "S4: fresh install"
  local cfg; cfg="$(new_cfg)"
  run_capture "$cfg" --yes --no-official
  [ "$RC" -eq 0 ] && ok "S4: fresh install succeeded" || bad "S4: fresh install failed (rc=$RC): $OUT"
  [ -f "$cfg/rules/engineering-policy.md" ] && ok "S4: rules file present" || bad "S4: rules file missing"
  [ ! -e "$cfg/CLAUDE.md" ] && ok "S4: no CLAUDE.md created" || bad "S4: CLAUDE.md was created"
  python3 -c '
import json, sys
d = json.load(open(sys.argv[1] + "/settings.json"), object_pairs_hook=lambda p: p)
assert d[0][0] == "$schema", d[0]
' "$cfg" && ok "S4: \$schema is first key" || bad "S4: \$schema is not first key"
  python3 -c '
import os, stat, sys
cfg = sys.argv[1]
assert stat.S_IMODE(os.stat(cfg + "/settings.json").st_mode) == 0o600
assert stat.S_IMODE(os.stat(cfg + "/rules/engineering-policy.md").st_mode) == 0o644
assert os.path.isfile(cfg + "/engineering-installer.json")
assert stat.S_IMODE(os.stat(cfg + "/engineering-installer.json").st_mode) == 0o600
' "$cfg" && ok "S4: modes and marker correct" || bad "S4: modes or marker incorrect"
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S5/S6: seeded fixture, enforce / defaults --------------------------------------------
s05() {
  step "S5: seeded fixture, enforce"
  local cfg; cfg="$(new_cfg)"
  cp "$HERE/ci/fixtures/settings-seeded.json" "$cfg/settings.json" || bad "S5: setup failed"
  ENGINEERING_RECOMMENDED="$HERE/ci/fixtures/recommended-with-list.json" \
    run_capture "$cfg" --yes --no-official --settings-mode enforce
  [ "$RC" -eq 0 ] && ok "S5: install succeeded" || bad "S5: install failed (rc=$RC): $OUT"
  # Note: install.sh only computes/prints a drift report in defaults mode (decision 3's
  # drift-report bullet is under "defaults"); enforce mode does not surface a ref-loss line
  # in the summary, so the ref loss is verified structurally below instead.
  python3 - "$cfg/settings.json" <<'PY' && ok "S5: merged shape correct" || bad "S5: merged shape incorrect"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["model"] == "sonnet", d["model"]
allow = d["permissions"]["allow"]
assert allow == ["Bash(git status)", "Bash(ls)", "Bash(git diff)"], allow
assert d["env"]["FOO"] == "bar"
assert d["modelSettings"]["claude-opus-5"]["effortLevel"] == "high"
assert d["enabledPlugins"]["sample@claude-plugins-official"] is False
assert "ref" not in d["extraKnownMarketplaces"]["widgets"]["source"]
assert d["enabledPlugins"]["engineering@engineering"] is True
PY
  uninstall_in "$cfg"; rm -rf "$cfg"
}

s06() {
  step "S6: seeded fixture, defaults"
  local cfg; cfg="$(new_cfg)"
  cp "$HERE/ci/fixtures/settings-seeded.json" "$cfg/settings.json" || bad "S6: setup failed"
  ENGINEERING_RECOMMENDED="$HERE/ci/fixtures/recommended-with-list.json" \
    run_capture "$cfg" --yes --no-official --settings-mode defaults
  [ "$RC" -eq 0 ] && ok "S6: install succeeded" || bad "S6: install failed (rc=$RC): $OUT"
  # the drift report prints one "drift: <dotted.path>: recommended=<json> current=<json>"
  # line per path; `model` is not a secret-bearing path, so its values are shown.
  printf '%s\n' "$OUT" | grep -Eq '^[[:space:]]*drift: model: recommended=' \
    && ok "S6: drift report names model with recommended=" || bad "S6: drift report missing a 'model: recommended=' line"
  python3 - "$cfg/settings.json" <<'PY' && ok "S6: merged shape correct" || bad "S6: merged shape incorrect"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["model"] == "haiku", d["model"]
assert d["extraKnownMarketplaces"]["widgets"]["source"]["ref"] == "v1.2.3"
PY
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S7: upgrade from 2.7.x -----------------------------------------------------------------
s07() {
  step "S7: upgrade from 2.7.x (no marker, legacy CLAUDE.md policy)"
  local cfg; cfg="$(new_cfg)"
  cp "$HERE/ci/fixtures/settings-27x-upgrade.json" "$cfg/settings.json" || bad "S7: setup failed"
  cp "$(policy_src)" "$cfg/CLAUDE.md" || bad "S7: setup failed"
  run_capture "$cfg" --yes --no-official
  [ "$RC" -eq 0 ] && ok "S7: first 2.8.0 run succeeded" || bad "S7: first run failed (rc=$RC): $OUT"
  case "$OUT" in *"mode: defaults"*) ok "S7: mode defaults selected" ;; *) bad "S7: mode not defaults: $OUT" ;; esac
  case "$OUT" in *"first run of this installer on an existing configuration; run with --settings-mode enforce to apply the recommended values"*) ok "S7: first-run line printed" ;; *) bad "S7: first-run line missing" ;; esac
  python3 -c '
import json, sys
d = json.load(open(sys.argv[1] + "/settings.json"))
assert d["model"] in ("opus", "opus[1m]"), d["model"]
' "$cfg" && ok "S7: scalar kept" || bad "S7: scalar not kept"
  [ -f "$cfg/engineering-installer.json" ] && ok "S7: marker written" || bad "S7: marker missing"

  run_capture "$cfg" --yes --no-official
  [ "$RC" -eq 0 ] && ok "S7: rerun succeeded" || bad "S7: rerun failed (rc=$RC): $OUT"
  case "$OUT" in *"mode: defaults"*) ok "S7: rerun still defaults" ;; *) bad "S7: rerun mode not defaults"; esac
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S8: rerun auto-mode + variants ---------------------------------------------------------
s08() {
  step "S8: rerun auto-mode keeps edits, no new stamp when unchanged"
  local cfg; cfg="$(new_cfg)"
  install_in "$cfg" --yes --no-official >/dev/null 2>&1 || bad "S8: setup failed"
  python3 -c '
import json, sys
p = sys.argv[1] + "/settings.json"
d = json.load(open(p))
d["model"] = "haiku"
d.setdefault("modelSettings", {})["claude-opus-5"] = {"effortLevel": "high"}
json.dump(d, open(p, "w"), indent=2)
' "$cfg" || bad "S8: setup failed (edit)"
  run_capture "$cfg" --yes --no-official
  case "$OUT" in *"mode: defaults"*) ok "S8: rerun auto-selects defaults" ;; *) bad "S8: rerun mode not defaults: $OUT" ;; esac
  python3 -c '
import json, sys
d = json.load(open(sys.argv[1] + "/settings.json"))
assert d["model"] == "haiku"
assert d["modelSettings"]["claude-opus-5"]["effortLevel"] == "high"
' "$cfg" && ok "S8: edits kept" || bad "S8: edits not kept"
  local before after
  before="$(count_stamps "$cfg")"
  run_capture "$cfg" --yes --no-official
  case "$OUT" in *"settings.json: unchanged"*) ok "S8: second rerun reports settings.json: unchanged" ;; *) bad "S8: second rerun missing 'settings.json: unchanged'" ;; esac
  case "$OUT" in *"rules/engineering-policy.md: unchanged"*) ok "S8: second rerun reports rules/engineering-policy.md: unchanged" ;; *) bad "S8: second rerun missing 'rules/engineering-policy.md: unchanged'" ;; esac
  after="$(count_stamps "$cfg")"
  [ "$before" = "$after" ] && ok "S8: no new stamp on unchanged rerun" || bad "S8: unchanged rerun created a new stamp"
  uninstall_in "$cfg"; rm -rf "$cfg"

  # variant: fresh install with --policy-target claude-md, edit model, rerun -> still defaults
  cfg="$(new_cfg)"
  install_in "$cfg" --yes --no-official --policy-target claude-md >/dev/null 2>&1 || bad "S8 variant (claude-md): setup failed"
  python3 -c '
import json, sys
p = sys.argv[1] + "/settings.json"
d = json.load(open(p)); d["model"] = "haiku"
json.dump(d, open(p, "w"), indent=2)
' "$cfg" || bad "S8 variant (claude-md): setup failed (edit)"
  run_capture "$cfg" --yes --no-official --policy-target claude-md
  case "$OUT" in *"mode: defaults"*) ok "S8 variant (claude-md): rerun still defaults" ;; *) bad "S8 variant (claude-md): rerun not defaults: $OUT" ;; esac
  uninstall_in "$cfg"; rm -rf "$cfg"

  # variant: two consecutive enforce runs -> exactly one stamp
  cfg="$(new_cfg)"
  local rec; rec="$(mktemp)"; cp "$HERE/settings.recommended.json" "$rec"
  ENGINEERING_RECOMMENDED="$rec" install_in "$cfg" --yes --no-official --settings-mode enforce >/dev/null 2>&1 \
    || bad "S8 variant (enforce x2): first run failed"
  local n1; n1="$(count_stamps "$cfg")"
  ENGINEERING_RECOMMENDED="$rec" install_in "$cfg" --yes --no-official --settings-mode enforce >/dev/null 2>&1 \
    || bad "S8 variant (enforce x2): second run failed"
  local n2; n2="$(count_stamps "$cfg")"
  [ "$n1" = "1" ] && [ "$n2" = "1" ] && ok "S8 variant (enforce x2): exactly one stamp" || bad "S8 variant (enforce x2): expected one stamp, got $n1 then $n2"
  rm -f "$rec"
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S9: symlinked settings.json and rules/ dir ---------------------------------------------
s09() {
  step "S9: symlinked settings.json and rules/ dir"
  local cfg; cfg="$(new_cfg)"
  # settings.json's symlink target lives OUTSIDE $CFG (a sibling scratch dir, like a
  # dotfiles checkout) so --restore has to take the "outside $CFG but equal to the
  # recorded target" path. rules/ stays inside $CFG.
  local ext; ext="$(mktemp -d)"
  SCEN9_EXT="$ext"
  local real_settings="$ext/settings.json"
  local real_rules_dir="$cfg/real-rules"
  printf '{}\n' > "$real_settings" || bad "S9: setup failed"
  chmod 0600 "$real_settings" || bad "S9: setup failed"
  mkdir -p "$real_rules_dir" || bad "S9: setup failed"
  ln -s "$real_settings" "$cfg/settings.json" || bad "S9: setup failed"
  ln -s "$real_rules_dir" "$cfg/rules" || bad "S9: setup failed"
  run_capture "$cfg" --yes --no-official
  [ "$RC" -eq 0 ] && ok "S9: install through symlinks succeeded" || bad "S9: install failed (rc=$RC): $OUT"
  [ -L "$cfg/settings.json" ] && [ "$(readlink "$cfg/settings.json")" = "$real_settings" ] && ok "S9: settings.json symlink intact" || bad "S9: settings.json symlink broken"
  [ -L "$cfg/rules" ] && [ "$(readlink "$cfg/rules")" = "$real_rules_dir" ] && ok "S9: rules symlink intact" || bad "S9: rules symlink broken"
  [ -f "$real_rules_dir/engineering-policy.md" ] && ok "S9: rules file written through symlinked dir" || bad "S9: rules file missing in real dir"
  python3 -c '
import os, stat, sys
assert stat.S_IMODE(os.stat(sys.argv[1]).st_mode) == 0o600
' "$real_settings" && ok "S9: settings mode 0600 kept" || bad "S9: settings mode not 0600"
  SCEN9_CFG="$cfg"
  uninstall_in "$cfg"
}

# ---- S10: hard-linked settings.json --------------------------------------------------------
s10() {
  step "S10: hard-linked settings.json refused, then --break-hardlinks, then --restore --break-hardlinks"
  local cfg; cfg="$(new_cfg)"
  install_in "$cfg" --yes --no-official >/dev/null 2>&1 || bad "S10: setup install failed"
  local before after
  before="$(CLAUDE_CONFIG_DIR="$cfg" claude plugin marketplace list --json 2>/dev/null || true)"
  ln "$cfg/settings.json" "$cfg/settings.json.hardlink"
  python3 -c '
import json, sys
p = sys.argv[1] + "/settings.json"
d = json.load(open(p)); d["model"] = "haiku"
json.dump(d, open(p, "w"), indent=2)
' "$cfg"
  run_capture "$cfg" --yes --no-official
  [ "$RC" -eq 5 ] && ok "S10: hard link refused with exit 5" || bad "S10: expected exit 5, got $RC"
  after="$(CLAUDE_CONFIG_DIR="$cfg" claude plugin marketplace list --json 2>/dev/null || true)"
  [ "$before" = "$after" ] && ok "S10: marketplace unchanged before refusal" || bad "S10: marketplace changed despite refusal"
  run_capture "$cfg" --yes --no-official --break-hardlinks
  [ "$RC" -eq 0 ] && ok "S10: --break-hardlinks succeeds" || bad "S10: --break-hardlinks failed (rc=$RC): $OUT"
  run_capture "$cfg" --restore --break-hardlinks
  [ "$RC" -eq 0 ] && ok "S10: --restore --break-hardlinks onto hard-linked target succeeds" || bad "S10: restore --break-hardlinks failed (rc=$RC): $OUT"
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S11: legacy symlinked CLAUDE.md ---------------------------------------------------------
s11() {
  step "S11: legacy symlinked CLAUDE.md migration, decline, restore"
  local cfg; cfg="$(new_cfg)"
  local dotfiles="$cfg/dotfiles"; mkdir -p "$dotfiles"
  cp "$(policy_src)" "$dotfiles/CLAUDE.md" || bad "S11: setup failed"
  ln -s "$dotfiles/CLAUDE.md" "$cfg/CLAUDE.md" || bad "S11: setup failed"
  run_capture "$cfg" --yes --no-official
  [ "$RC" -eq 0 ] && ok "S11: migration run succeeded" || bad "S11: migration run failed (rc=$RC): $OUT"
  [ ! -e "$cfg/CLAUDE.md" ] && ok "S11: symlink removed" || bad "S11: symlink still present"
  cmp -s "$dotfiles/CLAUDE.md" "$(policy_src)" && ok "S11: dotfiles target untouched" || bad "S11: dotfiles target modified"
  [ -f "$cfg/rules/engineering-policy.md" ] && ok "S11: rules file installed" || bad "S11: rules file missing"
  python3 -c '
import glob, json, sys
manifests = glob.glob(sys.argv[1] + "/backups/engineering/*/manifest.json")
assert manifests, "no backup manifest found"
found = False
for m in manifests:
    d = json.load(open(m))
    for f in d["files"]:
        if f["rel"] == "CLAUDE.md":
            found = True
assert found, "CLAUDE.md not recorded in any backup manifest"
' "$cfg" && ok "S11: backup holds CLAUDE.md content" || bad "S11: backup missing CLAUDE.md"

  # decline path: ENGINEERING_NO_PROMPT=1
  local cfg2; cfg2="$(new_cfg)"
  local dotfiles2="$cfg2/dotfiles"; mkdir -p "$dotfiles2"
  cp "$(policy_src)" "$dotfiles2/CLAUDE.md" || bad "S11: setup failed"
  ln -s "$dotfiles2/CLAUDE.md" "$cfg2/CLAUDE.md" || bad "S11: setup failed"
  if OUT="$(ENGINEERING_NO_PROMPT=1 CLAUDE_CONFIG_DIR="$cfg2" "$HERE/install.sh" --no-official 2>&1)"; then RC=0; else RC=$?; fi
  [ "$RC" -eq 0 ] && ok "S11 decline: run succeeded" || bad "S11 decline: run failed (rc=$RC): $OUT"
  [ -L "$cfg2/CLAUDE.md" ] && ok "S11 decline: CLAUDE.md symlink kept" || bad "S11 decline: CLAUDE.md symlink lost"
  [ ! -f "$cfg2/rules/engineering-policy.md" ] && ok "S11 decline: rules file absent" || bad "S11 decline: rules file created despite decline"
  case "$OUT" in *"migrate later: ./install.sh --yes"*) ok "S11 decline: migration command printed" ;; *) bad "S11 decline: migration command missing" ;; esac
  rm -rf "$cfg2"

  if command -v setsid >/dev/null 2>&1; then
    local cfg3; cfg3="$(new_cfg)"
    local dotfiles3="$cfg3/dotfiles"; mkdir -p "$dotfiles3"
    cp "$(policy_src)" "$dotfiles3/CLAUDE.md" || bad "S11: setup failed"
    ln -s "$dotfiles3/CLAUDE.md" "$cfg3/CLAUDE.md" || bad "S11: setup failed"
    if OUT="$(setsid env CLAUDE_CONFIG_DIR="$cfg3" "$HERE/install.sh" --no-official < /dev/null 2>&1)"; then RC=0; else RC=$?; fi
    [ "$RC" -eq 0 ] && [ -L "$cfg3/CLAUDE.md" ] && ok "S11 setsid: no migration without a tty" || bad "S11 setsid: unexpected result (rc=$RC)"
    rm -rf "$cfg3"
  else
    echo "   skip: setsid not available"
  fi

  # --restore, target unmodified: link recreated, target byte-identical. The stamp is named
  # explicitly: each restore takes its own pre-restore backup, which would otherwise become
  # the newest stamp and make a second bare --restore undo the first one instead.
  local s11_stamp; s11_stamp="$(stamp_with "$cfg" CLAUDE.md)"
  [ -n "$s11_stamp" ] && ok "S11: migration stamp records CLAUDE.md" || bad "S11: no stamp records CLAUDE.md"
  run_capture "$cfg" --restore "$s11_stamp"
  [ "$RC" -eq 0 ] && ok "S11 restore: exit 0" || bad "S11 restore: exit $RC: $OUT"
  [ -L "$cfg/CLAUDE.md" ] && ok "S11 restore: symlink recreated" || bad "S11 restore: symlink not recreated"
  cmp -s "$dotfiles/CLAUDE.md" "$(policy_src)" && ok "S11 restore: target byte-identical" || bad "S11 restore: target modified"

  # edit the dotfiles target, remove the link, restore again: link recreated, target NOT overwritten
  rm -f "$cfg/CLAUDE.md"
  printf '\nuser edit after backup\n' >> "$dotfiles/CLAUDE.md" || bad "S11: setup failed"
  run_capture "$cfg" --restore "$s11_stamp"
  [ "$RC" -eq 8 ] && ok "S11 restore (edited target): refused (rc=8)" || bad "S11 restore (edited target): expected rc=8, got $RC"
  # the link is not recreated: a manifest must never create a path whose recorded target no
  # longer holds the backed-up bytes (scripts/safe_write.py restore).
  [ ! -e "$cfg/CLAUDE.md" ] && [ ! -L "$cfg/CLAUDE.md" ] && ok "S11 restore (edited target): symlink not recreated" || bad "S11 restore (edited target): symlink recreated despite refusal"
  case "$OUT" in *"refused CLAUDE.md: recorded symlink target"*"missing or modified"*) ok "S11 restore (edited target): refusal names CLAUDE.md" ;; *) bad "S11 restore (edited target): refusal message missing: $OUT" ;; esac
  grep -q "user edit after backup" "$dotfiles/CLAUDE.md" && ok "S11 restore (edited target): target not overwritten" || bad "S11 restore (edited target): target was overwritten"

  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S12: legacy regular CLAUDE.md with appended user text -----------------------------------
s12() {
  step "S12: legacy regular CLAUDE.md with appended user text"
  local cfg; cfg="$(new_cfg)"
  cat "$(policy_src)" > "$cfg/CLAUDE.md" || bad "S12: setup failed"
  printf '\n\n## my own notes\nkeep this in mind\n' >> "$cfg/CLAUDE.md" || bad "S12: setup failed"
  run_capture "$cfg" --yes --no-official
  [ "$RC" -eq 0 ] && ok "S12: install succeeded" || bad "S12: install failed (rc=$RC): $OUT"
  [ ! -e "$cfg/CLAUDE.md" ] && ok "S12: legacy CLAUDE.md deleted" || bad "S12: legacy CLAUDE.md still present"
  [ -f "$cfg/rules/engineering-policy.md" ] && ok "S12: rules file installed" || bad "S12: rules file missing"
  python3 -c '
import glob, json, sys
manifests = glob.glob(sys.argv[1] + "/backups/engineering/*/manifest.json")
assert any(f["rel"] == "CLAUDE.md" for m in manifests for f in json.load(open(m))["files"])
' "$cfg" && ok "S12: backed up before deletion" || bad "S12: not backed up"
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S13: user CLAUDE.md not ours / user rules file without header --------------------------
s13() {
  step "S13: user CLAUDE.md untouched; user rules file without header refused"
  local cfg; cfg="$(new_cfg)"
  printf '# My own notes\nnot the policy\n' > "$cfg/CLAUDE.md" || bad "S13: setup failed"
  run_capture "$cfg" --yes --no-official
  [ "$RC" -eq 0 ] && ok "S13: install succeeded" || bad "S13: install failed (rc=$RC): $OUT"
  grep -q '^# My own notes$' "$cfg/CLAUDE.md" && ok "S13: user CLAUDE.md untouched" || bad "S13: user CLAUDE.md modified"
  [ -f "$cfg/rules/engineering-policy.md" ] && ok "S13: rules file still installed" || bad "S13: rules file not installed"
  uninstall_in "$cfg"; rm -rf "$cfg"

  cfg="$(new_cfg)"
  mkdir -p "$cfg/rules" || bad "S13: setup failed"
  printf '# my own rule\nnot ours\n' > "$cfg/rules/engineering-policy.md" || bad "S13: setup failed"
  run_capture "$cfg" --yes --no-official
  [ "$RC" -eq 1 ] && ok "S13: user rules file without header refused (rc=1)" || bad "S13: expected rc=1, got $RC"
  case "$OUT" in *"not managed by this installer; refusing to overwrite it"*) ok "S13: refusal message correct" ;; *) bad "S13: refusal message missing" ;; esac
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S14: --policy-target claude-md ----------------------------------------------------------
s14() {
  step "S14: --policy-target claude-md"
  local cfg; cfg="$(new_cfg)"
  run_capture "$cfg" --yes --no-official --policy-target claude-md
  [ "$RC" -eq 0 ] && ok "S14: install succeeded" || bad "S14: install failed (rc=$RC): $OUT"
  cmp -s "$cfg/CLAUDE.md" "$(policy_src)" && ok "S14: CLAUDE.md installed byte-identical" || bad "S14: CLAUDE.md differs"
  [ ! -e "$cfg/rules/engineering-policy.md" ] && ok "S14: rules file not created" || bad "S14: rules file was created"
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S15: --dry-run --------------------------------------------------------------------------
s15() {
  step "S15: --dry-run makes no changes and predicts the marketplace entry accurately"
  local cfg; cfg="$(new_cfg)"
  cp "$HERE/ci/fixtures/settings-seeded.json" "$cfg/settings.json" || bad "S15: setup failed"
  local before_mtime before_hash
  before_mtime="$(stat -c %Y "$cfg/settings.json" 2>/dev/null || stat -f %m "$cfg/settings.json")"
  before_hash="$(sha256_of "$cfg/settings.json")"
  run_capture "$cfg" --dry-run --no-official --settings-mode enforce
  [ "$RC" -eq 0 ] && ok "S15: dry-run exits 0" || bad "S15: dry-run failed (rc=$RC): $OUT"
  local after_mtime after_hash
  after_mtime="$(stat -c %Y "$cfg/settings.json" 2>/dev/null || stat -f %m "$cfg/settings.json")"
  after_hash="$(sha256_of "$cfg/settings.json")"
  [ "$before_mtime" = "$after_mtime" ] && [ "$before_hash" = "$after_hash" ] && ok "S15: settings.json unchanged" || bad "S15: settings.json changed by dry-run"
  [ ! -e "$cfg/CLAUDE.md" ] && [ ! -e "$cfg/rules" ] && [ ! -d "$cfg/backups/engineering" ] && [ ! -e "$cfg/engineering-installer.json" ] && ok "S15: no CLAUDE.md/rules/backups created" || bad "S15: dry-run created files"
  if marketplace_has_engineering "$cfg"; then bad "S15: marketplace was registered by dry-run"; else ok "S15: no marketplace registered"; fi
  case "$OUT" in *"predicted marketplace entry:"*) ok "S15: predicted marketplace entry printed" ;; *) bad "S15: predicted marketplace entry missing" ;; esac
  local predicted; predicted="$(printf '%s\n' "$OUT" | sed -n '/predicted marketplace entry:/{n;p;}')"

  run_capture "$cfg" --yes --no-official --settings-mode enforce
  [ "$RC" -eq 0 ] && ok "S15: real install after dry-run succeeded" || bad "S15: real install failed (rc=$RC): $OUT"
  python3 -c '
import json, sys
predicted = json.loads(sys.argv[1])["source"]
d = json.load(open(sys.argv[2] + "/settings.json"))
actual = d["extraKnownMarketplaces"]["engineering"]["source"]
assert actual == predicted, (predicted, actual)
' "$predicted" "$cfg" && ok "S15: predicted marketplace entry matches actual" || bad "S15: predicted entry does not match actual"
  uninstall_in "$cfg"; rm -rf "$cfg"

  # dry-run over the S9 state: symlinked settings.json (target outside $CFG) and rules/ dir
  local ext; ext="$(mktemp -d)"
  cfg="$(new_cfg)"
  printf '{}\n' > "$ext/settings.json" || bad "S15: setup failed"
  chmod 0600 "$ext/settings.json" || bad "S15: setup failed"
  mkdir -p "$cfg/real-rules" || bad "S15: setup failed"
  ln -s "$ext/settings.json" "$cfg/settings.json" || bad "S15: setup failed"
  ln -s "$cfg/real-rules" "$cfg/rules" || bad "S15: setup failed"
  before_hash="$(sha256_of "$ext/settings.json")"
  run_capture "$cfg" --dry-run --no-official
  [ "$RC" -eq 0 ] && ok "S15 (symlinked state): dry-run exits 0" || bad "S15 (symlinked state): dry-run failed (rc=$RC): $OUT"
  after_hash="$(sha256_of "$ext/settings.json")"
  [ "$before_hash" = "$after_hash" ] && ok "S15 (symlinked state): settings target unchanged" || bad "S15 (symlinked state): settings target changed"
  [ -L "$cfg/settings.json" ] && [ -L "$cfg/rules" ] && ok "S15 (symlinked state): symlinks intact" || bad "S15 (symlinked state): symlinks changed"
  [ ! -e "$cfg/real-rules/engineering-policy.md" ] && [ ! -d "$cfg/backups/engineering" ] && [ ! -e "$cfg/engineering-installer.json" ] && [ ! -e "$cfg/CLAUDE.md" ] \
    && ok "S15 (symlinked state): nothing written" || bad "S15 (symlinked state): dry-run created files"
  if marketplace_has_engineering "$cfg"; then bad "S15 (symlinked state): marketplace registered by dry-run"; else ok "S15 (symlinked state): no marketplace registered"; fi
  rm -rf "$cfg" "$ext"

  # dry-run over the S12 state: legacy CLAUDE.md policy awaiting migration
  cfg="$(new_cfg)"
  cat "$(policy_src)" > "$cfg/CLAUDE.md" || bad "S15: setup failed"
  printf '\n\n## my own notes\nkeep this in mind\n' >> "$cfg/CLAUDE.md" || bad "S15: setup failed"
  before_hash="$(sha256_of "$cfg/CLAUDE.md")"
  run_capture "$cfg" --dry-run --no-official
  [ "$RC" -eq 0 ] && ok "S15 (legacy state): dry-run exits 0" || bad "S15 (legacy state): dry-run failed (rc=$RC): $OUT"
  after_hash="$(sha256_of "$cfg/CLAUDE.md")"
  [ "$before_hash" = "$after_hash" ] && ok "S15 (legacy state): CLAUDE.md unchanged" || bad "S15 (legacy state): CLAUDE.md changed by dry-run"
  [ ! -e "$cfg/rules" ] && [ ! -d "$cfg/backups/engineering" ] && [ ! -e "$cfg/engineering-installer.json" ] && [ ! -e "$cfg/settings.json" ] \
    && ok "S15 (legacy state): nothing written" || bad "S15 (legacy state): dry-run created files"
  case "$OUT" in *"would prompt to migrate legacy CLAUDE.md to rules/engineering-policy.md"*) ok "S15 (legacy state): preview mentions migration" ;; *) bad "S15 (legacy state): preview does not mention migration: $OUT" ;; esac
  if marketplace_has_engineering "$cfg"; then bad "S15 (legacy state): marketplace registered by dry-run"; else ok "S15 (legacy state): no marketplace registered"; fi
  rm -rf "$cfg"
}

# ---- S16: --restore ----------------------------------------------------------------------------
s16() {
  step "S16: --restore byte-identical, mode; tampered manifest refused"
  if [ -n "${SCEN9_CFG:-}" ] && [ -d "$SCEN9_CFG" ]; then
    # The stamp is named explicitly: a restore now takes its own pre-restore backup, so
    # the newest stamp after the first restore is that pre-restore copy, not S9's install.
    local s9_stamp before_stamps after_stamps
    s9_stamp="$(stamp_with "$SCEN9_CFG" settings.json)"
    before_stamps="$(count_stamps "$SCEN9_CFG")"
    [ -n "$s9_stamp" ] && ok "S16: S9 install stamp records settings.json" || bad "S16: no S9 stamp recording settings.json"
    # the symlink is left intact: restore must write through it to the outside-$CFG target
    run_capture "$SCEN9_CFG" --restore "$s9_stamp"
    [ "$RC" -eq 0 ] && ok "S16: restore after S9 exits 0" || bad "S16: restore after S9 failed (rc=$RC): $OUT"
    [ -L "$SCEN9_CFG/settings.json" ] && ok "S16: symlinked settings.json still a symlink after restore" || bad "S16: symlink lost after restore"
    python3 -c '
import hashlib, json, os, sys
cfg, stamp = sys.argv[1], sys.argv[2]
d = json.load(open(os.path.join(cfg, "backups", "engineering", stamp, "manifest.json")))
for f in d["files"]:
    if f["rel"] == "settings.json":
        real = os.path.realpath(cfg + "/settings.json")
        got = hashlib.sha256(open(real, "rb").read()).hexdigest()
        assert got == f["sha256"], (got, f["sha256"])
        break
else:
    raise AssertionError("settings.json not in manifest")
' "$SCEN9_CFG" "$s9_stamp" && ok "S16: restored content matches manifest sha256" || bad "S16: restored content mismatch"

    # (e) the restore saved the pre-restore state first
    after_stamps="$(count_stamps "$SCEN9_CFG")"
    case "$OUT" in *"pre-restore backup:"*) ok "S16: pre-restore backup line printed" ;; *) bad "S16: pre-restore backup line missing: $OUT" ;; esac
    [ "$after_stamps" -gt "$before_stamps" ] && ok "S16: restore created a new stamp ($before_stamps -> $after_stamps)" || bad "S16: restore created no pre-restore stamp"

    # variant: the link is gone and the recorded (outside-$CFG) target was edited
    if [ -n "${SCEN9_EXT:-}" ] && [ -f "$SCEN9_EXT/settings.json" ]; then
      rm -f "$SCEN9_CFG/settings.json"
      printf '\n' >> "$SCEN9_EXT/settings.json" || bad "S16: setup failed"
      run_capture "$SCEN9_CFG" --restore "$s9_stamp"
      [ "$RC" -eq 8 ] && ok "S16: edited outside-\$CFG symlink target refused (rc=8)" || bad "S16: expected rc=8 for edited symlink target, got $RC: $OUT"
      case "$OUT" in
        *"refused settings.json: recorded symlink target"*"missing or modified"*) ok "S16: refusal names the recorded symlink target" ;;
        *) bad "S16: refusal message missing: $OUT" ;;
      esac
      [ ! -e "$SCEN9_CFG/settings.json" ] && ok "S16: refused restore did not recreate the link" || bad "S16: refused restore recreated the link"
      rm -rf "$SCEN9_EXT"
    else
      bad "S16: S9 external symlink target unavailable"
    fi
    rm -rf "$SCEN9_CFG"
  else
    echo "   skip: S9 config unavailable"
  fi

  local cfg; cfg="$(new_cfg)"
  install_in "$cfg" --yes --no-official >/dev/null 2>&1 || bad "S16: setup install failed"
  python3 -c '
import json, sys
p = sys.argv[1] + "/settings.json"
d = json.load(open(p)); d["model"] = "haiku"
json.dump(d, open(p, "w"), indent=2)
' "$cfg" || bad "S16: setup failed (edit)"
  install_in "$cfg" --yes --no-official >/dev/null 2>&1 || bad "S16: setup rerun failed"
  local manifest
  manifest="$(python3 -c '
import glob, os, sys
dirs = sorted(d for d in glob.glob(os.path.join(sys.argv[1], "backups", "engineering", "*")) if os.path.isdir(d))
print(os.path.join(dirs[-1], "manifest.json") if dirs else "")
' "$cfg")"
  if [ -f "$manifest" ]; then
    python3 -c '
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["files"][0]["rel"] = "../evil.json"
json.dump(d, open(p, "w"))
' "$manifest"
    run_capture "$cfg" --restore
    case "$OUT" in *"traversal"*|*".."*) ok "S16: '..' manifest path refused" ;; *) bad "S16: '..' manifest path not refused: $OUT" ;; esac
    [ "$RC" -eq 8 ] && ok "S16: '..' refusal exit 8" || bad "S16: '..' refusal expected exit 8, got $RC"

    python3 -c '
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["files"][0]["rel"] = "/etc/passwd"
json.dump(d, open(p, "w"))
' "$manifest"
    run_capture "$cfg" --restore
    case "$OUT" in *"absolute"*) ok "S16: absolute manifest path refused" ;; *) bad "S16: absolute manifest path not refused: $OUT" ;; esac

    python3 -c '
import json, sys
p = sys.argv[1]
d = json.load(open(p))
d["files"][0]["rel"] = "settings.json"
d["files"][0]["sha256"] = "0" * 64
json.dump(d, open(p, "w"))
' "$manifest"
    run_capture "$cfg" --restore
    case "$OUT" in *"sha256 mismatch"*) ok "S16: tampered sha256 refused" ;; *) bad "S16: tampered sha256 not refused: $OUT" ;; esac
  else
    bad "S16: no backup manifest to tamper with"
  fi
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S17: prune keeps newest 5 ----------------------------------------------------------------
s17() {
  step "S17: prune keeps newest 5 stamps"
  local cfg; cfg="$(new_cfg)"
  local recdir; recdir="$(mktemp -d)"
  local i
  for i in 1 2 3 4 5 6; do
    python3 -c '
import json, sys
d = json.load(open(sys.argv[1]))
d["model"] = "fable-variant-" + sys.argv[2]
json.dump(d, open(sys.argv[3], "w"), indent=2)
' "$HERE/settings.recommended.json" "$i" "$recdir/rec-$i.json"
    ENGINEERING_RECOMMENDED="$recdir/rec-$i.json" install_in "$cfg" --yes --no-official --settings-mode enforce >/dev/null 2>&1 \
      || bad "S17: install run $i failed"
  done
  local n; n="$(find "$cfg/backups/engineering" -maxdepth 1 -mindepth 1 -type d 2>/dev/null | wc -l | tr -d ' ')"
  [ "$n" = "5" ] && ok "S17: exactly 5 stamps remain" || bad "S17: expected 5 stamps, found $n"
  rm -rf "$recdir"
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S18: --no-official / --purge-official -----------------------------------------------------
s18() {
  step "S18: --no-official preserves; --purge-official removes (explicit false kept)"
  local seed cfg
  seed='{"enabledPlugins":{"superpowers@claude-plugins-official":true,"context7@claude-plugins-official":false},"extraKnownMarketplaces":{"claude-plugins-official":{"source":{"source":"github","repo":"anthropics/claude-plugins-official"}}}}'

  cfg="$(new_cfg)"
  printf '%s' "$seed" > "$cfg/settings.json" || bad "S18: setup failed"
  run_capture "$cfg" --yes --no-official
  [ "$RC" -eq 0 ] && ok "S18 --no-official: install succeeded" || bad "S18 --no-official: install failed (rc=$RC): $OUT"
  python3 -c '
import json, sys
d = json.load(open(sys.argv[1] + "/settings.json"))
assert d["enabledPlugins"]["superpowers@claude-plugins-official"] is True
assert d["enabledPlugins"]["context7@claude-plugins-official"] is False
assert "claude-plugins-official" in d["extraKnownMarketplaces"]
' "$cfg" && ok "S18 --no-official: official entries preserved" || bad "S18 --no-official: official entries lost"
  uninstall_in "$cfg"; rm -rf "$cfg"

  cfg="$(new_cfg)"
  printf '%s' "$seed" > "$cfg/settings.json" || bad "S18: setup failed"
  run_capture "$cfg" --yes --purge-official
  [ "$RC" -eq 0 ] && ok "S18 --purge-official: install succeeded" || bad "S18 --purge-official: install failed (rc=$RC): $OUT"
  python3 -c '
import json, sys
d = json.load(open(sys.argv[1] + "/settings.json"))
assert "superpowers@claude-plugins-official" not in d["enabledPlugins"]
assert d["enabledPlugins"]["context7@claude-plugins-official"] is False
assert "claude-plugins-official" not in d.get("extraKnownMarketplaces", {})
' "$cfg" && ok "S18 --purge-official: official entries removed, explicit false kept" || bad "S18 --purge-official: purge behaviour wrong"
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S19: shims (claude-old, claude-fail-install, claude-old-plugin) --------------------------
s19() {
  step "S19a: claude-old (< 2.1.267) exits before any write"
  local cfg bindir; cfg="$(new_cfg)"; bindir="$(shim_bin "$HERE/ci/shims/claude-old" claude)"
  if OUT="$(PATH="$bindir:$PATH" CLAUDE_CONFIG_DIR="$cfg" "$HERE/install.sh" --yes --no-official 2>&1)"; then RC=0; else RC=$?; fi
  [ "$RC" -ne 0 ] && ok "S19a: rejected old CLI (rc=$RC)" || bad "S19a: old CLI accepted"
  [ ! -e "$cfg/settings.json" ] && [ ! -e "$cfg/CLAUDE.md" ] && [ ! -e "$cfg/rules" ] && ok "S19a: nothing written" || bad "S19a: something was written"
  case "$OUT" in *"2.1.267"*) ok "S19a: message names required version" ;; *) bad "S19a: message missing required version"; esac
  rm -rf "$cfg" "$bindir"

  step "S19b: claude-fail-install fails plugin install, exit 1, no installer writes"
  cfg="$(new_cfg)"; bindir="$(shim_bin "$HERE/ci/shims/claude-fail-install" claude)"
  # Reproduce the state install.sh reaches just before `plugin install`: the marketplace is
  # already registered (which is what creates settings.json), so settings.json can be hashed
  # before the failing run and compared after it. --dry-run would register nothing.
  CLAUDE_CONFIG_DIR="$cfg" claude plugin marketplace add "$HERE" >/dev/null 2>&1 || bad "S19b: setup marketplace add failed"
  local pre_hash post_hash
  if [ -f "$cfg/settings.json" ]; then pre_hash="$(sha256_of "$cfg/settings.json")"; else pre_hash="absent"; fi
  if OUT="$(PATH="$bindir:$PATH" CLAUDE_CONFIG_DIR="$cfg" "$HERE/install.sh" --yes --no-official 2>&1)"; then RC=0; else RC=$?; fi
  [ "$RC" -eq 1 ] && ok "S19b: exit 1" || bad "S19b: expected exit 1, got $RC"
  if [ -f "$cfg/settings.json" ]; then post_hash="$(sha256_of "$cfg/settings.json")"; else post_hash="absent"; fi
  [ "$pre_hash" = "$post_hash" ] && ok "S19b: settings.json byte-identical across the failed install" || bad "S19b: settings.json changed by the failed install"
  [ ! -f "$cfg/engineering-installer.json" ] && ok "S19b: no marker" || bad "S19b: marker written"
  [ ! -e "$cfg/CLAUDE.md" ] && [ ! -e "$cfg/rules/engineering-policy.md" ] && ok "S19b: no policy file" || bad "S19b: policy file written"
  [ ! -d "$cfg/backups/engineering" ] && ok "S19b: no backup stamp" || bad "S19b: backup stamp created"
  PATH="$bindir:$PATH" CLAUDE_CONFIG_DIR="$cfg" claude plugin uninstall engineering@engineering >/dev/null 2>&1 || true
  rm -rf "$cfg" "$bindir"

  step "S19c: claude-old-plugin falls back to --policy-target claude-md"
  cfg="$(new_cfg)"; bindir="$(shim_bin "$HERE/ci/shims/claude-old-plugin" claude)"
  mkdir -p "$cfg/plugins/cache/engineering/engineering/0.0.0-legacy/hooks" || bad "S19: setup failed"
  printf '#!/usr/bin/env bash\ncat "$(dirname "$0")/../context/CLAUDE.md"\n' > "$cfg/plugins/cache/engineering/engineering/0.0.0-legacy/hooks/session-start.sh" || bad "S19: setup failed"
  if OUT="$(PATH="$bindir:$PATH" CLAUDE_CONFIG_DIR="$cfg" "$HERE/install.sh" --yes --no-official 2>&1)"; then RC=0; else RC=$?; fi
  [ "$RC" -eq 0 ] && ok "S19c: install succeeded" || bad "S19c: install failed (rc=$RC): $OUT"
  [ ! -f "$cfg/rules/engineering-policy.md" ] && ok "S19c: no rules file" || bad "S19c: rules file was created"
  [ -f "$cfg/CLAUDE.md" ] && ok "S19c: policy fell back to CLAUDE.md" || bad "S19c: CLAUDE.md not written"
  case "$OUT" in *"does not support the rules-file policy; keeping the policy in CLAUDE.md"*) ok "S19c: fallback message correct" ;; *) bad "S19c: fallback message missing: $OUT" ;; esac
  PATH="$bindir:$PATH" CLAUDE_CONFIG_DIR="$cfg" claude plugin uninstall engineering@engineering >/dev/null 2>&1 || true
  rm -rf "$cfg" "$bindir"
}

# ---- S22: python3 < 3.8 precondition -----------------------------------------------------------
s22() {
  step "S22: python3 < 3.8 exits before any write"
  local cfg bindir; cfg="$(new_cfg)"; bindir="$(shim_bin "$HERE/ci/shims/python3-old" python3)"
  if OUT="$(PATH="$bindir:$PATH" CLAUDE_CONFIG_DIR="$cfg" "$HERE/install.sh" --yes --no-official 2>&1)"; then RC=0; else RC=$?; fi
  [ "$RC" -ne 0 ] && ok "S22: rejected old python3 (rc=$RC)" || bad "S22: old python3 accepted"
  [ ! -e "$cfg/settings.json" ] && [ ! -e "$cfg/CLAUDE.md" ] && [ ! -e "$cfg/rules" ] && ok "S22: nothing written" || bad "S22: something was written"
  case "$OUT" in *">= 3.8"*) ok "S22: message names required python version" ;; *) bad "S22: message missing required python version: $OUT" ;; esac
  rm -rf "$cfg" "$bindir"
}

# ---- S23: foreign 'engineering' marketplace binding is refused ---------------------------------
s23() {
  step "S23: an 'engineering' marketplace bound elsewhere is refused"
  local cfg; cfg="$(new_cfg)"
  CLAUDE_CONFIG_DIR="$cfg" claude plugin marketplace add "$HERE" >/dev/null 2>&1 || bad "S23: setup marketplace add failed"
  run_capture "$cfg" --source ahueb/engineering --no-official --yes
  [ "$RC" -eq 1 ] && ok "S23: foreign binding refused (rc=1)" || bad "S23: expected exit 1, got $RC: $OUT"
  case "$OUT" in *"is registered elsewhere, not 'ahueb/engineering'"*) ok "S23: message says the binding is not the requested source" ;; *) bad "S23: message does not name the requested source: $OUT" ;; esac
  case "$OUT" in *"run 'claude plugin marketplace remove engineering'"*) ok "S23: message gives the rebind command" ;; *) bad "S23: message missing the rebind command: $OUT" ;; esac
  [ ! -e "$cfg/rules/engineering-policy.md" ] && [ ! -e "$cfg/CLAUDE.md" ] && [ ! -e "$cfg/engineering-installer.json" ] && ok "S23: nothing installed" || bad "S23: installer wrote despite refusal"
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S24: two backups in one run land in one stamp/manifest -------------------------------------
s24() {
  step "S24: settings.json and CLAUDE.md backed up in one run share one manifest"
  local cfg; cfg="$(new_cfg)"
  cp "$HERE/ci/fixtures/settings-seeded.json" "$cfg/settings.json" || bad "S24: setup failed (settings)"
  cat "$(policy_src)" > "$cfg/CLAUDE.md" || bad "S24: setup failed (policy)"
  run_capture "$cfg" --yes --no-official
  [ "$RC" -eq 0 ] && ok "S24: install succeeded" || bad "S24: install failed (rc=$RC): $OUT"
  local n; n="$(count_stamps "$cfg")"
  [ "$n" = "1" ] && ok "S24: exactly one stamp for the run" || bad "S24: expected 1 stamp, found $n"
  python3 -c '
import glob, json, os, sys
cfg = sys.argv[1]
manifests = glob.glob(os.path.join(cfg, "backups", "engineering", "*", "manifest.json"))
assert len(manifests) == 1, manifests
rels = sorted(f["rel"] for f in json.load(open(manifests[0]))["files"])
assert rels == ["CLAUDE.md", "settings.json"], rels
' "$cfg" && ok "S24: single manifest lists settings.json and CLAUDE.md" || bad "S24: manifest does not list both files"
  [ -f "$cfg/rules/engineering-policy.md" ] && [ ! -e "$cfg/CLAUDE.md" ] && ok "S24: migrated to the rules file" || bad "S24: migration did not happen"
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S25: installed-version probe ignores a distractor plugin id --------------------------------
s25() {
  step "S25: installed-version probe ignores a distractor plugin entry"
  local cfg bindir; cfg="$(new_cfg)"; bindir="$(shim_bin "$HERE/ci/shims/claude-distractor" claude)"
  if OUT="$(PATH="$bindir:$PATH" CLAUDE_CONFIG_DIR="$cfg" "$HERE/install.sh" --yes --no-official 2>&1)"; then RC=0; else RC=$?; fi
  [ "$RC" -eq 0 ] && ok "S25: install succeeded" || bad "S25: install failed (rc=$RC): $OUT"
  [ -f "$cfg/rules/engineering-policy.md" ] && ok "S25: rules policy installed" || bad "S25: rules file missing (probe matched the distractor?)"
  [ ! -e "$cfg/CLAUDE.md" ] && ok "S25: no CLAUDE.md fallback" || bad "S25: fell back to CLAUDE.md"
  case "$OUT" in
    *"does not support the rules-file policy"*|*"could not determine the installed engineering plugin version"*)
      bad "S25: version probe was confused by the distractor: $OUT" ;;
    *) ok "S25: no capability-gate fallback message" ;;
  esac
  PATH="$bindir:$PATH" CLAUDE_CONFIG_DIR="$cfg" claude plugin uninstall engineering@engineering >/dev/null 2>&1 || true
  rm -rf "$cfg" "$bindir"
}

# ---- S26: cache fallback picks the highest semver, not the highest string -----------------------
s26() {
  step "S26: cache-directory fallback picks 0.10.0 over 0.9.0"
  local cfg bindir; cfg="$(new_cfg)"; bindir="$(shim_bin "$HERE/ci/shims/claude-empty-list" claude)"
  local base="$cfg/plugins/cache/engineering/engineering"
  local v
  for v in 0.9.0 0.10.0; do
    mkdir -p "$base/$v/.claude-plugin" "$base/$v/hooks" || bad "S26: setup failed"
    printf '{"name":"engineering","version":"%s"}\n' "$v" > "$base/$v/.claude-plugin/plugin.json" || bad "S26: setup failed"
  done
  # only the higher version's hook knows about the rules file
  printf '#!/usr/bin/env bash\n# legacy hook: CLAUDE.md only\n' > "$base/0.9.0/hooks/session-start.sh" || bad "S26: setup failed"
  printf '#!/usr/bin/env bash\n# reads rules/engineering-policy.md\n' > "$base/0.10.0/hooks/session-start.sh" || bad "S26: setup failed"
  if OUT="$(PATH="$bindir:$PATH" CLAUDE_CONFIG_DIR="$cfg" "$HERE/install.sh" --yes --no-official 2>&1)"; then RC=0; else RC=$?; fi
  [ "$RC" -eq 0 ] && ok "S26: install succeeded" || bad "S26: install failed (rc=$RC): $OUT"
  [ -f "$cfg/rules/engineering-policy.md" ] && ok "S26: policy target stayed rules" || bad "S26: rules file missing (0.9.0 chosen?)"
  [ ! -e "$cfg/CLAUDE.md" ] && ok "S26: no CLAUDE.md fallback" || bad "S26: fell back to CLAUDE.md"
  case "$OUT" in *"does not support the rules-file policy"*) bad "S26: capability gate used the lower version: $OUT" ;; *) ok "S26: no capability-gate fallback message" ;; esac
  python3 -c '
import json, sys
d = json.load(open(sys.argv[1] + "/engineering-installer.json"))
assert d["policy_target"] == "rules", d
' "$cfg" && ok "S26: marker records policy target rules" || bad "S26: marker policy target wrong"
  PATH="$bindir:$PATH" CLAUDE_CONFIG_DIR="$cfg" claude plugin uninstall engineering@engineering >/dev/null 2>&1 || true
  rm -rf "$cfg" "$bindir"
}

# ---- S27: --dry-run --restore is a usage error --------------------------------------------------
s27() {
  step "S27: --dry-run --restore exits 2"
  local cfg; cfg="$(new_cfg)"
  run_capture "$cfg" --dry-run --restore
  [ "$RC" -eq 2 ] && ok "S27: --dry-run --restore exits 2" || bad "S27: expected exit 2, got $RC: $OUT"
  case "$OUT" in *"--dry-run cannot be combined with --restore"*) ok "S27: message explains the conflict" ;; *) bad "S27: message missing: $OUT" ;; esac
  run_capture "$cfg" --restore --dry-run
  [ "$RC" -eq 2 ] && ok "S27: --restore --dry-run exits 2 too" || bad "S27: expected exit 2 for the reversed order, got $RC: $OUT"
  rm -rf "$cfg"
}

# ---- S28: dangling settings.json symlink --------------------------------------------------------
s28() {
  step "S28: dangling settings.json symlink refused, then --create-through-dangling"
  local cfg ext; cfg="$(new_cfg)"; ext="$(mktemp -d)"
  ln -s "$ext/settings.json" "$cfg/settings.json" || bad "S28: setup failed"
  run_capture "$cfg" --yes --no-official
  [ "$RC" -eq 4 ] && ok "S28: dangling symlink refused (rc=4)" || bad "S28: expected exit 4, got $RC: $OUT"
  case "$OUT" in *"settings.json is a dangling symlink; check out the dotfiles target or pass --create-through-dangling"*) ok "S28: refusal message correct" ;; *) bad "S28: refusal message missing: $OUT" ;; esac
  [ ! -e "$ext/settings.json" ] && ok "S28: target not created by the refused run" || bad "S28: target created despite refusal"
  [ ! -e "$cfg/rules/engineering-policy.md" ] && [ ! -e "$cfg/engineering-installer.json" ] && ok "S28: nothing installed" || bad "S28: installer wrote despite refusal"

  run_capture "$cfg" --yes --no-official --create-through-dangling
  [ "$RC" -eq 0 ] && ok "S28: --create-through-dangling succeeds" || bad "S28: --create-through-dangling failed (rc=$RC): $OUT"
  [ -L "$cfg/settings.json" ] && ok "S28: symlink kept" || bad "S28: symlink replaced by a regular file"
  [ -f "$ext/settings.json" ] && ok "S28: link target created" || bad "S28: link target missing"
  python3 -c '
import json, sys
d = json.load(open(sys.argv[1]))
assert d["enabledPlugins"]["engineering@engineering"] is True, d.get("enabledPlugins")
' "$ext/settings.json" && ok "S28: merged settings written through the link" || bad "S28: settings not merged into the target"
  uninstall_in "$cfg"; rm -rf "$cfg" "$ext"
}

# ---- S29: --policy-target claude-md with the rules file already installed -----------------------
s29() {
  step "S29: --policy-target claude-md does not duplicate an installed rules policy"
  local cfg; cfg="$(new_cfg)"
  install_in "$cfg" --yes --no-official >/dev/null 2>&1 || bad "S29: setup install failed"
  [ -f "$cfg/rules/engineering-policy.md" ] && ok "S29: setup installed the rules policy" || bad "S29: setup did not install the rules policy"
  run_capture "$cfg" --yes --no-official --policy-target claude-md
  [ "$RC" -eq 0 ] && ok "S29: run succeeded" || bad "S29: run failed (rc=$RC): $OUT"
  case "$OUT" in *"rules/engineering-policy.md is already installed; not writing CLAUDE.md"*) ok "S29: message explains the skip" ;; *) bad "S29: message missing: $OUT" ;; esac
  [ ! -e "$cfg/CLAUDE.md" ] && ok "S29: no CLAUDE.md written" || bad "S29: CLAUDE.md was written"
  [ -f "$cfg/rules/engineering-policy.md" ] && ok "S29: rules policy still installed" || bad "S29: rules policy removed"
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S30: interactive migration prompt, accepted on a pty ---------------------------------------
s30() {
  step "S30: interactive migration prompt accepted on a pty"
  if ! python3 -c 'import pty' >/dev/null 2>&1; then
    echo "   skip: pty unavailable"
    return
  fi
  local cfg; cfg="$(new_cfg)"
  cat "$(policy_src)" > "$cfg/CLAUDE.md" || bad "S30: setup failed"
  # no --yes and no ENGINEERING_NO_PROMPT: install.sh opens /dev/tty and reads the answer
  if OUT="$(CLAUDE_CONFIG_DIR="$cfg" python3 "$HERE/ci/pty_run.py" '[y/N]' 'y
' "$HERE/install.sh" --no-official 2>&1)"; then RC=0; else RC=$?; fi
  [ "$RC" -eq 0 ] && ok "S30: install succeeded under a pty" || bad "S30: install failed (rc=$RC): $OUT"
  case "$OUT" in *"Migrate the existing"*) ok "S30: prompt was shown" ;; *) bad "S30: prompt was not shown: $OUT" ;; esac
  case "$OUT" in *"migrated legacy CLAUDE.md policy to rules/engineering-policy.md"*) ok "S30: migration confirmed" ;; *) bad "S30: migration message missing: $OUT" ;; esac
  [ -f "$cfg/rules/engineering-policy.md" ] && ok "S30: rules policy installed" || bad "S30: rules policy missing"
  [ ! -e "$cfg/CLAUDE.md" ] && ok "S30: legacy CLAUDE.md removed" || bad "S30: legacy CLAUDE.md still present"
  uninstall_in "$cfg"; rm -rf "$cfg"
}

# ---- S20 (--full): default official-plugin path ------------------------------------------------
s20() {
  step "S20 (--full): default path (no --no-official) installs superpowers"
  if ! network_available; then
    if [ "${CI_ALLOW_SKIP:-0}" = "1" ]; then echo "   skip: no network for S20"; FULL_RAN="$FULL_RAN S20(skipped)"; return; fi
    bad "S20: no network available and CI_ALLOW_SKIP is not set"; return
  fi
  local cfg; cfg="$(new_cfg)"
  run_capture "$cfg" --yes
  if [ "$RC" -eq 0 ]; then
    python3 -c '
import json, sys
d = json.load(open(sys.argv[1] + "/settings.json"))
assert d["enabledPlugins"].get("superpowers@claude-plugins-official") is True
assert "claude-plugins-official" in d.get("extraKnownMarketplaces", {})
' "$cfg" && ok "S20: superpowers installed via official marketplace" || bad "S20: superpowers not installed"
  else
    bad "S20: install failed (rc=$RC): $OUT"
  fi
  CLAUDE_CONFIG_DIR="$cfg" claude plugin uninstall superpowers@claude-plugins-official >/dev/null 2>&1 || true
  uninstall_in "$cfg"; rm -rf "$cfg"
  FULL_RAN="$FULL_RAN S20"
}

# ---- S21 (--full): rules-file load via claude -p ------------------------------------------------
s21() {
  step "S21 (--full): rules-file load via claude -p --model haiku"
  local creds="$HOME/.claude/.credentials.json"
  if [ ! -f "$creds" ]; then
    if [ "${CI_ALLOW_SKIP:-0}" = "1" ]; then echo "   skip: no credentials at $creds"; FULL_RAN="$FULL_RAN S21(skipped)"; return; fi
    bad "S21: no credentials at $creds and CI_ALLOW_SKIP is not set"; return
  fi
  if ! network_available; then
    if [ "${CI_ALLOW_SKIP:-0}" = "1" ]; then echo "   skip: no network for S21"; FULL_RAN="$FULL_RAN S21(skipped)"; return; fi
    bad "S21: no network available and CI_ALLOW_SKIP is not set"; return
  fi
  local cfg; cfg="$(new_cfg)"
  # the copied credentials must not survive this function, including on an early exit
  S21_CFG="$cfg"
  trap 'rm -rf "${S21_CFG:-}"' EXIT
  mkdir -p "$cfg/rules" || bad "S21: setup failed"
  cp "$creds" "$cfg/.credentials.json" || bad "S21: setup failed"
  local sentinel="CI_SENTINEL_$$_${RANDOM:-0}"
  printf '# ci sentinel rule\nWhenever you respond, include this exact literal token somewhere in your reply: %s\n' "$sentinel" > "$cfg/rules/ci-sentinel.md" || bad "S21: setup failed"
  local out
  if out="$(CLAUDE_CONFIG_DIR="$cfg" claude -p --model haiku "reply with a short greeting" 2>&1)"; then
    case "$out" in
      *"$sentinel"*) ok "S21: sentinel from rules file present in reply" ;;
      *) bad "S21: sentinel not found in claude -p output" ;;
    esac
  else
    bad "S21: claude -p failed: $out"
  fi
  rm -rf "$cfg"
  trap - EXIT
  S21_CFG=""
  FULL_RAN="$FULL_RAN S21"
}

if [ "$TIER" != "quick" ]; then
  s01; s02; s03; s04; s05; s06; s07; s08; s09; s10
  s11; s12; s13; s14; s15; s16; s17; s18; s19; s22
  s23; s24; s25; s26; s27; s28; s29; s30
fi
if [ "$TIER" = "full" ]; then
  s20; s21
fi

echo
if [ "$TIER" = "full" ]; then
  echo "full-tier scenarios run:${FULL_RAN:- none}"
fi
if [ "$fail" = 0 ]; then echo "CI: all checks passed"; else echo "CI: FAILED" >&2; exit 1; fi
