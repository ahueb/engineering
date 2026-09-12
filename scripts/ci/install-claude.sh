#!/usr/bin/env bash
# Install Claude Code at the version pinned in claude-version.txt and verify the binary
# against Anthropic's GPG-signed release manifest before it is used by CI.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VERSION="$(tr -d '[:space:]' < "$HERE/claude-version.txt")"
KEY="$HERE/anthropic-release-key.asc"
FPR="31DDDE24DDFAB679F42D7BD2BAA929FF1A7ECACE"
REPO="https://downloads.claude.ai/claude-code-releases"
TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# 1. Key: the vendored key must carry the published fingerprint and must be the only
#    primary key imported into this throwaway keyring.
export GNUPGHOME="$TMP/gnupg"; mkdir -m 0700 "$GNUPGHOME"
gpg --batch --import "$KEY" >/dev/null 2>&1
[ "$(gpg --batch --with-colons --list-keys 2>/dev/null | grep -c '^pub:')" -eq 1 ] || { echo "more than one primary key imported" >&2; exit 1; }
gpg --batch --with-colons --fingerprint 2>/dev/null | grep -q "^fpr:*:$FPR:" || { echo "release key fingerprint mismatch" >&2; exit 1; }

# 2. Manifest: signature must verify against that key and be bound to the pinned fingerprint.
curl -fsSL "$REPO/$VERSION/manifest.json" -o "$TMP/manifest.json"
curl -fsSL "$REPO/$VERSION/manifest.json.sig" -o "$TMP/manifest.json.sig"
STATUS="$(gpg --batch --status-fd 1 --verify "$TMP/manifest.json.sig" "$TMP/manifest.json" 2>/dev/null)" || { echo "manifest signature invalid for $VERSION" >&2; exit 1; }
echo "$STATUS" | grep -Eq "^\[GNUPG:\] VALIDSIG .* $FPR\$" || { echo "manifest signature not bound to $FPR" >&2; exit 1; }
echo "$STATUS" | grep -Eq "^\[GNUPG:\] (EXPKEYSIG|REVKEYSIG|KEYREVOKED|KEYEXPIRED|EXPSIG)" && { echo "manifest signed by an expired or revoked key" >&2; exit 1; }

# 3. Download the platform binary named in the verified manifest directly (no convenience
#    installer is executed) and verify its SHA256 and size against the manifest BEFORE the
#    binary is placed anywhere or run.
case "$(uname -s)-$(uname -m)" in
  Linux-x86_64) PLATFORM=linux-x64 ;;
  Linux-aarch64|Linux-arm64) PLATFORM=linux-arm64 ;;
  Darwin-arm64) PLATFORM=darwin-arm64 ;;
  Darwin-x86_64) PLATFORM=darwin-x64 ;;
  *) echo "unsupported platform $(uname -s)-$(uname -m)" >&2; exit 1 ;;
esac
BINARY_NAME="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["platforms"][sys.argv[2]]["binary"])' "$TMP/manifest.json" "$PLATFORM")"
EXPECTED_CHECKSUM="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["platforms"][sys.argv[2]]["checksum"])' "$TMP/manifest.json" "$PLATFORM")"
EXPECTED_SIZE="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["platforms"][sys.argv[2]]["size"])' "$TMP/manifest.json" "$PLATFORM")"

curl -fsSL "$REPO/$VERSION/$PLATFORM/$BINARY_NAME" -o "$TMP/claude"

ACTUAL_SIZE="$(python3 -c 'import os,sys; print(os.path.getsize(sys.argv[1]))' "$TMP/claude")"
ACTUAL_CHECKSUM="$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$TMP/claude")"
EXPECTED_CHECKSUM="$(printf '%s' "$EXPECTED_CHECKSUM" | tr 'A-F' 'a-f')"
if [ "$EXPECTED_CHECKSUM" != "$ACTUAL_CHECKSUM" ] || [ "$EXPECTED_SIZE" -ne "$ACTUAL_SIZE" ]; then
  rm -f "$TMP/claude"
  echo "binary checksum/size mismatch: expected sha256=$EXPECTED_CHECKSUM size=$EXPECTED_SIZE got sha256=$ACTUAL_CHECKSUM size=$ACTUAL_SIZE" >&2
  exit 1
fi

mkdir -p "$HOME/.local/bin"
chmod 0755 "$TMP/claude"
mv "$TMP/claude" "$HOME/.local/bin/claude"
BIN="$HOME/.local/bin/claude"

echo "claude $VERSION verified ($PLATFORM, sha256 $ACTUAL_CHECKSUM)"
"$BIN" --version | grep -qF "$VERSION" || { echo "installer produced a different version" >&2; exit 1; }
"$BIN" --version
