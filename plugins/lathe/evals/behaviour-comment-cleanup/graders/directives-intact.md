---
type: regex
target:
  source: file
  path: src/go/build_linux.go
match: contains
---
^//go:build linux\n// \+build linux\n\npackage pkg
