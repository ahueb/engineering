#!/usr/bin/env python3
"""Parse a stream-json transcript from a single plan-execution benchmark run.

Usage: parse_run.py <log-file> <test-command-substring>

Prints one JSON object to stdout:
  {
    "fan_out": bool,       # an Agent/Task tool_use was observed
    "cost_usd": float|null,# total_cost_usd from the final result event
    "repair_rounds": int,  # Bash invocations of the test command after the first
    "num_turns": int|null,
    "duration_ms": int|null,
    "is_error": bool|null,
    "raw_result_event": object|null
  }

Malformed or non-JSON lines are skipped (stream-json is newline-delimited
JSON; partial writes or stray stderr mixed into the file are tolerated).
"""
import json
import sys


def main():
    if len(sys.argv) != 3:
        print("usage: parse_run.py <log-file> <test-command-substring>", file=sys.stderr)
        sys.exit(2)
    log_path, test_cmd = sys.argv[1], sys.argv[2]

    fan_out = False
    test_cmd_invocations = 0
    result_event = None

    try:
        with open(log_path, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict):
                    continue

                etype = event.get("type")

                if etype == "assistant":
                    message = event.get("message") or {}
                    content = message.get("content") or []
                    if isinstance(content, list):
                        for item in content:
                            if not isinstance(item, dict):
                                continue
                            if item.get("type") != "tool_use":
                                continue
                            name = item.get("name")
                            if name in ("Agent", "Task"):
                                fan_out = True
                            if name == "Bash":
                                tool_input = item.get("input") or {}
                                command = tool_input.get("command") or ""
                                if test_cmd and test_cmd in command:
                                    test_cmd_invocations += 1

                if etype == "result":
                    result_event = event
    except FileNotFoundError:
        pass

    repair_rounds = max(0, test_cmd_invocations - 1)

    cost_usd = None
    num_turns = None
    duration_ms = None
    is_error = None
    if result_event is not None:
        cost_usd = result_event.get("total_cost_usd", result_event.get("cost_usd"))
        num_turns = result_event.get("num_turns")
        duration_ms = result_event.get("duration_ms")
        is_error = result_event.get("is_error")

    out = {
        "fan_out": fan_out,
        "cost_usd": cost_usd,
        "repair_rounds": repair_rounds,
        "num_turns": num_turns,
        "duration_ms": duration_ms,
        "is_error": is_error,
        "raw_result_event": result_event,
    }
    print(json.dumps(out))


if __name__ == "__main__":
    main()
