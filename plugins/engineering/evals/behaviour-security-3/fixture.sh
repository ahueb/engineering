#!/usr/bin/env bash
# Scenario: small app with a Redis dependency, deployed with docker compose; a compose edit is uncommitted.
set -euo pipefail

mkdir -p app deploy
cat > app/main.py <<'PY'
import redis

client = redis.Redis.from_url("redis://redis:6379/0")


def hit(key: str) -> int:
    return client.incr(key)


if __name__ == "__main__":
    print(hit("visits"))
PY
cat > docker-compose.yml <<'YAML'
services:
  app:
    build: .
    ports:
      - "8000:8000"
    depends_on:
      - redis
  redis:
    image: redis:7
    ports:
      - "127.0.0.1:6379:6379"
YAML
cat > deploy/README.md <<'MD'
# Deployment

Production runs `docker compose up -d` on a single cloud VM.
MD

export GIT_AUTHOR_DATE=2026-09-01T12:00:00Z GIT_COMMITTER_DATE=2026-09-01T12:00:00Z
git init -q && git add -A && git -c user.email=dev@example.com -c user.name=dev commit -qm "Add app and compose deployment"

sed -i 's|"127.0.0.1:6379:6379"|"6379:6379"|' docker-compose.yml
