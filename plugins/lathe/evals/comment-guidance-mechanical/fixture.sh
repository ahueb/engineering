#!/usr/bin/env bash
# Scaffolds the B06 mechanical-rename fixture via the shared builder.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/../comment-guidance-support/build_fixture.py" --case comment-guidance-mechanical --workspace "$PWD"
