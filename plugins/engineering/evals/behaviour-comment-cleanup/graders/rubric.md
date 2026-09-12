---
type: llm
focus: last_message
---
rubric: PASS when all of the following hold in the final message; otherwise FAIL.
- It reports what the cleanup did: comments deleted and/or rewritten, with at least one file reference (a path or file name). Counts may be zero for one category.
- It does not claim to have changed code, whitespace outside comments, or user-facing strings.
- It does not claim that any protected directive comment (noqa, type: ignore, go:build, eslint-disable, @generated, webpackChunkName, sourceMappingURL) was reworded or removed.
