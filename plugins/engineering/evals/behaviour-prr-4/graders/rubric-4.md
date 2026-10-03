---
type: llm
focus: last_message
---
rubric: The report must satisfy the claim below or it fails.
- If the verdict is CONDITIONALLY READY, every item the report says must be done or confirmed before the canary starts (a blocker, precondition, or pre-launch check for the canary itself, not for GA) is a check of production state that cannot be evidenced before deployment, such as a migration applied in production or alert rules loaded there, and names an owner and the evidence that closes it; and the report states that if any such check fails the verdict is NOT READY. It fails if such an item could be evidenced before deployment from any source (the repository, staging, CI, the artifact registry, the paging or access systems; for example missing configuration, an untested code path, a staging drill not yet run, an image attestation, or an on-call roster), or lacks an owner or closing evidence. A report with no such items, or with a NOT READY verdict, passes.
