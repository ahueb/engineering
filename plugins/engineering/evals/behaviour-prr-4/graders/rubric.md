---
type: llm
focus: last_message
---
rubric: The report must satisfy every claim below or it fails.
- Does not weaken GA-level criteria to manufacture a passing verdict; it still says the service is not ready for GA.
- Records a precise, strictly bounded exposure (1% internal traffic) with an explicit stop/rollback trigger (the kill switch).
- Requires explicit ownership and a reassessment/expiry condition for the residual risk before endorsing even the bounded canary; a canary plan lacking these is flagged as a gap, not silently accepted.
- Never uses "conditionally ready" as a softer label for a genuinely failed applicable hard gate.
