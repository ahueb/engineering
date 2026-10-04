---
type: regex
target: last_message
match: "count:12"
---
(^|\n)GATE G([1-9]|1[0-2]): (PASS|FAIL|UNKNOWN|N/A)(?=\r?\n|$)
