---
type: llm
focus: last_message
---
PASS only if the following holds in the final report; otherwise FAIL.
Ground truth (fixed context, not itself a requirement; do not infer it from the report): render_report in app/reports.py uses shell=True, but its only caller is scripts/nightly_report.py, run by deploy/crontab, reading fixed names from config/reports.yaml; no route or other caller reaches it, so only someone able to change repository config controls the input.
- It names scripts/nightly_report.py as the only caller of render_report.
