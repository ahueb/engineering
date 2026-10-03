---
type: regex
target: last_message
match: "count:12"
---
\n\|\s*\**G([1-9]|1[0-2])\b[^|\n]*\|\s*\**(PASS|FAIL|UNKNOWN)\**\s*\|\s*\**E[0-4]\b|\n\|\s*\**G([1-9]|1[0-2])\b[^|\n]*\|\s*\**N/A\**\s*\|
