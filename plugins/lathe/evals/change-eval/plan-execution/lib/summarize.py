#!/usr/bin/env python3
"""Read results.jsonl and write a markdown summary applying the pre-registered decision rule.

Usage: summarize.py <results.jsonl> <out.md> <runs-per-cell>

Decision rule (pre-registered before the run): adopt the bounded-check variant
only if every completed fixture pair shows equal or better correctness on
every run and the variant's worst-run cost is within 20% of the current
variant's worst-run cost for that fixture; an incomplete pair, or a
within-cell cost spread above 20%, makes the result "no decision".
"""
import json
import sys
from collections import defaultdict


def load(path):
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            records.append(json.loads(line))
    return records


def spread_ok(costs):
    """within-cell cost spread <= 20%: (max-min)/min <= 0.20"""
    valid_costs = [c for c in costs if c is not None]
    if not valid_costs:
        return None
    lo, hi = min(valid_costs), max(valid_costs)
    if lo <= 0:
        return None
    return (hi - lo) / lo <= 0.20


def main():
    if len(sys.argv) != 4:
        print("usage: summarize.py <results.jsonl> <out.md> <runs-per-cell>", file=sys.stderr)
        sys.exit(2)
    results_path, out_path, runs_per_cell = sys.argv[1], sys.argv[2], int(sys.argv[3])

    records = load(results_path)

    # cell = (fixture, variant) -> list of records ordered by run_index
    cells = defaultdict(dict)
    fixtures_order = []
    for r in records:
        fixture, variant, run_index = r["fixture"], r["variant"], r["run_index"]
        if fixture not in fixtures_order:
            fixtures_order.append(fixture)
        cells[(fixture, variant)][run_index] = r

    lines = []
    lines.append("# plan-execution benchmark: current vs. bounded-check")
    lines.append("")
    lines.append(
        "Decision rule (pre-registered before the run): adopt the bounded-check variant "
        "only if every completed fixture pair shows equal or better correctness "
        "on every run and the variant's worst-run cost is within 20% of the "
        "current variant's worst-run cost for that fixture; an incomplete pair, "
        "or a within-cell cost spread above 20%, makes the result \"no decision\"."
    )
    lines.append("")

    fixture_verdicts = {}

    for fixture in fixtures_order:
        lines.append(f"## Fixture: {fixture}")
        lines.append("")
        lines.append("| variant | run | valid (fan-out) | tests passed | cost (USD) | wall-clock (s) | repair rounds | diff-stat lines |")
        lines.append("|---|---|---|---|---|---|---|---|")

        cell_data = {}
        for variant in ("current", "bounded-check"):
            cell = cells.get((fixture, variant), {})
            for run_index in sorted(cell):
                r = cell[run_index]
                lines.append(
                    f"| {variant} | {run_index} | {r.get('valid')} | "
                    f"{r.get('tests_passed')} | {r.get('cost_usd')} | "
                    f"{r.get('wall_clock_s')} | {r.get('repair_rounds')} | "
                    f"{r.get('diff_stat_lines')} |"
                )
            cell_data[variant] = cell

        lines.append("")

        current_cell = cell_data.get("current", {})
        bounded_cell = cell_data.get("bounded-check", {})

        complete = (
            len(current_cell) == runs_per_cell
            and len(bounded_cell) == runs_per_cell
            and all(current_cell[i].get("valid") for i in current_cell)
            and all(bounded_cell[i].get("valid") for i in bounded_cell)
        )

        if not complete:
            verdict = "no decision (incomplete pair)"
        else:
            current_costs = [current_cell[i].get("cost_usd") for i in sorted(current_cell)]
            bounded_costs = [bounded_cell[i].get("cost_usd") for i in sorted(bounded_cell)]

            current_spread_ok = spread_ok(current_costs)
            bounded_spread_ok = spread_ok(bounded_costs)

            correctness_ok = all(
                bool(bounded_cell[i].get("tests_passed"))
                >= bool(current_cell[i].get("tests_passed"))
                for i in sorted(current_cell)
                if i in bounded_cell
            )

            current_valid_costs = [c for c in current_costs if c is not None]
            bounded_valid_costs = [c for c in bounded_costs if c is not None]

            if not current_valid_costs or not bounded_valid_costs:
                verdict = "no decision (missing cost data)"
            else:
                current_worst = max(current_valid_costs)
                bounded_worst = max(bounded_valid_costs)
                cost_within_20pct = (
                    current_worst > 0
                    # One-sided: a cheaper variant always satisfies the cost bound.
                    and (bounded_worst - current_worst) / current_worst <= 0.20
                )

                if current_spread_ok is False or bounded_spread_ok is False:
                    verdict = "no decision (within-cell cost spread > 20%)"
                elif not correctness_ok:
                    verdict = "reject bounded-check (worse correctness on at least one run)"
                elif cost_within_20pct:
                    verdict = "adopt bounded-check for this fixture"
                else:
                    verdict = (
                        "no decision (worst-run cost not within 20%: "
                        f"current={current_worst:.4f}, bounded-check={bounded_worst:.4f})"
                    )

        fixture_verdicts[fixture] = verdict
        lines.append(f"**Fixture verdict:** {verdict}")
        lines.append("")

    lines.append("## Overall")
    lines.append("")
    if not fixture_verdicts:
        lines.append("No results recorded.")
    elif all(v == "adopt bounded-check for this fixture" for v in fixture_verdicts.values()):
        lines.append(
            "**Adopt bounded-check.** Every fixture shows equal or better "
            "correctness on every run and worst-run cost within 20%."
        )
    elif any("no decision" in v for v in fixture_verdicts.values()):
        lines.append(
            "**No decision.** At least one fixture is incomplete, has a "
            "within-cell cost spread above 20%, or lacks cost data; see "
            "per-fixture verdicts above."
        )
    else:
        lines.append(
            "**Reject bounded-check.** At least one fixture shows worse "
            "correctness on at least one run; see per-fixture verdicts above."
        )

    with open(out_path, "w") as f:
        f.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
