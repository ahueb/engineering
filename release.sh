#!/usr/bin/env bash
# Bump the plugin version, commit, and refresh the locally installed copy.
# Claude Code installs plugins into a version-keyed cache and skips `plugin update`
# when the version is unchanged, so edits are invisible until this runs.
#
#   ./release.sh patch|minor|major     bump semver, commit, update local install
#   ./release.sh 2.3.0                 set an explicit version
#   ./release.sh --no-commit patch     bump and update only
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="$HERE/plugins/engineering/.claude-plugin/plugin.json"
COMMIT=1
[ "${1:-}" = "--no-commit" ] && { COMMIT=0; shift; }
KIND="${1:-patch}"

CUR="$(python3 -c "import json;print(json.load(open('$MANIFEST'))['version'])")"
case "$KIND" in
  patch|minor|major)
    NEW="$(python3 - "$CUR" "$KIND" <<'PY'
import sys
maj, mi, pa = (int(x) for x in sys.argv[1].split("."))
k = sys.argv[2]
print({"major": f"{maj+1}.0.0", "minor": f"{maj}.{mi+1}.0", "patch": f"{maj}.{mi}.{pa+1}"}[k])
PY
)" ;;
  *) NEW="$KIND"; [[ "$NEW" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "not a semver version: $NEW" >&2; exit 2; } ;;
esac

python3 - "$MANIFEST" "$NEW" <<'PY'
import json, sys
p, v = sys.argv[1], sys.argv[2]
d = json.load(open(p)); d["version"] = v
with open(p, "w") as f: json.dump(d, f, indent=2); f.write("\n")
PY
echo "version: $CUR -> $NEW"
claude plugin validate "$HERE/plugins/engineering" --strict >/dev/null && echo "validation passed"

if [ "$COMMIT" = 1 ] && git -C "$HERE" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "$HERE" add -A
  git -C "$HERE" commit -qm "Release engineering $NEW" && echo "committed"
fi

if claude plugin list 2>/dev/null | grep -q "engineering@engineering"; then
  claude plugin update engineering@engineering && echo "local install updated to $NEW"
else
  echo "engineering@engineering is not installed here; skipping local update"
fi
echo "Recipients get $NEW with: claude plugin update engineering@engineering"
