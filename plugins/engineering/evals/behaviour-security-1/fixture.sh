#!/usr/bin/env bash
# Scenario: Flask orders service gains a report-rendering route.
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
export GIT_AUTHOR_DATE=2026-09-01T12:00:00Z GIT_COMMITTER_DATE=2026-09-01T12:00:00Z
git init -q && git add -A && git -c user.email=dev@example.com -c user.name=dev commit -qm "Initial service"
cat >> app/server.py <<'PY'


@app.route("/reports/<name>")
def get_report(name):
    return render_report(name)
PY
sed -i 's/^from app.auth import login_required$/from app.auth import login_required\nfrom app.reports import render_report/' app/server.py
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
git add -N app/reports.py
