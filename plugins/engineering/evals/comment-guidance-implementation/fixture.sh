#!/usr/bin/env bash
# Scaffolds the B03 implementation fixture (contracts.py + test_contracts.py) via the shared builder.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/../comment-guidance-support/build_fixture.py" --case comment-guidance-implementation --workspace "$PWD"
