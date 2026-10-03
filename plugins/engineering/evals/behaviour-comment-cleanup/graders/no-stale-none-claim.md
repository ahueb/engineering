---
type: regex
target:
  source: file
  path: src/py/contracts.py
match: not_contains
flags: i
---
returns None when
