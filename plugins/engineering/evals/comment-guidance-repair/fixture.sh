#!/usr/bin/env bash
# Scaffolds the B07 boundary-off-by-one repair fixture (with captured failing-test output) via the shared builder.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/../comment-guidance-support/build_fixture.py" --case comment-guidance-repair --workspace "$PWD"
