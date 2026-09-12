---
type: llm
focus: last_message
---
rubric: The report must satisfy every claim below or it fails.
- Explicitly challenges code coverage percentage as a standalone correctness proxy rather than treating 95% coverage as evidence of readiness.
- Explicitly challenges the single SAST scanner's clean result as insufficient for security assurance, and flags the absence of authorization/business-logic abuse-case testing.
- Requires p95/p99 or other tail/peak-load evidence rather than accepting the average-latency figure alone as performance evidence.
- Identifies the missing migration-rollback evidence as a release/reversion-safety gap ("rollback fiction") rather than accepting the migration as safe by default.
- Does not let the high coverage, clean scan, or good average latency compensate for these gaps.
