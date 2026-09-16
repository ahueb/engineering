#!/usr/bin/env bash
# Scaffolds the B02 review-only fixture (no checker/convenience files) via the shared builder.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/../comment-guidance-support/build_fixture.py" --case comment-guidance-review-only --workspace "$PWD"
