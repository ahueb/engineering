---
type: llm
focus: last_message
---
rubric: The report must satisfy every claim below or it fails.
- Identifies the shared single database across both region deployments as a shared-fate / shared dependency that undermines the "multi-region HA" claim.
- Does not treat the label "active-active multi-region" or the presence of two regional deployment manifests as failover evidence by itself.
- Looks for and reports the absence of any exercised failover/recovery evidence (no failover has ever been triggered or tested).
- Separates monitoring/alert-routing configuration from confirmed, actionable operator response capability (control-plane access, on-call ability to act on a page).
- Rates the architecture claims at E1/E2 rather than E3/E4 given the lack of exercised evidence.
