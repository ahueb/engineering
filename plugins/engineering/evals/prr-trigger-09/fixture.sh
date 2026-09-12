#!/usr/bin/env bash
# Scaffold: build the shared orders-api fixture repository in the workspace.
set -euo pipefail
exec bash "$(dirname "${BASH_SOURCE[0]}")/../fixture-service.sh"
