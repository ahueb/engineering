#!/usr/bin/env bash
# Scaffolds the B01 explicit comment-cleanup fixture via the shared builder.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/../comment-guidance-support/build_fixture.py" --case behaviour-comment-cleanup --workspace "$PWD"
