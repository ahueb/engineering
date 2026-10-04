#!/usr/bin/env bash
# Scaffolds the B08 documentation-only plan plus unproved runtime-claim item via the shared builder.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/../comment-guidance-support/build_fixture.py" --case comment-guidance-doc-plan --workspace "$PWD"
