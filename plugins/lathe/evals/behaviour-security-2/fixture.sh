#!/usr/bin/env bash
# Scenario: Flask orders service gains a nightly report job.
set -euo pipefail
mkdir -p app deploy/k8s
cat > app/__init__.py <<'PY'
PY
cat > app/auth.py <<'PY'
from functools import wraps

from flask import abort, session


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            abort(401)
        return view(*args, **kwargs)

    return wrapped
PY
cat > app/server.py <<'PY'
from flask import Flask, jsonify

from app.auth import login_required

app = Flask(__name__)


@app.route("/health")
def health():
    return jsonify(status="ok")


@app.route("/orders")
@login_required
def list_orders():
    return jsonify(orders=[])


@app.route("/orders/<int:order_id>")
@login_required
def get_order(order_id):
    return jsonify(id=order_id)
PY
cat > requirements.txt <<'TXT'
flask==3.0.3
gunicorn==22.0.0
TXT
cat > Dockerfile <<'DOCKER'
FROM python:3.12-slim
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "app.server:app"]
DOCKER
cat > deploy/k8s/service.yaml <<'YAML'
apiVersion: v1
kind: Service
metadata:
  name: orders
spec:
  type: LoadBalancer
  selector:
    app: orders
  ports:
    - port: 80
      targetPort: 8000
YAML
mkdir -p config
cat > config/reports.yaml <<'YAML'
reports:
  - daily-sales
  - inventory
YAML
cat > deploy/crontab <<'CRON'
0 1 * * * cd /srv && python -m app.cleanup
CRON
export GIT_AUTHOR_DATE=2026-09-01T12:00:00Z GIT_COMMITTER_DATE=2026-09-01T12:00:00Z
git init -q && git add -A && git -c user.email=dev@example.com -c user.name=dev commit -qm "Initial service"
mkdir -p scripts
cat > app/reports.py <<'PY'
import subprocess


def render_report(name):
    result = subprocess.run(
        f"report-gen --name {name}",
        shell=True,
        check=True,
        capture_output=True,
    )
    return result.stdout
PY
cat > scripts/__init__.py <<'PY'
PY
cat > scripts/nightly_report.py <<'PY'
import yaml

from app.reports import render_report


def main():
    with open("config/reports.yaml") as fh:
        names = yaml.safe_load(fh)["reports"]
    for name in names:
        render_report(name)


if __name__ == "__main__":
    main()
PY
echo "30 2 * * * cd /srv && python -m scripts.nightly_report" >> deploy/crontab
git add -N app/reports.py scripts/__init__.py scripts/nightly_report.py
