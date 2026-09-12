---
type: regex
target: last_message
match: contains
---
(^|\n)VERDICT: (NOT READY|CONDITIONALLY READY)(\r?\n|$)
