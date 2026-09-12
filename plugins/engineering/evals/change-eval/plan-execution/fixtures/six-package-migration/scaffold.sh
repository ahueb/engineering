#!/usr/bin/env bash
# Scaffold the six-package-migration fixture into $1 (created fresh).
# Usage: scaffold.sh <target-dir>
set -euo pipefail

TARGET="${1:?usage: scaffold.sh <target-dir>}"
rm -rf "$TARGET"
mkdir -p "$TARGET/src/services" "$TARGET/tests"

cat > "$TARGET/src/__init__.py" <<'EOF'
EOF
cat > "$TARGET/src/services/__init__.py" <<'EOF'
EOF
cat > "$TARGET/tests/__init__.py" <<'EOF'
EOF

cat > "$TARGET/src/legacy_config.py" <<'EOF'
"""Deprecated config store. Being migrated away from; do not use in new code."""
_STORE = {"timeout": "30", "retries": "3", "region": "us-east-1"}


def get(key, default=None):
    return _STORE.get(key, default)
EOF

cat > "$TARGET/src/config.py" <<'EOF'
"""New config API. Pre-existing, shared by every package below. Do not modify."""


class Config:
    _STORE = {"timeout": "30", "retries": "3", "region": "us-east-1"}

    def get(self, key, default=None):
        return self._STORE.get(key, default)
EOF

# svcN specs: (index, config-key, default, expected-value)
declare -a SPECS=(
  "1 timeout 10 30"
  "2 retries 1 3"
  "3 region local us-east-1"
  "4 timeout 5 30"
  "5 retries 0 3"
  "6 region unknown us-east-1"
)

for spec in "${SPECS[@]}"; do
  read -r n key default expected <<<"$spec"
  cat > "$TARGET/src/services/svc${n}.py" <<EOF
from src import legacy_config


def get_${key}():
    return legacy_config.get("${key}", "${default}")


def describe():
    return f"svc${n} ${key}={get_${key}()}"
EOF

  cat > "$TARGET/tests/test_svc${n}.py" <<EOF
import unittest

from src.services.svc${n} import get_${key}, describe


class TestSvc${n}(unittest.TestCase):
    def test_get_${key}(self):
        self.assertEqual(get_${key}(), "${expected}")

    def test_describe(self):
        self.assertEqual(describe(), "svc${n} ${key}=${expected}")


if __name__ == "__main__":
    unittest.main()
EOF
done

{
  echo "# Plan: migrate six services off the deprecated legacy_config module"
  echo
  echo "Six independent migrations, one per service. Each task owns disjoint"
  echo "files. The replacement API, \`src/config.py\` (\`Config\` class), is"
  echo "already implemented; do not modify it."
  echo
  for spec in "${SPECS[@]}"; do
    read -r n key default expected <<<"$spec"
    echo "## Task ${n}: migrate svc${n}"
    echo
    echo "Files: \`src/services/svc${n}.py\` (modify), \`tests/test_svc${n}.py\` (modify only if needed)."
    echo
    echo "Replace the \`from src import legacy_config\` / \`legacy_config.get(...)\`"
    echo "call in \`get_${key}\` with \`config.Config().get(\"${key}\", \"${default}\")\`"
    echo "(import \`from src.config import Config\`). \`svc${n}.py\` must not import"
    echo "\`legacy_config\` afterward. Behaviour (return values of \`get_${key}\` and"
    echo "\`describe\`) must not change."
    echo
    echo "Acceptance: \`tests/test_svc${n}.py\` passes unchanged (expects"
    echo "\`get_${key}() == \"${expected}\"\`)."
    echo
  done
  echo "## Test command"
  echo
  echo '```'
  echo "python3 -m unittest discover -s tests -t . -v"
  echo '```'
} > "$TARGET/plan.md"

cd "$TARGET"
git init -q
git add -A
git -c user.email=fixture@example.com -c user.name=fixture commit -q -m "scaffold: six-package-migration fixture"
