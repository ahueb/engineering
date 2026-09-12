#!/usr/bin/env bash
# Plugin PreToolUse guard (Bash|PowerShell matcher). Allows every agent except
# engineering:auditor unrestricted; for engineering:auditor, restricts the
# command to a small read-only allowlist (hooks/readonly-allowlist.txt),
# tokenised with shell-style unquoting (shlex.split), and denies any command
# containing a bare '$', a backslash, a backtick, '<', '>', or unbalanced '&',
# to guard against accidental mutation during an audit. Fails closed: if
# python3 is unavailable, the python program crashes, or the input JSON does
# not parse, the guard denies engineering:auditor (and allows every other
# agent, since agent_type cannot be determined). Unquoted brace, glob, and
# tilde characters are denied because the shell expands them after the guard
# has seen the text. This is not a sandbox
# against a hostile repository: obfuscated commands, repository-controlled
# runners, and interpreters are out of scope (see README/SECURITY).
# bash 3.2 compatible: reads stdin once, hands it to a single python3 program
# that does the actual parsing and decision.
set -u

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
ALLOWLIST="${PLUGIN_ROOT}/hooks/readonly-allowlist.txt"

# Read stdin with a bash builtin (not the external `cat`), so a PATH override that hides
# every external command (the fail-closed test in ci.sh) still lets this script see its
# input and reach the fail-closed fallback below.
input=""
IFS= read -r -d '' input || true

out=""
rc=1
if command -v python3 >/dev/null 2>&1; then
  set +e
  out="$(printf '%s' "$input" | python3 -c '
import json, re, shlex, sys

def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(3)

    agent_type = data.get("agent_type", "") or ""
    if not re.match(r"^engineering:auditor$", agent_type):
        sys.exit(0)

    def deny(reason):
        out = {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": "readonly guard: " + reason,
            }
        }
        print(json.dumps(out))
        sys.exit(0)

    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict) or not isinstance(tool_input.get("command"), str):
        deny("no command string in tool_input")
    command = tool_input["command"]

    if not command.strip():
        sys.exit(0)

    if ">" in command:
        deny("contains \x27>\x27")
    if "<" in command:
        deny("contains \x27<\x27")
    if "`" in command:
        deny("contains a backtick")
    if "$" in command:
        deny("contains \x27$\x27")
    if "\\" in command:
        deny("contains a backslash")
    if "&" in command.replace("&&", ""):
        deny("contains \x27&\x27 outside \x27&&\x27")

    # The shell expands braces, globs, and tildes after the guard has looked at
    # the text, so an unquoted metacharacter could turn an innocent-looking
    # token into a forbidden one (sort -{u,o} out a). Quoted ones are inert.
    quote = ""
    for ch in command:
        if quote:
            if ch == quote:
                quote = ""
            continue
        if ch in "\x27\x22":
            quote = ch
        elif ch in "{}*?[]~":
            deny("unquoted \x27" + ch + "\x27; quote it or drop it")

    allowlist_path = sys.argv[1] if len(sys.argv) > 1 else ""
    entries = {}
    try:
        with open(allowlist_path) as f:
            for line in f:
                line = line.rstrip("\n")
                if not line or line.startswith("#"):
                    continue
                parts = line.split("|")
                if len(parts) < 4:
                    continue
                token = parts[0]
                verb_whitelist = parts[1].split()
                forbidden_regex = "|".join(parts[2:-1])
                max_operands_raw = parts[-1].strip()
                max_operands = int(max_operands_raw) if max_operands_raw else None
                entries[token] = (verb_whitelist, forbidden_regex, max_operands)
    except Exception:
        deny("allowlist unreadable")

    simple_commands = [c for c in re.split(r"\|\||&&|[;|\n]", command) if c.strip()]
    if not simple_commands:
        sys.exit(0)

    for simple in simple_commands:
        try:
            tokens = shlex.split(simple, posix=True)
        except ValueError:
            deny("unbalanced quoting")
        if not tokens:
            continue
        first = tokens[0]
        if first not in entries:
            deny("token \x27" + first + "\x27 not allowed")
        verb_whitelist, forbidden_regex, max_operands = entries[first]
        rest = tokens[1:]
        if verb_whitelist:
            if not rest or rest[0] not in verb_whitelist:
                deny(first + ": verb not allowed")
        if forbidden_regex:
            for arg in rest:
                if re.search(forbidden_regex, arg):
                    deny(first + ": forbidden argument \x27" + arg + "\x27")
        if max_operands is not None:
            operand_count = sum(1 for a in rest if not a.startswith("-"))
            if operand_count > max_operands:
                deny(first + ": too many operands")

    sys.exit(0)

main()
' "$ALLOWLIST")"
  rc=$?
  set -u
fi

if [ "$rc" -eq 0 ]; then
  [ -n "$out" ] && printf '%s\n' "$out"
  exit 0
fi

# Fail closed: python3 was missing, or the python program crashed (including
# an unparseable-JSON exit 3). We cannot determine agent_type reliably, so
# fall back to a substring check on the raw input; only engineering:auditor
# is denied, every other agent is allowed as before.
case "$input" in
  *'"agent_type"'*'"engineering:auditor"'*)
    printf '%s\n' '{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny", "permissionDecisionReason": "readonly guard: guard unavailable, denying for engineering:auditor"}}'
    ;;
esac

exit 0
