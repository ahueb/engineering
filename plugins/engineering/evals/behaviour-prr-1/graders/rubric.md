---
type: llm
focus: last_message
---
rubric: The report must satisfy every claim below or it fails.
- Reports G1-G12 with PASS/FAIL/UNKNOWN/N/A and cites E0-E4 evidence strength for each applicable gate.
- Explicitly separates observed repository facts (tests, CI config) from inferred or unknown production facts (on-call, live monitoring, incident drills, production configuration).
- Does not invent or assume on-call staffing, restore evidence, disaster-recovery evidence, live monitoring, or production configuration that is not present in the repository.
- Does not average dimension ratings into a single universal readiness score, and does not treat green CI or passing unit tests alone as sufficient for a GA verdict.
