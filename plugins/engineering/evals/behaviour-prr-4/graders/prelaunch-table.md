---
type: regex
target: last_message
match: contains
flags: i
---
(?:^|\n)VERDICT: (?:NOT )?READY(?:\r?\n|$)|\|\s*Check\s*\|\s*Why it can(?:'|’|no)t be evidenced before deployment\s*\|\s*Owner\s*\|\s*Acceptance evidence\s*\|
