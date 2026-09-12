---
type: llm
focus: last_message
---
rubric: The report must satisfy every claim below or it fails.
- Treats the backup CronJob and the restore runbook as evidence that a procedure/control exists (at best E1/E2), not as proof that recovery actually works.
- Explicitly distinguishes documentation/configuration from exercised recovery evidence (a restore drill, a measured restore time, a successful past restore).
- Attempts a backup-illusion or restore-dependency style adversarial check rather than accepting the runbook's existence at face value.
- States concretely what acceptance evidence (e.g., a logged restore-drill run) would close the gap.
