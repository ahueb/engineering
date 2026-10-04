# Plugin evals

Trigger-quality cases for `production-readiness-review`: ten prompts that should invoke the skill (`prr-trigger-*`) and ten that should not (`prr-no-trigger-*`). Each case has one `tool_used: Skill` grader.

Every `prr-trigger-*` case has a `case.yaml` naming `fixture.sh`, which builds the shared `fixture-service.sh` orders-api repository in the workspace so the readiness question has something to review; pass `--scaffold` (and `--trust-plugin` when not interactive) or the positive cases run against an empty directory and fail for the wrong reason.

```bash
cd plugins/engineering
claude plugin eval . --tag prr-trigger --scaffold --trust-plugin        # positive cases
claude plugin eval . --tag prr-no-trigger                                # negative cases
claude plugin eval . --case 'prr-*' --runs 1 --scaffold --trust-plugin   # full suite, one run each
claude plugin eval . --case 'prr-*' --scaffold --trust-plugin --ablation none --threshold 1.0  # CI gate: fail on any grader miss
```

`cleanup-trigger-*` and `cleanup-no-trigger-*` do the same for `comment-cleanup`: ten prompts that should invoke it and ten that should not, each scaffolded with the comment-guidance review fixture.

    claude plugin eval plugins/engineering --tag cleanup-trigger --scaffold --trust-plugin --ablation none --runs 3 --model claude-sonnet-5-5 --no-publish
    claude plugin eval plugins/engineering --tag cleanup-no-trigger --scaffold --trust-plugin --ablation none --runs 3 --model claude-sonnet-5-5 --no-publish

Negative cases pass trivially on the without-plugin arm; run them with `--ablation none` to make the check meaningful.

Run with the session default model. On a 200K-context model such as Haiku the skill listing overruns its default budget and the least-invoked skills lose their descriptions, so trigger cases fail for a reason unrelated to the description text; `settings.recommended.json` raises `skillListingBudgetFraction` to 0.02 for normal sessions, but eval runs do not read user settings (the eval sandbox loads no user settings, hooks, or other plugins).

Every run is a model call on your account (about 9 USD for the full suite at one run per case). With a path target (`.` from `plugins/engineering`, or `plugins/engineering` from the repository root) raw results land in `plugins/engineering/evals/results/`, which is ignored by git; summarise a run in `RESULTS.md`. Do not target the repository root (`claude plugin eval .` run from the root): the 2026-10-02 run that did so recorded the repository root as its suite root and wrote its results to `<repo>/evals/results/` (now also ignored). Any invocation without `--tag` or `--case` runs all 62 cases under one set of flags. Every suite below needs its own invocation, `--scaffold`, and its own grants; without `--scaffold` the workspaces are empty and the behaviour and comment-guidance results are void.

## Output-behavior (outcome-graded) cases

Eight output-behavior scenarios for the audit itself (green CI is not readiness, backup
documentation is not restore evidence, proxy-metric theater, a properly bounded canary that
should be CONDITIONALLY READY, AI overlay, multi-region falsification, CRA-scope product without a
vulnerability reporting path, and a canary proposal whose kill switch is never wired in) are
described in `../skills/production-readiness-review/references/evals-behavior.md` and
implemented as `behaviour-prr-1` … `behaviour-prr-8`. Each scaffolds its own repository (via
`fixture-service.sh` plus scenario-specific artefacts) and is graded on the report's
machine-checkable `VERDICT:`/`GATE G<n>:` lines, a `repo-evidence` regex that requires the report
to cite one of the paths that scenario's own `fixture.sh` creates, and an `llm` rubric judged one
criterion per grader (`rubric`, `rubric-2`, ...; see "Judge" below) — no reliance on
`tool_used: Skill` alone. `repo-evidence` exists because an audit of an empty workspace
(`VERDICT: NOT READY`, gates UNKNOWN or FAIL) otherwise passes scenarios 1, 2, 3, and 7, as
all four did on 2026-10-02. A report that names a scenario path only to say it is missing would
still satisfy `repo-evidence`; none of 42 empty-workspace reports did.
Run them with grants that exclude `Edit`/`Write` (the audit must stay read-only). The git grants
cover the hardened read-only plumbing the skill uses, but they are not a read-only boundary: a rule
matches any command that starts with its text before the `*`, so it also admits further options (for
example `--ext-diff` or `--output=<file>` after the `diff-tree` prefix), and Claude Code auto-allows
plain read-only `git` forms such as `git status` and `git log` without any grant. The skill's
instructions are what keep the model to the hardened commands:

```bash
cd plugins/engineering
claude plugin eval . --tag behaviour-readiness --scaffold --trust-plugin --ablation none \
  --judge-model sonnet --allow-tools Read Grep Glob "Bash(python3 *)" \
  "Bash(git -c core.fsmonitor=false -c core.hooksPath=/dev/null rev-parse *)" \
  "Bash(git -c core.fsmonitor=false -c core.hooksPath=/dev/null ls-tree *)" \
  "Bash(git -c core.fsmonitor=false -c core.hooksPath=/dev/null diff-tree --no-textconv --no-ext-diff *)" \
  "Bash(git -c core.fsmonitor=false -c core.hooksPath=/dev/null cat-file -t *)" \
  "Bash(git -c core.fsmonitor=false -c core.hooksPath=/dev/null cat-file -s *)" \
  "Bash(git -c core.fsmonitor=false -c core.hooksPath=/dev/null cat-file -p *)" \
  --max-cost-usd 16
```

Before the skill told it to run the probe as its own call, every run on 2026-10-02 and 2026-10-03
(48/48) chained the first call to the bundled `repo_probe.py` with `git` in one Bash call. The 44 that used `git -C <dir> ...` were denied, as was one
that added `echo "exit=$?"; cd ... && git ...`; the 3 that used plain `git status --short | head`
or `git log --stat -3 | head` ran. So the probe ran in 0/21 runs on 2026-10-02 and 3/27 on
2026-10-03, and most reports carry no probe output.
Since the skill runs the probe as its own call, it ran in 24/24 runs. The suite also grants
those hardened git forms, so the skill can run the hardened `git -c ...` commands that tie HEAD to the tagged
release: with `Bash(python3 *)` alone all 28 git calls in one 24-run measurement were denied, and
scenario 4 could not show that `src/` at HEAD matched the release.

`behaviour-comment-cleanup` exercises `/lathe:comment-cleanup` against a small polyglot
repository and asserts that every protected directive comment (lint/type suppressions, build
directives, source-map and bundler magic comments, `@generated` headers) survives byte-identical
while ordinary stale comments are rewritten. It needs `Edit`/`Write` and runs as a separate
invocation with its own budget:

```bash
cd plugins/engineering
claude plugin eval . --case behaviour-comment-cleanup --scaffold --trust-plugin --ablation none \
  --judge-model sonnet --allow-tools Read Grep Glob Skill Edit Write "Bash(python3 *)" --max-cost-usd 6
```

These two invocations are separate on purpose: `--case 'prr-*'` (the trigger-quality suite
above) must never be widened to `behaviour-*` — the `behaviour-*` cases are outcome-graded,
cost far more per run, and need write grants the trigger suite does not.

## Security-reviewer suite

The five `behaviour-security-*` cases run `/lathe:change-review` on an uncommitted diff and grade the merged report. Cases 1, 3, and 4 test detection and exposure reasoning (a public route to a shell command; Redis published on all interfaces by a config-only change; `pull_request_target` running PR code with secrets). Cases 2 and 5 test restraint: an operator-only caller must not be rated High or Critical, and an authorization check applied by a blueprint hook and a scoped base class must not be reported missing. Graders are `tool_used`, `regex`, and one-criterion `llm` rubrics.

```bash
cd plugins/engineering
claude plugin eval . --tag behaviour-security --scaffold --trust-plugin --ablation none --runs 3 \
  --judge-model sonnet --allow-tools Read Grep Glob Skill Agent "Bash(git *)" --max-cost-usd 20 --no-publish
```

## Comment-guidance suite

Nine native cases (`behaviour-comment-cleanup` plus `comment-guidance-review-only`,
`comment-guidance-implementation`, `comment-guidance-plan`, `comment-guidance-change-review`,
`comment-guidance-mechanical`, `comment-guidance-repair`, `comment-guidance-doc-plan`, and
`behaviour-comment-cleanup-reliance`) exercise comment/docstring guidance end to end: explicit
cleanup, natural-language review, implementation, plan-execution, change-review, mechanical rename,
hard-repair, plan-auditor, and a cleanup that must defer a thread-safety comment a caller and a test
rely on. Each is tagged
`comment-guidance-write` or `comment-guidance-read`; `behaviour-comment-cleanup` carries both
`behaviour`/`behaviour-cleanup` and `comment-guidance-write`. Run reads and writes as separate
invocations with separate budgets:

```bash
: "${COMMENT_WRITE_BUDGET_USD:?Set an authorized budget for this invocation}"
: "${COMMENT_SUBJECT_MODEL:?Set the tested parent model}"
: "${COMMENT_JUDGE_MODEL:?Set the tested judge model}"

claude plugin eval plugins/engineering \
  --tag comment-guidance-write --scaffold --trust-plugin \
  --ablation none --runs 3 --threshold 1.0 \
  --model "$COMMENT_SUBJECT_MODEL" --judge-model "$COMMENT_JUDGE_MODEL" \
  --allow-tools Read Grep Glob Skill Agent Edit Write \
    "Bash(python3 *)" "Bash(git *)" \
  --keep-temp --no-publish --max-cost-usd "$COMMENT_WRITE_BUDGET_USD"
```

This grant reaches every write case, so `behaviour-comment-cleanup` (whose own `allowed_tools`
are `Read Grep Glob Skill`) runs here with `Agent`, `Edit`, `Write`, and both Bash patterns;
its separate invocation above grants less. Record which invocation a result came from.

The read cases run one invocation each, because an `--allow-tools` grant reaches every case in
its invocation (it adds the tool even where a case's `allowed_tools` omits it), while a gated
tool a case lists but the invocation does not grant is withheld (the harness prints `not granted
... Bash(git *)`). `comment-guidance-change-review` reviews `git diff`, so only it gets git:

```bash
: "${COMMENT_READ_BUDGET_USD:?Set an authorized budget for each invocation}"
for c in comment-guidance-review-only comment-guidance-doc-plan; do
  claude plugin eval plugins/engineering \
    --case "$c" --scaffold --trust-plugin \
    --ablation none --runs 3 --threshold 1.0 \
    --model "$COMMENT_SUBJECT_MODEL" --judge-model "$COMMENT_JUDGE_MODEL" \
    --allow-tools Read Grep Glob Skill Agent \
    --keep-temp --no-publish --max-cost-usd "$COMMENT_READ_BUDGET_USD"
done
claude plugin eval plugins/engineering \
  --case comment-guidance-change-review --scaffold --trust-plugin \
  --ablation none --runs 3 --threshold 1.0 \
  --model "$COMMENT_SUBJECT_MODEL" --judge-model "$COMMENT_JUDGE_MODEL" \
  --allow-tools Read Grep Glob Skill Agent "Bash(git *)" \
  --keep-temp --no-publish --max-cost-usd "$COMMENT_READ_BUDGET_USD"
```

`tool_used` counts every call the model emits, including calls made inside subagents and calls
that fail: a call to a tool the run withheld (`No such tool available`) and a call the grant
denied both count. So `no-edit`/`no-write`/`no-bash` count attempts, and a `min: 1` grader such as
`unittest-run` passes on a denied attempt. An artifact grader (`tests-pass`, `repair-output-ok`,
`verification-output-present`) shows only that the expected text is in the file, and the
artifacts checker only that the file exists: agents save that output with `Write`, so neither
proves a check ran. The evidence that a check ran is a Bash call in the trace whose result is
not a denial and contains the runner's output. `comment-guidance-review-only` has no `no-bash`
grader: its prompt forbids edits, not commands, and models try `git diff` on its uncommitted
change; `no-edit`/`no-write` and the artifacts checker cover unauthorized edits.
`comment-guidance-doc-plan` keeps `no-bash` because its prompt forbids running tests.

In the eval's don't-ask permission mode with a `Bash(python3 *)` grant, these were denied:
output redirection to a file (`> out.txt`, with or without `2>&1`), a pipe into `tee`, `python`
in place of `python3`, `python3 ... ; echo $?`, and `python3 ... ; git -C <dir> ...` (even with
only read-like git subcommands). A plain `python3 ...` command, including `2>&1`, ran, as did a
plain `git status --short` and the compounds `python3 ... ; git status --short | head; git
rev-parse HEAD` and `python3 ... ; git log --stat -3 | head -50; ls -la` (Claude Code 2.1.288). The implementation, plan, and repair cases ask
for test output in a file, so the agent has to run the plain command and save its output with
`Write`. A run whose only verification attempt is denied and that then stops is an unverified
trial under the incomplete-run rule below, not a pass or a fail.

Judge: in Claude Code 2.1.288 (read from the installed CLI) an `llm` grader sends the judge model the criterion and the focus
text and asks for exactly one word, PASS or FAIL, under a "strict, terse evaluation judge"
system prompt; it takes three votes and passes on a majority. The judge gives no reasons, and
none are recorded. A `trace` focus shows only the first 12 and last 12 trace messages. Asked for
a whole multi-bullet rubric at once, this judge returned FAIL on reports that it passed on every
bullet when each bullet was its own grader (9/9 votes on three `comment-guidance-review-only`
reports, and two `behaviour-prr-6` reports), and PASS on a `behaviour-prr-4` report that failed
one bullet 3/3 judged alone, a report whose whole rubric had drawn FAIL FAIL FAIL in the eval
run. These diagnostic cases (2026-10-03) fed the recorded evidence through a file `focus`, not
`last_message`. Each `llm` rubric is therefore split into one grader per bullet (`rubric`,
`rubric-2`, ...), each with the shared ground truth,
and a case passes only when every one passes. Splitting does not make the judge reliable: on
2026-10-03 it still failed single-bullet graders whose criterion the evidence satisfies (two
`behaviour-prr-1` reports with all 12 gates rated, one `behaviour-prr-6` report with no E3/E4
rating), and split votes 4 of 9 FAIL on three identical `comment-guidance-repair` files under a
criterion that named a function docstring the file lacks (see `RESULTS.md`). The
`behaviour-prr-1` bullet is now the regex graders `gate-lines` and `gate-evidence`, and the repair
bullet is reworded. Wording matters as much: a `behaviour-prr-6` `rubric-5` that named the HA and
multi-region claims and also excluded E3 ratings on gate FAILs made the judge fail all three reports
in one run, none of which rated the claim above E1; replayed as final messages, the same reports
passed under the current, shorter criterion. Splitting can also drop an exception one
bullet made to another: `comment-guidance-mechanical`'s hardware-sentence bullet is now the regex
`hardware-sentence-unchanged`, and its `prose-renamed` grader states that sentence as the rename's
one exception. Write criteria the judge can decide from the focus alone (state any before-state or plan
content inline), prefer a regex grader for anything mechanical, and re-check every `llm` FAIL
against the evidence before recording it. Calibrated on 2026-10-03 against 25 hand-verified
judgments (each fed through a file focus): Sonnet 5.5 made 0 errors and Opus 5.5 made 1, so the
suite keeps `claude-sonnet-5-5` as judge. That bounds how the judge reads a criterion, not its error
rate in a run: judging the agent's final message (`last_message`) in eval runs, the same judge
failed 3 of that set's 9 PASS items (the reports above), so every `llm` FAIL is still rechecked.
`python3 scripts/eval_recheck.py <results-dir>/aggregate-result.json` replays every failed `llm`
grader with a judge that must give a reason per criterion and lists disagreements as "NEEDS
REVIEW"; it calls `claude -p` once per failure and never changes a recorded score. Add `--include-passes --grader <glob>` to recheck the judgments the harness passed as well, which is how false passes are found; the recorded results use it for scenario 4's `rubric-4` and scenario 5's `rubric` and `rubric-4`.

A `regex` grader with `target: trace` sees the whole trace as compact JSON, one message per line;
a subagent's messages carry `"parent_tool_use_id":"toolu_..."` and the parent's carry `null`.
`comment-guidance-plan` uses that: `bulk-implementer-instructed` requires at least two
`bulk-implementer` dispatches to carry the no-build/no-test instruction, and `no-worker-test-command`
fails the case if a subagent's own Bash call, run or denied, starts a test, lint, or commit command
(`python3 -m unittest`, `-m pytest`, or `-m py_compile`, `pytest`, `node --test`, `npm test`, `eslint`,
or `git commit`) at the start of the command or after `;`, `&&`, `||`, `|`, `(`, or a newline,
optionally after variable assignments, `env`, `time`, `nice`, or `timeout <n>`, and with interpreter
options such as `-X dev` before `-m`. A mention such as
`which pytest`, `grep pytest`, or reading `pytest.ini` does not count; a test file run directly or
another linter is not detected. Measured workers have made only read-only Bash calls, so it has not
been exercised on a real violation. `tests-ran` (implementation, plan, and repair cases) pairs a Bash
call whose command runs `-m unittest` with that call's own result, matched by tool-call id, whether
the tests passed or failed, and requires unittest's "Ran N tests" line with N of at least 1 in that
result, so reading, searching, or printing a stored log such as the repair case's
`failed_check.txt` does not satisfy it. In the plan and implementation cases the run must be the parent's; in the
repair case the `hard-repair` subagent's run counts. `probe-ran` (every readiness scenario) matches the readiness
probe's own JSON output in a tool result.

Prerequisites: Claude Code >= 2.1.273, verified locally for `--keep-temp` support; on Linux the
`Bash` grants above additionally require bubblewrap and socat to be installed for the eval
sandbox to run bash tools at all. The budget variables above are authorized-budget inputs you
must set explicitly; they are not recommended dollar amounts.

`--keep-temp` retains each run's scaffold workspace instead of deleting it. Retaining the
workspace path is not itself a passing result: for every actual retained workspace, run

```bash
python3 scripts/comment_guidance_checks.py artifacts \
  --case "$CASE_ID" \
  --fixtures plugins/engineering/evals/comment-guidance-support/fixtures.json \
  --manifest plugins/engineering/evals/comment-guidance-support/manifest.json \
  --candidate "$RETAINED_WORKSPACE" \
  --report "$TRUSTED_REPORT_PATH"
```

from the repository root, against each retained workspace, before treating that trial as
verified. The report's `artifact_status` covers only the deterministic checks this helper
implements; `semantic_status` is always `REQUIRES_REVIEW` and is never a substitute for reading
the `llm`-graded findings.

Trust boundary: `--trust-plugin` authorizes the inspected plugin/scaffold code in this
repository, not an arbitrary untrusted repository. Run this suite in a disposable config with no
unrelated secrets, no production credentials, and no side-effecting real integrations; a
read-only or bounded-write prompt is not itself a security sandbox.

The run's home directory is the harness's, not yours, but it is not empty of links to yours: on
2026-10-02 and 2026-10-03 every retained run (65 checked) had `home/.aws/cli/cache` as a symlink to the invoking user's real
`~/.aws/cli/cache`, beside a harness `.gitconfig` (`Plugin Eval`, `eval@example.invalid`). Agents
saw `../.aws/` in `git status`. Probe runs could list the link (`Bash(ls *)`) but were denied
traversing it: Bash `ls` through the link, and `Glob` and `Read` both through the link and by
absolute path, while
`Read` of a missing file in the sandbox's own `../.aws/cli/` was permitted; unrestricted Bash was
not tested.

Incomplete-run handling: a cost-limit abort, a denied required tool, a missing subagent trace, or
a retained workspace that cannot be located is an **unverified** trial, not a passing or failing
one — do not count it toward a pass rate and do not silently drop it from the reported
denominator.

`directives-intact`-style and `rubric`-style graders in these cases grade the *contents of
scaffolded and edited files after the run* (via `focus`/`target: { source: file, path: ... }`),
not the agent's final message; a final-message grader here is retained only for honest self-
reporting of scope and exceptions, not as evidence of artifact correctness.
