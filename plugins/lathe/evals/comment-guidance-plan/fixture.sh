#!/usr/bin/env bash
# Scaffolds the B04 plan-execution fixture (windowing/presentation + PLAN.md) via the shared builder.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$DIR/../comment-guidance-support/build_fixture.py" --case comment-guidance-plan --workspace "$PWD"
