#!/usr/bin/env bash
# Scaffold: the comment-guidance review fixture (a small repo with accurate and stale comments).
set -euo pipefail
exec python3 "$(dirname "${BASH_SOURCE[0]}")/../comment-guidance-support/build_fixture.py" --case comment-guidance-review-only --workspace "$PWD"
