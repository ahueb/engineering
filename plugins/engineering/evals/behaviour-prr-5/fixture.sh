#!/usr/bin/env bash
# Scenario 5: an AI-enabled service. Normal web-service controls are strong (from the shared
# fixture), but model versioning, evaluation slices, prompt-injection/tool-abuse tests,
# provider fallback, and cost ceilings are not evidenced.
set -euo pipefail
DIR="$(dirname "${BASH_SOURCE[0]}")"
bash "$DIR/../fixture-service.sh" --no-commit

cat > src/summarize.js <<'JS'
// Calls the model provider to summarize an order note. No pinned model version, no retry to a
// fallback provider, and no per-request or per-day cost ceiling.
const client = require('some-llm-sdk');
async function summarizeNote(note) {
  const res = await client.chat({ model: 'latest', messages: [{ role: 'user', content: note }] });
  return res.choices[0].message.content;
}
module.exports = { summarizeNote };
JS

cat > docs/ai-notes.md <<'MD'
# AI feature notes
`summarizeNote` calls the configured provider with `model: "latest"` (no pinned version).
There is no evaluation suite over labeled summarization slices, no prompt-injection or
tool-abuse test suite, no fallback provider if the primary is down, and no cost ceiling or
budget alert on model spend.
MD

git init -q && git add -A && git -c user.email=dev@example.com -c user.name=dev commit -qm "orders-api: adds an AI-enabled note summarization feature"
