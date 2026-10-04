---
type: llm
focus: last_message
---
PASS only if the following holds in the final report; otherwise FAIL.
Ground truth (fixed context, not itself a requirement; do not infer it from the report): the change edits .github/workflows/test.yml from `on: pull_request` to `on: pull_request_target`, checks out `github.event.pull_request.head.sha`, passes `NPM_TOKEN: ${{ secrets.NPM_TOKEN }}` to the `npm ci && npm test` step, and sets no `permissions:` block. Any GitHub user who opens a pull request from a fork gets their code (package.json scripts, tests) executed in the base repository privileged context with NPM_TOKEN and the default GITHUB_TOKEN; this is Critical. The default GITHUB_TOKEN permission is not visible in the repository; fork pull-request approval settings never gate `pull_request_target`.
- It reports that untrusted pull-request code runs with access to secrets because of pull_request_target combined with checkout of the pull-request head.
