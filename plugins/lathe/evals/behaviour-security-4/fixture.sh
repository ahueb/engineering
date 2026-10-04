#!/usr/bin/env bash
# Scenario: small Node package with a test workflow and an .npmrc that reads NPM_TOKEN; a workflow edit is uncommitted.
set -euo pipefail

mkdir -p test .github/workflows
cat > package.json <<'JSON'
{
  "name": "tinylib",
  "version": "1.0.0",
  "main": "index.js",
  "scripts": {
    "test": "node test/run.js"
  }
}
JSON
cat > package-lock.json <<'JSON'
{
  "name": "tinylib",
  "version": "1.0.0",
  "lockfileVersion": 3,
  "requires": true,
  "packages": {
    "": {
      "name": "tinylib",
      "version": "1.0.0"
    }
  }
}
JSON
cat > index.js <<'JS'
module.exports.add = (a, b) => a + b;
JS
cat > test/run.js <<'JS'
const assert = require("assert");
const { add } = require("../index.js");

assert.strictEqual(add(1, 2), 3);
console.log("ok");
JS
cat > .npmrc <<'NPMRC'
//registry.npmjs.org/:_authToken=${NPM_TOKEN}
NPMRC
cat > .github/workflows/test.yml <<'YAML'
name: test
on: pull_request
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci && npm test
YAML

export GIT_AUTHOR_DATE=2026-09-01T12:00:00Z GIT_COMMITTER_DATE=2026-09-01T12:00:00Z
git init -q && git add -A && git -c user.email=dev@example.com -c user.name=dev commit -qm "Add package and test workflow"

cat > .github/workflows/test.yml <<'YAML'
name: test
on: pull_request_target
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          ref: ${{ github.event.pull_request.head.sha }}
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: npm ci && npm test
        env:
          NPM_TOKEN: ${{ secrets.NPM_TOKEN }}
YAML
