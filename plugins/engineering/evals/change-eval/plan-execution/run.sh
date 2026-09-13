#!/usr/bin/env bash
# plan-execution benchmark harness.
#
# Compares the shipped plan-execution skill ("current") against a variant
# with one added bounded package-local check ("bounded-check") across
# three frozen fixtures, 3 runs per (fixture, variant) cell = 18 runs.
#
# Usage:
#   run.sh --dry-run
#   run.sh --budget-usd <N> [--output-dir <dir>] [--runs <n>]
#
# Frozen inputs (not overridable except where noted):
#   model: sonnet
#   output-format: stream-json
#   permission-mode: acceptEdits
#   allowedTools: Read Write Edit Bash Agent Skill Grep Glob
#   runs per cell: 3
#
# The real run executes, per (fixture, variant, run):
#   claude -p '/engineering:plan-execution <plan>' \
#     --plugin-dir <variant-dir> --model sonnet --output-format stream-json \
#     --permission-mode acceptEdits \
#     --allowedTools Read Write Edit Bash Agent Skill Grep Glob
# inside a fresh scratch CLAUDE_CONFIG_DIR holding a copy of
# $HOME/.claude/.credentials.json (or $CLAUDE_CONFIG_DIR/.credentials.json
# if that env var is already set), and inside a fresh git repository built
# by the fixture's scaffold.sh.
#
# Assumption: the CLI's stream-json output over -p works with the exact
# flag set given in the plan/contract. If your installed CLI version
# requires --verbose for --output-format stream-json under -p, set
# EXTRA_CLAUDE_FLAGS="--verbose" in the environment before invoking this
# script; run.sh does not add flags on its own.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"   # plugins/engineering
LIB_DIR="$SCRIPT_DIR/lib"
FIXTURES_DIR="$SCRIPT_DIR/fixtures"
VARIANTS_DIR="$SCRIPT_DIR/variants"

FIXTURES=(two-package-refactor four-package-feature six-package-migration)
VARIANTS=(current bounded-check)
RUNS_PER_CELL=3

MODEL="sonnet"
OUTPUT_FORMAT="stream-json"
PERMISSION_MODE="acceptEdits"
ALLOWED_TOOLS="Read Write Edit Bash Agent Skill Grep Glob"
TEST_CMD_SUBSTR="unittest discover"

DRY_RUN=false
BUDGET_USD=""
OUTPUT_DIR=""
EXTRA_CLAUDE_FLAGS="${EXTRA_CLAUDE_FLAGS:-}"

usage() {
  sed -n '2,40p' "${BASH_SOURCE[0]}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --budget-usd) BUDGET_USD="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --runs) RUNS_PER_CELL="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done

# Build the interleaved cell order: for each fixture, for each run index,
# for each variant. This satisfies "fixture 1 both variants, then fixture
# 2, ..." while allowing a per-pair budget check (a "pair" = both variants
# for the same fixture and run index).
build_cells() {
  for fixture in "${FIXTURES[@]}"; do
    for run_index in $(seq 1 "$RUNS_PER_CELL"); do
      for variant in "${VARIANTS[@]}"; do
        echo "${fixture}:${variant}:${run_index}"
      done
    done
  done
}

if $DRY_RUN; then
  echo "Frozen inputs:"
  echo "  model: $MODEL"
  echo "  output-format: $OUTPUT_FORMAT"
  echo "  permission-mode: $PERMISSION_MODE"
  echo "  allowedTools: $ALLOWED_TOOLS"
  echo "  runs per cell: $RUNS_PER_CELL"
  echo "  fixtures: ${FIXTURES[*]}"
  echo "  variants: ${VARIANTS[*]}"
  echo "  budget-usd: ${BUDGET_USD:-<none supplied>}"
  echo
  echo "Cells (fixture, variant, run), interleaved order:"
  i=0
  while IFS=: read -r fixture variant run_index; do
    i=$((i + 1))
    printf '  %2d. %s, %s, run %s\n' "$i" "$fixture" "$variant" "$run_index"
  done < <(build_cells)
  exit 0
fi

if [[ -n "$BUDGET_USD" && ! "$BUDGET_USD" =~ ^[0-9]+(\.[0-9]+)?$ ]]; then
  echo "--budget-usd must be a plain decimal number (got '$BUDGET_USD')" >&2
  exit 2
fi
if [[ -z "$BUDGET_USD" ]]; then
  echo "error: --budget-usd is required for a real run (set from the pilot: 1.5 * single-run cost * 18)" >&2
  exit 2
fi

if [[ -z "$OUTPUT_DIR" ]]; then
  OUTPUT_DIR="$SCRIPT_DIR/.runs/$(date -u +%Y%m%dT%H%M%SZ)"
fi
mkdir -p "$OUTPUT_DIR"
RESULTS_JSONL="$OUTPUT_DIR/results.jsonl"
SUMMARY_MD="$OUTPUT_DIR/summary.md"
LOGS_DIR="$OUTPUT_DIR/logs"
mkdir -p "$LOGS_DIR"
: > "$RESULTS_JSONL"

SRC_CFG_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
if [[ ! -f "$SRC_CFG_DIR/.credentials.json" ]]; then
  echo "error: no credentials found at $SRC_CFG_DIR/.credentials.json" >&2
  exit 2
fi

CUMULATIVE_COST="0"
STOP=false

build_variant_dir() {
  local variant="$1" dest="$2"
  rm -rf "$dest"
  mkdir -p "$dest"
  cp -r "$PLUGIN_ROOT/." "$dest/"
  # Never let a variant plugin dir carry its own copy of this benchmark's
  # working state; it is unused at run time and only adds copy cost.
  rm -rf "$dest/evals/change-eval/plan-execution/.runs"
  if [[ "$variant" == "bounded-check" ]]; then
    patch -p1 -d "$dest" < "$VARIANTS_DIR/bounded-check/skill.patch"
  fi
}

run_cell() {
  local fixture="$1" variant="$2" run_index="$3"
  local cell_id="${fixture}__${variant}__run${run_index}"
  echo "==> $cell_id" >&2

  local repo_dir cfg_dir variant_dir log_file err_file
  repo_dir="$(mktemp -d)"
  cfg_dir="$(mktemp -d)"
  variant_dir="$(mktemp -d)"
  log_file="$LOGS_DIR/${cell_id}.stream.jsonl"
  err_file="$LOGS_DIR/${cell_id}.stderr.log"

  "$FIXTURES_DIR/$fixture/scaffold.sh" "$repo_dir"
  build_variant_dir "$variant" "$variant_dir"
  cp "$SRC_CFG_DIR/.credentials.json" "$cfg_dir/.credentials.json"
  chmod 600 "$cfg_dir/.credentials.json"

  local plan_file="$repo_dir/plan.md"
  local start end wall
  start="$(python3 -c 'import time; print(time.time())')"
  (
    cd "$repo_dir"
    # shellcheck disable=SC2086
    CLAUDE_CONFIG_DIR="$cfg_dir" claude -p "/engineering:plan-execution $plan_file" \
      --plugin-dir "$variant_dir" \
      --model "$MODEL" \
      --output-format "$OUTPUT_FORMAT" \
      --permission-mode "$PERMISSION_MODE" \
      --allowedTools $ALLOWED_TOOLS \
      $EXTRA_CLAUDE_FLAGS
  ) > "$log_file" 2> "$err_file" || true
  end="$(python3 -c 'import time; print(time.time())')"
  wall="$(python3 -c 'import sys; print(round(float(sys.argv[1]) - float(sys.argv[2]), 2))' "$end" "$start")"

  local parsed
  parsed="$(python3 "$LIB_DIR/parse_run.py" "$log_file" "$TEST_CMD_SUBSTR")"
  local fan_out cost_usd repair_rounds
  fan_out="$(python3 -c "import json,sys;print(json.loads(sys.argv[1])['fan_out'])" "$parsed")"
  cost_usd="$(python3 -c "import json,sys;v=json.loads(sys.argv[1])['cost_usd'];print(v if v is not None else '')" "$parsed")"
  repair_rounds="$(python3 -c "import json,sys;print(json.loads(sys.argv[1])['repair_rounds'])" "$parsed")"

  # Authoritative test result: run the fixture's own test command directly,
  # independent of anything claimed in the transcript.
  local tests_passed="false"
  if ( cd "$repo_dir" && python3 -m unittest discover -s tests -t . ) > "$LOGS_DIR/${cell_id}.tests.log" 2>&1; then
    tests_passed="true"
  fi

  git -C "$repo_dir" add -A -N > /dev/null 2>&1 || true
  local diff_stat_lines
  diff_stat_lines="$(git -C "$repo_dir" diff --stat HEAD 2>/dev/null | wc -l | tr -d ' ')"

  local valid="true"
  if [[ "$fan_out" != "True" ]]; then
    valid="false"
  fi

  if [[ -n "$cost_usd" ]]; then
    CUMULATIVE_COST="$(python3 -c 'import sys; print(float(sys.argv[1]) + float(sys.argv[2]))' "$CUMULATIVE_COST" "$cost_usd")"
  fi

  python3 - "$RESULTS_JSONL" <<PYEOF
import json, sys
rec = {
    "fixture": "$fixture",
    "variant": "$variant",
    "run_index": $run_index,
    "valid": $( [[ "$valid" == "true" ]] && echo True || echo False ),
    "fan_out": $( [[ "$fan_out" == "True" ]] && echo True || echo False ),
    "tests_passed": $( [[ "$tests_passed" == "true" ]] && echo True || echo False ),
    "cost_usd": ${cost_usd:-None},
    "wall_clock_s": $wall,
    "repair_rounds": $repair_rounds,
    "diff_stat_lines": ${diff_stat_lines:-0},
    "cumulative_cost_usd": $CUMULATIVE_COST,
    "repo_dir": "$repo_dir",
    "log_file": "$log_file",
}
with open(sys.argv[1], "a") as f:
    f.write(json.dumps(rec) + "\n")
PYEOF

  rm -rf "$cfg_dir" "$variant_dir"
  # repo_dir intentionally left on disk for inspection; the caller's
  # environment (e.g. CI) is responsible for cleaning $OUTPUT_DIR/.. if
  # disk space matters. See README for cleanup guidance.
}

for fixture in "${FIXTURES[@]}"; do
  $STOP && break
  for run_index in $(seq 1 "$RUNS_PER_CELL"); do
    $STOP && break
    for variant in "${VARIANTS[@]}"; do
      run_cell "$fixture" "$variant" "$run_index"
    done
    # End of a completed pair (both variants for this fixture/run_index):
    # apply the per-cell stop rule.
    over_budget="$(python3 -c 'import sys; print(1 if float(sys.argv[1]) > float(sys.argv[2]) else 0)' "$CUMULATIVE_COST" "$BUDGET_USD")"
    if [[ "$over_budget" == "1" ]]; then
      echo "budget exceeded (cumulative \$$CUMULATIVE_COST > \$$BUDGET_USD); stopping after a completed pair" >&2
      STOP=true
    fi
  done
done

python3 "$LIB_DIR/summarize.py" "$RESULTS_JSONL" "$SUMMARY_MD" "$RUNS_PER_CELL"

echo "results: $RESULTS_JSONL" >&2
echo "summary: $SUMMARY_MD" >&2
