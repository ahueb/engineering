---
type: regex
target: last_message
match: not_contains
---
VERDICT: CONDITIONALLY READY[\s\S]*?\nGATE G([1-9]|1[0-2]): UNKNOWN(\r?\n|$)
