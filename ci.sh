#!/usr/bin/env bash
# Local CI gate. Runs before every push (see .githooks/pre-push) and inside release.sh.
# No GitHub Actions or server-side hooks are used: this script is the only gate.
#
#   ./ci.sh            run every check
#   ./ci.sh --quick    skip the scratch-directory behavioural checks (static + tests only)
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN="$HERE/plugins/engineering"
PRR="$PLUGIN/skills/production-readiness-review"
QUICK=0
[ "${1:-}" = "--quick" ] && QUICK=1

fail=0
step() { printf '\n== %s\n' "$1"; }
ok() { echo "   ok: $1"; }
bad() { echo "   FAIL: $1" >&2; fail=1; }

for tool in bash python3 claude; do
  command -v "$tool" >/dev/null || { echo "$tool is required" >&2; exit 1; }
done

step "shell syntax and lint"
bash -n "$HERE/install.sh" "$HERE/release.sh" "$HERE/ci.sh" "$PLUGIN/hooks/session-start.sh" && ok "bash -n" || bad "bash -n"
if command -v shellcheck >/dev/null; then
  shellcheck -S warning "$HERE/install.sh" "$HERE/release.sh" "$HERE/ci.sh" "$PLUGIN/hooks/session-start.sh" && ok "shellcheck" || bad "shellcheck"
else
  echo "   skip: shellcheck not installed"
fi

step "plugin and marketplace manifests"
claude plugin validate "$PLUGIN" --strict >/dev/null && ok "plugin validate --strict" || bad "plugin validate --strict"
claude plugin validate "$HERE" --strict >/dev/null && ok "marketplace validate --strict" || bad "marketplace validate --strict"
python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$PLUGIN/hooks/hooks.json" && ok "hooks.json is JSON" || bad "hooks.json is JSON"
python3 -c "import json,sys; json.load(open(sys.argv[1]))" "$HERE/settings.recommended.json" && ok "settings.recommended.json is JSON" || bad "settings.recommended.json is JSON"

step "probe"
python3 -W error -m py_compile "$PRR/scripts/repo_probe.py" && ok "py_compile" || bad "py_compile"
python3 -m unittest "$PRR/tests/test_repo_probe.py" >/dev/null 2>&1 && ok "unit tests" || bad "unit tests"
rm -rf "$PRR/tests/__pycache__" "$PRR/scripts/__pycache__"

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

step "hook contract"
tmp="$(mktemp -d)"
printf '# Agent operating policy\n' > "$tmp/CLAUDE.md"
[ -z "$(CLAUDE_CONFIG_DIR="$tmp" bash "$PLUGIN/hooks/session-start.sh")" ] && ok "silent when policy installed" || bad "hook not silent when policy installed"
printf '# other\n' > "$tmp/CLAUDE.md"
[ "$(CLAUDE_CONFIG_DIR="$tmp" bash "$PLUGIN/hooks/session-start.sh" | head -1)" = "# Agent operating policy" ] && ok "injects when policy absent" || bad "hook does not inject"
rm -rf "$tmp"

if [ "$QUICK" = 0 ]; then
  step "installer behaviour (scratch config dir, --no-official)"
  scratch="$(mktemp -d)"
  cfg="$scratch/cfg"; mkdir -p "$cfg"
  printf '{not json' > "$cfg/settings.json"
  if (cd "$HERE" && CLAUDE_CONFIG_DIR="$cfg" ./install.sh --no-official >/dev/null 2>&1); then bad "install accepted invalid settings.json"; else ok "invalid settings.json rejected"; fi
  [ ! -f "$cfg/CLAUDE.md" ] && ok "nothing written after rejection" || bad "CLAUDE.md written despite rejection"
  rm -f "$cfg/settings.json"
  (cd "$HERE" && CLAUDE_CONFIG_DIR="$cfg" ./install.sh --no-official >/dev/null 2>&1) && ok "fresh install" || bad "fresh install"
  cmp -s "$cfg/CLAUDE.md" "$PLUGIN/context/CLAUDE.md" && ok "policy installed byte-identical" || bad "policy differs"
  before="$(find "$cfg" -maxdepth 1 -name 'settings.json.bak-*' | wc -l)"
  (cd "$HERE" && CLAUDE_CONFIG_DIR="$cfg" ./install.sh --no-official >/dev/null 2>&1) && ok "identical rerun" || bad "identical rerun"
  after="$(find "$cfg" -maxdepth 1 -name 'settings.json.bak-*' | wc -l)"
  [ "$before" = "$after" ] && ok "rerun created no new backup" || bad "rerun created a backup"
  python3 - "$cfg/settings.json" <<'PY' && ok "merged settings shape" || bad "merged settings shape"
import json, sys
d = json.load(open(sys.argv[1]))
assert d["enabledPlugins"].get("engineering@engineering") is True
assert not any(k.endswith("@claude-plugins-official") for k in d["enabledPlugins"])
assert "engineering" in d["extraKnownMarketplaces"]
PY
  CLAUDE_CONFIG_DIR="$cfg" claude plugin uninstall engineering@engineering >/dev/null 2>&1 || true
  rm -rf "$scratch"
fi

echo
if [ "$fail" = 0 ]; then echo "CI: all checks passed"; else echo "CI: FAILED" >&2; exit 1; fi
