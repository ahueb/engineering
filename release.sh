#!/usr/bin/env bash
# Bump the plugin version, commit, and refresh the locally installed copy.
# Claude Code installs plugins into a version-keyed cache and skips `plugin update`
# when the version is unchanged, so edits are invisible until this runs.
#
#   ./release.sh patch|minor|major     bump semver, run ci.sh, commit, sign tag vX.Y.Z, update local install
#   ./release.sh 2.3.0                 set an explicit version
#   ./release.sh --no-commit patch     bump and update only (--no-commit may appear anywhere)
#
# Before writing anything, the working tree must be clean except for
# CHANGELOG.md and the plugin manifest (those are the only files this script
# commits). After writing the new version, `claude plugin validate --strict`
# must pass; on failure the manifest is restored to its prior contents and
# nothing is committed.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="$HERE/plugins/engineering/.claude-plugin/plugin.json"
COMMIT=1
KIND=""
while [ $# -gt 0 ]; do
  case "$1" in
    --no-commit) COMMIT=0 ;;
    -*)
      echo "usage: $0 [--no-commit] patch|minor|major|x.y.z" >&2
      exit 2
      ;;
    *)
      if [ -n "$KIND" ]; then
        echo "usage: $0 [--no-commit] patch|minor|major|x.y.z" >&2
        exit 2
      fi
      KIND="$1"
      ;;
  esac
  shift
done
KIND="${KIND:-patch}"

CUR="$(python3 - "$MANIFEST" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["version"])
PY
)"
[[ "$CUR" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "plugin.json version '$CUR' is not x.y.z" >&2; exit 2; }

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

if [ -n "$(git -C "$HERE" status --porcelain -- . ":(exclude)CHANGELOG.md" ":(exclude)plugins/engineering/.claude-plugin/plugin.json")" ]; then
  echo "working tree has unrelated changes; commit or stash them first" >&2
  exit 1
fi

ORIG="$(mktemp)"
cp "$MANIFEST" "$ORIG"
# Until the release is committed (or --no-commit finishes), any failure restores the manifest.
RELEASED=0
CI_LOG=""
trap 'if [ "$RELEASED" != 1 ]; then cp "$ORIG" "$MANIFEST"; fi; rm -f "$ORIG" ${CI_LOG:+"$CI_LOG"}' EXIT

python3 - "$MANIFEST" "$NEW" <<'PY'
import json, sys
p, v = sys.argv[1], sys.argv[2]
d = json.load(open(p)); d["version"] = v
with open(p, "w") as f: json.dump(d, f, indent=2); f.write("\n")
PY
echo "version: $CUR -> $NEW"

if ! claude plugin validate "$HERE/plugins/engineering" --strict; then
  echo "validation failed; version restored to $CUR" >&2
  exit 1
fi
echo "validation passed"

# release requires --full to have passed since the last installer-affecting change: run the
# network-covering tier when install.sh, ci.sh, scripts/, or ci/ changed since the previous
# tag (or when there is no previous tag yet), else the normal offline gate.
LAST_TAG="$(git -C "$HERE" describe --tags --abbrev=0 2>/dev/null || true)"
CI_TIER=""
if [ -z "$LAST_TAG" ]; then
  CI_TIER="--full"
  echo "no previous tag found; running ./ci.sh --full"
else
  # A git failure here must not be read as "nothing changed": fall back to --full.
  DIFF_RC=0
  CHANGED_PATHS="$(git -C "$HERE" diff --name-only "$LAST_TAG"..HEAD -- install.sh ci.sh scripts ci 2>/dev/null)" || DIFF_RC=$?
  if [ "$DIFF_RC" != 0 ]; then
    CI_TIER="--full"
    echo "could not diff against $LAST_TAG (git exit $DIFF_RC); running ./ci.sh --full"
  elif [ -n "$CHANGED_PATHS" ]; then
    CI_TIER="--full"
    echo "install.sh, ci.sh, scripts/, or ci/ changed since $LAST_TAG; running ./ci.sh --full"
  else
    echo "no installer-affecting changes since $LAST_TAG; running ./ci.sh"
  fi
fi
CI_LOG="$(mktemp)"
CI_RESULT=0
if [ "$CI_TIER" = "--full" ]; then
  "$HERE/ci.sh" --full >"$CI_LOG" 2>&1 || CI_RESULT=$?
else
  "$HERE/ci.sh" >"$CI_LOG" 2>&1 || CI_RESULT=$?
fi
if [ "$CI_RESULT" != 0 ]; then
  echo "ci.sh${CI_TIER:+ $CI_TIER} failed; version restored to $CUR" >&2
  grep -E '^ +FAIL: |^CI: ' "$CI_LOG" >&2 || tail -n 20 "$CI_LOG" >&2
  exit 1
fi
echo "ci passed (tier: ${CI_TIER:-default})"
# Which network scenarios actually ran is the evidence a release depends on; surface it.
if [ "$CI_TIER" = "--full" ]; then
  grep '^full-tier scenarios run:' "$CI_LOG" || echo "WARN: ci.sh --full printed no 'full-tier scenarios run:' line" >&2
fi

if [ "$COMMIT" = 1 ] && git -C "$HERE" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  git -C "$HERE" add -- "$MANIFEST" || { echo "git add failed" >&2; exit 1; }
  if [ -f "$HERE/CHANGELOG.md" ]; then
    git -C "$HERE" add -- "$HERE/CHANGELOG.md" || { echo "git add failed" >&2; exit 1; }
  fi
  if git -C "$HERE" diff --cached --quiet; then
    echo "nothing to commit (version unchanged)"
  else
    # `cmd && echo` would swallow a failure under set -e (the && makes it a tested
    # command), so commit and tag failures are handled explicitly.
    if ! git -C "$HERE" commit -qm "Release engineering $NEW"; then
      git -C "$HERE" reset -q -- "$MANIFEST" "$HERE/CHANGELOG.md" 2>/dev/null || true
      echo "git commit failed; version restored to $CUR and the index unstaged" >&2
      exit 1
    fi
    echo "committed"
    # The commit already carries $NEW: from here the EXIT trap must never put the old
    # manifest back, or the working tree would disagree with the release commit.
    RELEASED=1
    if ! git -C "$HERE" tag -s "v$NEW" -m "engineering $NEW"; then
      echo "git tag failed; the release commit stands. Create the tag with:" >&2
      echo "  git tag -s v$NEW -m 'engineering $NEW'" >&2
      exit 1
    fi
    echo "tagged v$NEW (signed)"
  fi
fi
RELEASED=1

if claude plugin list 2>/dev/null | grep -q "engineering@engineering"; then
  if claude plugin update engineering@engineering; then
    echo "local install updated to $NEW"
  else
    echo "WARN: local plugin update failed; run: claude plugin update engineering@engineering" >&2
  fi
else
  echo "engineering@engineering is not installed here; skipping local update"
fi
echo "Publish with: git push && git push --tags"
echo "Recipients get $NEW with: claude plugin update engineering@engineering"
