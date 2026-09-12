#!/usr/bin/env bash
# Release the engineering plugin through a required-check-gated PR flow.
# Claude Code installs plugins into a version-keyed cache and skips `plugin update`
# when the version is unchanged, so edits are invisible until `tag` (or the
# --no-commit escape hatch) refreshes the local copy.
#
#   ./release.sh prepare patch|minor|major|x.y.z [--no-pr]
#       bump plugin.json, fold CHANGELOG.md's "## [Unreleased]" content into a
#       new dated "## [X.Y.Z] - <date>" section, validate the plugin, run
#       ci.sh (tier auto-selected), branch release/vX.Y.Z from the current
#       HEAD, commit "Release engineering X.Y.Z" (plugin.json and CHANGELOG.md
#       only), and push it. Unless --no-pr, then opens/watches/merges the PR
#       (same as `pr` below).
#   ./release.sh pr X.Y.Z
#       for an already-pushed release/vX.Y.Z branch: gh pr create (base
#       main), gh pr checks --watch --fail-fast, gh pr merge --squash
#       --delete-branch. Requires an authenticated `gh`.
#   ./release.sh tag [X.Y.Z]
#       fetch origin/main, require its head commit subject to be exactly
#       "Release engineering X.Y.Z" and plugin.json at that commit to be
#       X.Y.Z, sign and push tag vX.Y.Z from origin/main, then refresh the
#       local plugin install. X.Y.Z defaults to origin/main's plugin.json
#       version.
#
# Legacy (deprecated), kept for compatibility:
#   ./release.sh patch|minor|major|x.y.z [--no-commit]
#       behaves like `prepare <bump> --no-pr`; --no-commit keeps its old
#       meaning of bumping, validating, and running ci.sh only, with nothing
#       branched, committed, or pushed.
#
# Before writing anything, the working tree must be clean except for
# CHANGELOG.md and the plugin manifest (those are the only files `prepare`
# commits). After writing the new version, `claude plugin validate --strict`
# must pass; on failure the manifest and changelog are restored to their
# prior contents and nothing is committed.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="$HERE/plugins/engineering/.claude-plugin/plugin.json"
CHANGELOG="$HERE/CHANGELOG.md"
REPO_URL="https://github.com/ahueb/engineering"

usage() {
  cat >&2 <<'EOF'
usage:
  release.sh prepare patch|minor|major|x.y.z [--no-pr]
  release.sh pr X.Y.Z
  release.sh tag [X.Y.Z]
  release.sh patch|minor|major|x.y.z [--no-commit]   (deprecated)
EOF
}

bump_version() {
  # $1 = current version, $2 = kind (patch|minor|major)
  python3 - "$1" "$2" <<'PY'
import sys
maj, mi, pa = (int(x) for x in sys.argv[1].split("."))
k = sys.argv[2]
print({"major": f"{maj+1}.0.0", "minor": f"{maj}.{mi+1}.0", "patch": f"{maj}.{mi}.{pa+1}"}[k])
PY
}

read_manifest_version() {
  python3 - "$1" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["version"])
PY
}

check_clean_tree() {
  if [ -n "$(git -C "$HERE" status --porcelain -- . ":(exclude)CHANGELOG.md" ":(exclude)plugins/engineering/.claude-plugin/plugin.json")" ]; then
    echo "working tree has unrelated changes; commit or stash them first" >&2
    exit 1
  fi
}

# Fold the CHANGELOG.md "## [Unreleased]" section's content under a new
# "## [X.Y.Z] - DATE" heading, leaving an empty Unreleased heading, and
# repoint/add the compare links at the bottom.
update_changelog() {
  local new="$1" cur="$2" date="$3"
  python3 - "$CHANGELOG" "$new" "$cur" "$date" "$REPO_URL" <<'PY'
import re, sys
path, new, cur, date, repo = sys.argv[1:6]
text = open(path).read()
lines = text.split("\n")
heading_idxs = [i for i, l in enumerate(lines) if l.startswith("## [")]
unrel_idx = next((i for i in heading_idxs if lines[i].strip() == "## [Unreleased]"), None)
if unrel_idx is None:
    sys.exit("release.sh: no '## [Unreleased]' heading found in CHANGELOG.md")
next_idx = next((i for i in heading_idxs if i > unrel_idx), len(lines))
content = lines[unrel_idx + 1:next_idx]
while content and content[0].strip() == "":
    content.pop(0)
while content and content[-1].strip() == "":
    content.pop()
new_heading = "## [%s] - %s" % (new, date)
rebuilt = lines[:unrel_idx + 1] + [""] + [new_heading]
if content:
    rebuilt += [""] + content
rebuilt += [""] + lines[next_idx:]
text = "\n".join(rebuilt)

# Repoint the Unreleased compare link and insert the new version's link.
old_unrel_re = re.compile(r"^\[Unreleased\]: .*$", re.M)
m = old_unrel_re.search(text)
if m is None:
    sys.exit("release.sh: no '[Unreleased]:' compare link found in CHANGELOG.md")
new_unrel_line = "[Unreleased]: %s/compare/v%s...HEAD" % (repo, new)
new_ver_line = "[%s]: %s/compare/v%s...v%s" % (new, repo, cur, new)
text = text[:m.start()] + new_unrel_line + "\n" + new_ver_line + text[m.end():]

with open(path, "w") as f:
    f.write(text)
PY
}

# Sets CI_TIER ("--full" or "") and TIER_REASON, based on whether
# install.sh, ci.sh, scripts/, or ci/ changed since the last tag.
ci_tier_reason() {
  local last_tag diff_rc=0 changed_paths
  last_tag="$(git -C "$HERE" describe --tags --abbrev=0 2>/dev/null || true)"
  if [ -z "$last_tag" ]; then
    CI_TIER="--full"; TIER_REASON="no previous tag found"
    return
  fi
  changed_paths="$(git -C "$HERE" diff --name-only "$last_tag"..HEAD -- install.sh ci.sh scripts ci 2>/dev/null)" || diff_rc=$?
  if [ "$diff_rc" != 0 ]; then
    CI_TIER="--full"; TIER_REASON="could not diff against $last_tag (git exit $diff_rc)"
  elif [ -n "$changed_paths" ]; then
    CI_TIER="--full"; TIER_REASON="install.sh, ci.sh, scripts/, or ci/ changed since $last_tag"
  else
    CI_TIER=""; TIER_REASON="no installer-affecting changes since $last_tag"
  fi
}

# Prints the CHANGELOG.md body text for "## [VERSION] ..." (without the
# heading itself), or nothing if that heading is not present.
changelog_section() {
  python3 - "$CHANGELOG" "$1" <<'PY'
import re, sys
path, ver = sys.argv[1], sys.argv[2]
text = open(path).read()
m = re.search(r"^## \[" + re.escape(ver) + r"\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.M | re.S)
print(m.group(1).strip() if m else "")
PY
}

# $1 = kind|x.y.z, $2 = 1 to skip the PR step, $3 = 1 to skip branch/commit/push entirely.
do_prepare() {
  local KIND="$1" NO_PR="$2" NO_COMMIT="$3"

  local CUR
  CUR="$(read_manifest_version "$MANIFEST")"
  [[ "$CUR" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "plugin.json version '$CUR' is not x.y.z" >&2; exit 2; }

  local NEW
  case "$KIND" in
    patch|minor|major) NEW="$(bump_version "$CUR" "$KIND")" ;;
    *) NEW="$KIND"; [[ "$NEW" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "not a semver version: $NEW" >&2; exit 2; } ;;
  esac

  check_clean_tree

  # Not local: the EXIT trap installed below fires after this function returns, and under
  # set -u a vanished local would make the trap itself fail after a successful release.
  ORIG_MANIFEST="$(mktemp)"; cp "$MANIFEST" "$ORIG_MANIFEST"
  ORIG_CHANGELOG="$(mktemp)"; cp "$CHANGELOG" "$ORIG_CHANGELOG"
  # Until the release is committed (or --no-commit finishes), any failure
  # restores the manifest and changelog.
  RELEASED=0
  CI_LOG=""
  trap 'if [ "$RELEASED" != 1 ]; then cp "$ORIG_MANIFEST" "$MANIFEST"; cp "$ORIG_CHANGELOG" "$CHANGELOG"; fi; rm -f "$ORIG_MANIFEST" "$ORIG_CHANGELOG" ${CI_LOG:+"$CI_LOG"}' EXIT

  python3 - "$MANIFEST" "$NEW" <<'PY'
import json, sys
p, v = sys.argv[1], sys.argv[2]
d = json.load(open(p)); d["version"] = v
with open(p, "w") as f: json.dump(d, f, indent=2); f.write("\n")
PY
  echo "version: $CUR -> $NEW"

  update_changelog "$NEW" "$CUR" "$(date +%Y-%m-%d)"
  echo "CHANGELOG.md: moved [Unreleased] content under [$NEW]"

  if ! claude plugin validate "$HERE/plugins/engineering" --strict; then
    echo "validation failed; version and changelog restored" >&2
    exit 1
  fi
  echo "validation passed"

  # release requires --full to have passed since the last installer-affecting
  # change: run the network-covering tier when install.sh, ci.sh, scripts/,
  # or ci/ changed since the previous tag (or when there is no previous tag
  # yet), else the normal offline gate.
  ci_tier_reason
  if [ "$CI_TIER" = "--full" ]; then
    echo "$TIER_REASON; running ./ci.sh --full"
  else
    echo "$TIER_REASON; running ./ci.sh"
  fi
  CI_LOG="$(mktemp)"
  local CI_RESULT=0
  if [ "$CI_TIER" = "--full" ]; then
    "$HERE/ci.sh" --full >"$CI_LOG" 2>&1 || CI_RESULT=$?
  else
    "$HERE/ci.sh" >"$CI_LOG" 2>&1 || CI_RESULT=$?
  fi
  if [ "$CI_RESULT" != 0 ]; then
    echo "ci.sh${CI_TIER:+ $CI_TIER} failed; version and changelog restored" >&2
    grep -E '^ +FAIL: |^CI: ' "$CI_LOG" >&2 || tail -n 20 "$CI_LOG" >&2
    exit 1
  fi
  echo "ci passed (tier: ${CI_TIER:-default})"
  # Which network scenarios actually ran is the evidence a release depends on; surface it.
  FULL_TIER_LINE=""
  if [ "$CI_TIER" = "--full" ]; then
    FULL_TIER_LINE="$(grep '^full-tier scenarios run:' "$CI_LOG" || true)"
    if [ -n "$FULL_TIER_LINE" ]; then
      echo "$FULL_TIER_LINE"
    else
      echo "WARN: ci.sh --full printed no 'full-tier scenarios run:' line" >&2
    fi
  fi

  if [ "$NO_COMMIT" = 1 ]; then
    RELEASED=1
    echo "--no-commit: version bumped and validated; nothing committed"
  else
    if ! git -C "$HERE" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      echo "not inside a git work tree; cannot branch/commit" >&2
      exit 1
    fi
    local BRANCH="release/v$NEW"
    if ! git -C "$HERE" checkout -b "$BRANCH"; then
      echo "git checkout -b $BRANCH failed" >&2
      exit 1
    fi
    echo "branched $BRANCH"
    git -C "$HERE" add -- "$MANIFEST" "$CHANGELOG" || { echo "git add failed" >&2; exit 1; }
    if git -C "$HERE" diff --cached --quiet; then
      echo "nothing to commit (version unchanged)"
      RELEASED=1
    else
      # `cmd && echo` would swallow a failure under set -e (the && makes it a
      # tested command), so commit and push failures are handled explicitly.
      if ! git -C "$HERE" commit -qm "Release engineering $NEW"; then
        git -C "$HERE" reset -q -- "$MANIFEST" "$CHANGELOG" 2>/dev/null || true
        echo "git commit failed; version and changelog restored, index unstaged" >&2
        exit 1
      fi
      echo "committed"
      # The commit already carries $NEW: from here the EXIT trap must never
      # put the old manifest/changelog back.
      RELEASED=1
      if ! ENGINEERING_RELEASE=1 git -C "$HERE" push -u origin "$BRANCH"; then
        echo "git push failed; push manually with:" >&2
        echo "  ENGINEERING_RELEASE=1 git push -u origin $BRANCH" >&2
        exit 1
      fi
      echo "pushed $BRANCH"
      if [ "$NO_PR" != 1 ]; then
        do_pr "$NEW"
      else
        echo "Continue with: ./release.sh pr $NEW"
      fi
    fi
  fi

  if claude plugin list 2>/dev/null | grep -q "engineering@engineering"; then
    if claude plugin update engineering@engineering; then
      echo "local install updated to $NEW"
    else
      echo "WARN: local plugin update failed; run: claude plugin update engineering@engineering" >&2
    fi
  else
    echo "engineering@engineering is not installed here; skipping local update"
  fi
}

# $1 = X.Y.Z, for an already-pushed release/vX.Y.Z branch.
do_pr() {
  local V="$1"
  local BRANCH="release/v$V"

  if ! command -v gh >/dev/null 2>&1 || ! gh auth status >/dev/null 2>&1; then
    echo "gh is not installed or not authenticated; finish the release manually:" >&2
    echo "  gh pr create --base main --head $BRANCH --title \"Release engineering $V\" --body-file <body.md>" >&2
    echo "  gh pr checks $BRANCH --watch --fail-fast" >&2
    echo "  gh pr merge $BRANCH --squash --subject \"Release engineering $V\" --delete-branch" >&2
    exit 1
  fi

  local BODY SECTION
  BODY="$(mktemp)"
  SECTION="$(changelog_section "$V")"
  {
    if [ -n "$SECTION" ]; then
      echo "$SECTION"
      echo
    fi
    if [ -n "${FULL_TIER_LINE:-}" ]; then
      echo "$FULL_TIER_LINE"
    else
      ci_tier_reason
      if [ "$CI_TIER" = "--full" ]; then
        echo "ci tier: full ($TIER_REASON)"
      else
        echo "ci tier: default ($TIER_REASON)"
      fi
    fi
  } > "$BODY"

  if ! gh pr create --base main --head "$BRANCH" --title "Release engineering $V" --body-file "$BODY"; then
    echo "gh pr create failed; retry with:" >&2
    echo "  gh pr create --base main --head $BRANCH --title \"Release engineering $V\" --body-file $BODY" >&2
    exit 1
  fi
  # $BODY is only needed for the create retry hint above; every later failure path (and the
  # success path) removes it here.
  rm -f "$BODY"
  echo "PR opened for $BRANCH"

  if ! gh pr checks "$BRANCH" --watch --fail-fast; then
    echo "gh pr checks failed; after fixing, continue with:" >&2
    echo "  gh pr checks $BRANCH --watch --fail-fast" >&2
    echo "  gh pr merge $BRANCH --squash --subject \"Release engineering $V\" --delete-branch" >&2
    exit 1
  fi
  echo "checks passed"

  # Squash, not rebase: main requires signed commits, and GitHub signs the squash commit it
  # creates but cannot sign the commits a rebase merge rewrites. The subject is what
  # `release.sh tag` later checks at origin/main.
  if ! gh pr merge "$BRANCH" --squash --subject "Release engineering $V" --delete-branch; then
    echo "gh pr merge failed; retry with:" >&2
    echo "  gh pr merge $BRANCH --squash --subject \"Release engineering $V\" --delete-branch" >&2
    exit 1
  fi
  echo "merged $BRANCH into main (squash) and deleted the branch"
}

# $1 = X.Y.Z or empty (defaults to origin/main's plugin.json version).
cmd_tag() {
  local V="$1"
  git -C "$HERE" fetch origin main
  local HEAD_SHA HEAD_SUBJECT
  HEAD_SHA="$(git -C "$HERE" rev-parse origin/main)"
  HEAD_SUBJECT="$(git -C "$HERE" log -1 --format=%s "$HEAD_SHA")"
  if [ -z "$V" ]; then
    V="$(git -C "$HERE" show "$HEAD_SHA:plugins/engineering/.claude-plugin/plugin.json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')"
  fi
  if [ "$HEAD_SUBJECT" != "Release engineering $V" ]; then
    echo "origin/main HEAD ($HEAD_SHA) subject is '$HEAD_SUBJECT'; expected 'Release engineering $V'" >&2
    exit 1
  fi
  local MANIFEST_VERSION
  MANIFEST_VERSION="$(git -C "$HERE" show "$HEAD_SHA:plugins/engineering/.claude-plugin/plugin.json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["version"])')"
  if [ "$MANIFEST_VERSION" != "$V" ]; then
    echo "plugin.json at origin/main is $MANIFEST_VERSION; expected $V" >&2
    exit 1
  fi

  if ! git -C "$HERE" tag -s "v$V" -m "engineering $V" origin/main; then
    echo "git tag failed; create it manually with:" >&2
    echo "  git tag -s v$V -m 'engineering $V' origin/main" >&2
    exit 1
  fi
  echo "tagged v$V (signed) on origin/main ($HEAD_SHA)"

  if ! ENGINEERING_RELEASE=1 git -C "$HERE" push origin "v$V"; then
    echo "git push of the tag failed; push manually with:" >&2
    echo "  ENGINEERING_RELEASE=1 git push origin v$V" >&2
    exit 1
  fi
  echo "pushed v$V"

  if claude plugin list 2>/dev/null | grep -q "engineering@engineering"; then
    if claude plugin update engineering@engineering; then
      echo "local install updated to $V"
    else
      echo "WARN: local plugin update failed; run: claude plugin update engineering@engineering" >&2
    fi
  else
    echo "engineering@engineering is not installed here; skipping local update"
  fi
}

main() {
  if [ $# -eq 0 ]; then usage; exit 2; fi
  case "$1" in
    -h|--help) usage; exit 0 ;;
    prepare)
      shift
      local KIND="" NO_PR=0
      while [ $# -gt 0 ]; do
        case "$1" in
          --no-pr) NO_PR=1 ;;
          -*) usage; exit 2 ;;
          *)
            if [ -n "$KIND" ]; then usage; exit 2; fi
            KIND="$1"
            ;;
        esac
        shift
      done
      [ -n "$KIND" ] || { usage; exit 2; }
      do_prepare "$KIND" "$NO_PR" 0
      ;;
    pr)
      shift
      [ $# -eq 1 ] || { usage; exit 2; }
      do_pr "$1"
      ;;
    tag)
      shift
      [ $# -le 1 ] || { usage; exit 2; }
      cmd_tag "${1:-}"
      ;;
    *)
      # Legacy: release.sh patch|minor|major|x.y.z [--no-commit]
      echo "release.sh: '$1' is deprecated; use 'release.sh prepare $1' (or 'release.sh prepare $1 --no-pr')" >&2
      local KIND="" NO_COMMIT=0
      while [ $# -gt 0 ]; do
        case "$1" in
          --no-commit) NO_COMMIT=1 ;;
          -*) usage; exit 2 ;;
          *)
            if [ -n "$KIND" ]; then usage; exit 2; fi
            KIND="$1"
            ;;
        esac
        shift
      done
      [ -n "$KIND" ] || { usage; exit 2; }
      do_prepare "$KIND" 1 "$NO_COMMIT"
      ;;
  esac
}
main "$@"
