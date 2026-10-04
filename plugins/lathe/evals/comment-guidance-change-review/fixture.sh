#!/usr/bin/env bash
# Scaffolds the B05 change-review fixture (uncommitted diff with a false authorization/ordering claim) via the shared builder.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/../comment-guidance-support/build_fixture.py" --case comment-guidance-change-review --workspace "$PWD"
