---
type: llm
focus: last_message
---
rubric: The report must satisfy the claim below or it fails.
- If the verdict is CONDITIONALLY READY, every item the report says must be done or confirmed before the canary starts (a blocker, precondition, or pre-launch check for the canary itself, not for GA) is a check of production state that cannot be evidenced before deployment, such as a migration applied in production or alert rules loaded there, and names an owner and the evidence that closes it. It fails if such an item is evidence that could be produced now from the repository or staging (for example missing configuration, an untested code path, or an unrun drill), or lacks an owner or closing evidence. A report with no such items, or with a NOT READY verdict, passes.
