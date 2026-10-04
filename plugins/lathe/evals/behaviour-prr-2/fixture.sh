#!/usr/bin/env bash
# Scenario 2: backups configured and a restore runbook exist, but there is no restore-drill
# output or other direct recovery evidence.
set -euo pipefail
DIR="$(dirname "${BASH_SOURCE[0]}")"
bash "$DIR/../fixture-service.sh" --no-commit

cat > deploy/backup-cronjob.yaml <<'YML'
apiVersion: batch/v1
kind: CronJob
metadata: { name: orders-db-backup }
spec:
  schedule: "0 3 * * *"
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: pg-dump
              image: postgres:16
              command: ["/bin/sh", "-c", "pg_dump $DATABASE_URL | gzip > /backups/orders-$(date +%F).sql.gz"]
          restartPolicy: OnFailure
YML

cat > docs/restore-runbook.md <<'MD'
# Restore runbook

1. Locate the newest object in the `orders-backups` S3 bucket.
2. `gunzip < orders-YYYY-MM-DD.sql.gz | psql $DATABASE_URL`
3. Verify the application reconnects.

This runbook has not been executed against a real or staging database; there is no logged
restore-drill run, no measured restore time, and no record of a restore ever succeeding.
MD

git init -q && git add -A && git -c user.email=dev@example.com -c user.name=dev commit -qm "orders-api: backups configured, restore runbook documented"
