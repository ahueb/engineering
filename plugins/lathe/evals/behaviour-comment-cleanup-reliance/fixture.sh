#!/usr/bin/env bash
# Scaffolds the B09 comment-cleanup reliance fixture via the shared builder.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/../comment-guidance-support/build_fixture.py" --case behaviour-comment-cleanup-reliance --workspace "$PWD"
