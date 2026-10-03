# Trigger eval results

Recorded from `claude plugin eval . --case 'prr-*' --runs 1 --ablation none --scaffold --trust-plugin -j 4` (2026-09-12 rows; the 2026-10-02 row records its own invocation).

| Run date (UTC) | Claude Code | Plugin | Cases | Passed | Cost (USD) | Notes |
|---|---|---|---:|---:|---:|---|
| 2026-10-03 | 2.1.288 | 2.10.0 + this release's tree | 20 | 20 | 7.17 | 3 runs per case, `--ablation none`, `--scaffold`, eval model claude-sonnet-5-5. Positive prompts invoked the skill in 30/30 runs, negative prompts in 0/30 |
| 2026-10-02 | 2.1.288 | 2.10.0 | 20 | 19 | 14.57 | 3 runs per case, `--ablation with-without`, no scaffold, eval model the session default (not recorded in the result). With-plugin arm: positive prompts invoked the skill in 29/30 runs, negative prompts in 0/30; without-plugin arm: 0/30 positive. The one miss is prr-trigger-05 ("Judge this PR as a release candidate") on an empty workspace; its trace was not kept, so the cause, the 2.5.0 row's "nothing to review", is inferred. Run from the repository root as one 35-case invocation; its behaviour and comment-guidance results are void (empty workspaces, no tool grants) and are superseded by the 2026-10-02 rows below |
| 2026-09-12 | 2.1.269 | 2.7.1 + reworded descriptions (released as 2.7.2) | 20 | 20 | 9.36 | eval model claude-opus-5[1m]; run on the final tree after the description style change |
| 2026-09-12 | 2.1.269 | 2.7.1 | 20 | 20 | 9.54 | eval model claude-opus-5[1m]; scaffolded |
| 2026-09-12 | 2.1.269 | 2.5.1 (pre-release tree) | 20 | 20 | 8.75 | eval model claude-opus-5[1m]; each trigger case scaffolds the `fixture-service.sh` orders-api repository |
| 2026-09-12 | 2.1.269 | 2.5.0 | 20 | 17 | 4.51 | no scaffold: trigger-04, -08, -10 failed because the workspace was empty and the model answered "nothing to review" without invoking the skill |

Per-case (latest run, 3 runs): every prr-trigger and prr-no-trigger case=1. In the 2026-10-02 run prr-trigger-05 was 0.67.

What this does and does not show: in the 2026-09-12 rows every positive prompt invoked `production-readiness-review` and no negative prompt did, on one run each; the 2026-10-02 row, at three runs per case, missed one positive run in 30 and fired on no negative run; the 2026-10-03 row, scaffolded, missed none. It does not measure report quality; that is measured by the outcome-graded `behaviour-prr-1`..`-8` and `behaviour-comment-cleanup` cases (results below). Rerun after changing the skill description or when Claude Code changes skill listing behaviour; three or more runs per case are needed before treating a single failure as a regression.

## comment-cleanup trigger results

| Run date (UTC) | Claude Code | Plugin | Cases | Passed | Cost (USD) | Notes |
|---|---|---|---:|---:|---:|---|
| 2026-10-03 | 2.1.288 | 2.10.0 + the widened description | 20 | 20 | 4.23 + 2.19 | `cleanup-trigger-*` and `cleanup-no-trigger-*`, 3 runs per case, `--ablation none`, `--scaffold`, eval model claude-sonnet-5-5. Positive prompts invoked `comment-cleanup` in 30/30 runs, negative prompts in 0/30 |

# Behaviour eval results

Recorded from `claude plugin eval . --case 'behaviour-prr-*' --runs 3 --scaffold --trust-plugin --ablation none --judge-model sonnet --allow-tools Read Grep Glob "Bash(python3 *)" --max-cost-usd 13` and the separate comment-cleanup invocation in `README.md` (2026-09-12 rows; the 2026-10-02/03 rows record their own invocation).

| Run date (UTC) | Claude Code | Plugin | Suite | Runs | Result | Cost (USD) | Notes |
|---|---|---|---:|---|---:|---|---|
| 2026-10-03 (latest, after the skill changes) | 2.1.288 | 2.10.0 + this release's tree | `behaviour-prr-1`..`-8` with `probe-ran`, scenario 4's `rubric-4` (pre-launch checks of production state only) and its reworked fixture, scenario 5's per-gap `rubric-4`; grants now include `Bash(git *)` | 8 × 3 | Scenarios 1, 2, 3, 6, 7, 8: 3/3 (one scenario-6 run was void, because the harness could not start the CLI while it was being reinstalled, and was rerun). Scenario 4: harness 1/3, verified 1/3 plus 1 ambiguous. Every run returned CONDITIONALLY READY with no UNKNOWN or FAIL gate, and every `rubric-4` judgment, passes included, was rechecked with reasons: one failed report's pre-launch checks are all production state (judge error); one lists the operator's production edit rights, which access records could show before deployment (real); the harness pass lists a test page and a ConfigMap presence check that the recheck judged checkable earlier (ambiguous). Scenario 5: 2/3; the failed report applies the AI/ML overlay outside G12 (real); `rubric-4` passed 3/3. The probe ran as its own call in every run. Earlier runs of the tree before the final rule and fixture changes, on the same day: with `Bash(python3 *)` only, all 28 git calls were denied and scenario 4 scored 0/3, scenario 5 1/3; with `Bash(git *)`, scenario 4 harness 2/3 twice (verified 1/3 the second time, once passes were rechecked), scenario 5 harness 0/3 and 1/3 (verified 2/3 plus 1 ambiguous each), scenario 6 2/3 plus 1 ambiguous and 3/3 | 11.86 + 0.45 (rerun), judge included | `--allow-tools Read Grep Glob "Bash(python3 *)" "Bash(git *)"`, otherwise as the next row |
| 2026-10-03 (before the skill changes) | 2.1.288 | 2.10.0 | `behaviour-prr-1`..`-8` (scenario 4 is now a bounded canary expecting CONDITIONALLY READY; scenario 8 is the unwired-kill-switch canary expecting NOT READY; scenario 5 names its exposure) | 8 × 3 | Scenarios 1, 2, 3, 7, 8: 3/3. Scenario 4: 1/3 on the final fixture. The fixture was revised several times on 2026-10-03, each time adding evidence for gaps the skill had raised. Harness counts in order: two 1-run pilots, 0/1 (NOT READY) and 0/1; then 0/3 and 0/3, where every run failed `rubric-4` ("never uses CONDITIONALLY READY as a softer label for a failed gate"), which was then replaced by a regex that checks only `GATE ... FAIL` lines; then 2/3 and 3/3 under that regex. 8 of the 11 CONDITIONALLY READY reports in those runs rated a gate UNKNOWN, which the skill's NOT READY rule does not allow, so `no-conditional-over-unknown` was added and the fixture's dates were made relative to the build day, with its drill step, down migration, and digest output corrected. Result: 1/3 at 04:26 UTC (two CONDITIONALLY READY reports with UNKNOWN gates, real). Those reports found that the release workflow lacked `attestations: write` and ran end-of-life Node 20; both were fixed. Final: 1/3 at 04:44 UTC (two NOT READY reports that place migration 0003, on the orders table stable also serves, outside the canary boundary, a defensible reading; see R15). Scenario 5: 0/3, `rubric-4` only, real (R18). Scenario 6: harness 2/3, verified 3/3 (the failed `rubric-5` report contains no E3 or E4 rating). Every `llm` FAIL was rechecked with `scripts/eval_recheck.py` | 11.02, plus scenario 4 reruns 2.27, 2.48, 2.16; judge included | Same invocation as the next row (scenario 4 reruns with `--case behaviour-prr-4`; the last two ran one at a time), judge `claude-sonnet-5-5`, kept after calibration: on 25 hand-verified judgments fed as files Sonnet 5.5 made 0 errors and Opus 5.5 made 1, but judging final messages in eval runs Sonnet 5.5 failed 3 of that set's 9 PASS items |
| 2026-10-03 (earlier) | 2.1.288 | 2.10.0 | `behaviour-prr-1`..`-7` (superseded by the row above; rubrics split per bullet, `repo-evidence` added; scenario 1's mechanical bullet now the `gate-lines`/`gate-evidence` regexes) | 7 × 3 | Latest run per scenario. Scenario 1: 3/3 (rerun at 00:43 after its G1-G12/E-level bullet became regex graders; in the 00:08 run the judge failed that bullet 2/3 although every report had 12 `GATE` lines and an E-level on all 12 gate-table rows). Scenario 2: 3/3. Scenario 3: 3/3 (rerun at 00:44 after `rubric-5` stated its gaps inline). Scenario 4: 0/3, but not a valid measurement: its fixture never wires in the kill switch the expected CONDITIONALLY READY depends on, and every report names that dead switch as the central blocker (R15). Scenario 5: 0/3, `rubric-4` (separate blockers from residual risk) 0/3, every other grader 3/3 (R18). Scenario 6: harness 2/3; the failed `rubric-5` (architecture claims at E1/E2, not E3/E4) is a judge error, since that report contains no E3 or E4 rating at all, so 3/3 on the evidence. Scenario 7: 3/3. `repo-evidence` passed in every run | 9.93 (00:08 run), 1.19 + 1.72 (reruns), judge included | `claude plugin eval . --tag behaviour-readiness` (and `--case behaviour-prr-1`, `--case behaviour-prr-3` for the reruns) `--scaffold --trust-plugin --ablation none --judge-model claude-sonnet-5-5 --allow-tools Read Grep Glob "Bash(python3 *)" --keep-temp --no-publish -j 3`; eval model claude-sonnet-5-5 (pinned by the cases). `repo_probe.py` ran in 2/21 runs of the 00:08 run (0/21 on 2026-10-02; see `README.md`) |
| 2026-10-03 (latest) | 2.1.288 | 2.10.0 + this release's tree | `behaviour-comment-cleanup` | 1 × 3 | 2/3 plus 1 ambiguous: every run rewrote `_cache_key`'s `# thread-safe` comment to a caller obligation ("no locking; callers must not mutate events concurrently"); the failed run also notes that keys use object identity (votes FAIL FAIL FAIL, recheck PASS). Earlier runs of the guidance on the same day: harness 2/3 (verified 3/3), 3/3, 1/3 with an example that said "safe only if ...", which runs copied, and 2/3 plus 1 ambiguous; the comparison's candidate arm later passed 3/3 | 0.85 | write grants |
| 2026-10-03 (before the skill changes) | 2.1.288 | 2.10.0 | `behaviour-comment-cleanup` (current graders, rubric split) | 1 × 3 | 0/3: `directives-intact` 3/3, `skill-fired` 3/3, `rubric`/`-2`/`-4` 3/3, `rubric-3` (no thread-safety claim) 0/3: every run kept `# thread-safe` on `_cache_key`, which a text check of each file confirms, and listed it under Deferred; see R16. Artifacts PASS 3/3 | 0.73, incl. judge | from the `comment-guidance-write` invocation, so with that invocation's wider grant |
| 2026-10-02 | 2.1.288 | 2.10.0 | `behaviour-prr-1`..`-7` (whole rubrics) | 7 × 3 | Superseded by the 2026-10-03 row. Scenarios 1, 2, 3, 7 3/3; 4 0/3; 5 0/3; 6 1/3. `repo-evidence` 21/21 | 5.71, incl. 0.92 judge | same invocation |
| 2026-10-02 | 2.1.288 | 2.10.0 | `behaviour-comment-cleanup` (whole rubric) | 1 × 3 | Superseded. 0/3, `rubric` 0/3, same thread-safety cause | 0.67, incl. 0.03 judge | write invocation |
| 2026-09-12 | 2.1.269 | 2.8.0 + this release's tree | `behaviour-prr-1`..`-7` | 7 × 3 | `VERDICT`/`GATE` regex graders: 18/18 on scenarios 1, 2, 3, 5, 6, 7; scenario 4: 0/3 (`NOT READY` where `CONDITIONALLY READY` is expected, see risk register R15); `llm` rubric 20/21 (one FAIL on scenario 5) | 9.84 | eval model claude-sonnet-5; prompts invoke the skill by slash command |
| 2026-09-12 | 2.1.269 | 2.8.0 + this release's tree | `behaviour-comment-cleanup` | 1 × 3 | 3/3 runs passed every grader (`directives-intact`, `rubric`, `skill-fired`) | 0.58 | eval model claude-sonnet-5; `Skill` added to the tool grants after a first 3-run batch (2/3) in which one run was denied the `Skill` tool by the sandbox |

Note on the 2026-09-12 `behaviour-comment-cleanup` row: this 3/3 result was measured under the
previous grader version, which graded the agent's final message with a regex plus an
`llm` rubric over that final message, and used a workspace-local convenience checker for line
membership. It did not grade file contents through an external, trusted checker and is not
evidence for the artifact-preservation, directive-attachment, or code-preservation properties the
current `directives-intact`/`rubric` graders and `scripts/comment_guidance_checks.py` assess.
Treat it only as historical evidence that the skill fired and produced a plausible final report.

## Comment-guidance suite results

Cases B01-B08 and installation/context tests I01-I04, as specified in
`docs/change-eval/comment-guidance-2026-09.md`.

Baseline-vs-candidate comparison, 2026-10-03 (Claude Code 2.1.288, baseline `e158b1e6` and the release
tree under the same eval overlay, three counterbalanced repetitions per arm, subject and judge model
claude-sonnet-5-5, 9.02 USD): accepted as a three-run screen. Verified passes, baseline vs candidate:
B01 0/3 vs 3/3, B05 2/3 vs 3/3, B02 0/3 vs 1/3 (improved; B02 only in skill invocation); B06 and B07
3/3 vs 3/3, B08 2/3 vs 2/3 (no difference); B03 0/3 with 3 unverified vs 3/3 (inconclusive under the
protocol, because every baseline run stopped at its denied command); B04 0/3 with 3 unverified vs 2/3
(mixed: the candidate completed it, but one candidate contract document adds an evaluation-order
guarantee that no baseline document had). I01, I03, and I04 pass in both arms; I02 passes on the
candidate, the only arm it ran on. No candidate run made an
unauthorized edit or broke a protected directive. Per-case detail and the evidence record are in the
protocol document.

2026-10-03 candidate screen after the skill changes (Claude Code 2.1.288, plugin 2.10.0 plus this
release's tree, subject and judge model claude-sonnet-5-5, `--ablation none`, 3 runs per case,
`--keep-temp`, the README's invocations; artifacts checker run on every retained workspace; every
`llm` FAIL rechecked with `scripts/eval_recheck.py`). As below, this screens the current tree only
and is not a comparison verdict. B01, B02, and B05 ran at 16:40-16:44 UTC on the final skill text;
B03, B04, B06, and B07 at 15:30 UTC and B08 at 16:04 UTC, before the last changes to comment-cleanup's
example and mechanism list (which the implementation and worker skills also load), change-review,
and the readiness skill, with `tests-ran` replayed on their traces under its final pattern. The
baseline comparison above ran every case again on the final tree. Cost: write 3.29, B01 0.85, B02 0.96, B05 0.71, B08 0.48 USD, judge
included.

| Case | Harness | Verified |
|---|---|---|
| B01 `behaviour-comment-cleanup` | 2/3 | 2/3 plus 1 ambiguous (see the behaviour table). Artifacts PASS 3/3 |
| B02 `comment-guidance-review-only` | 2/3 | 2/3: one run did not invoke `comment-cleanup` (`skill-fired`, real); its `rubric-5` FAIL is ambiguous (votes FAIL PASS FAIL, recheck PASS). Artifacts PASS 3/3 |
| B03 `comment-guidance-implementation` | 3/3 | 3/3, `tests-ran` 3/3. Artifacts PASS 3/3 |
| B04 `comment-guidance-plan` | 2/3 | 2/3 plus 1 ambiguous: every parent retried its denied compound call as one plain `python3` command, wrote `verification_output.txt`, and dispatched `plan-auditor`; the failed `doc-contract-preserved` doc adds that a one-shot generator is consumed (votes FAIL FAIL FAIL, recheck PASS). Artifacts PASS 3/3 |
| B05 `comment-guidance-change-review` | 3/3 | 3/3: `security-reviewer` dispatched and stated, no style finding. Artifacts PASS 3/3 |
| B06 `comment-guidance-mechanical` | 2/3 | 3/3: the failed `prose-renamed` file is identical in its buffer/queue lines to both passing runs (judge error). Artifacts PASS 3/3 |
| B07 `comment-guidance-repair` | 3/3 | 3/3, `tests-ran` 3/3 on the `hard-repair` subagent's own run. Artifacts PASS 3/3 |
| B08 `comment-guidance-doc-plan` | 3/3 | 3/3. Artifacts PASS 3/3 |

Earlier runs of these changes on 2026-10-03: B04 had a void run (the harness could not start the CLI
while it was being reinstalled) and B07 a run that stopped after one denied command, fixed by the
`hard-repair` rule; B05 had a run that reported a trailing blank line, fixed by the last change-review
revision; `tests-ran` passed a repair run whose tests never ran, by matching a `Read` of the stored
test log, since fixed; B01 scored 1/3 with an example its runs copied, since made generic.

2026-10-03 candidate screen, before the skill changes (Claude Code 2.1.288, plugin 2.10.0, subject and judge model
claude-sonnet-5-5, `--ablation none`, 3 runs per case, `--keep-temp`, the README's invocations:
one write invocation and one invocation per read case; artifacts checker run on every retained
workspace; every `llm` FAIL rechecked with `scripts/eval_recheck.py`). This screens the current
tree only: the baseline arm of the comparison in `docs/change-eval/comment-guidance-2026-09.md`
had not been run yet, so none of these is a comparison verdict. "Harness" is the eval's own pass count.
"Verified" re-checks every failed grader against the run's trace or file, deterministically where
the criterion allows; an `llm` FAIL whose criterion the evidence satisfies is a judge error. A run
whose required command was denied and that then stopped is unverified (README incomplete-run
rule). Cost: write 2.75, read 1.03 + 0.48 + 0.47 USD, judge included.

| Case | Harness | Verified |
|---|---|---|
| B01 `behaviour-comment-cleanup` | 0/3 | 0/3 fail on `rubric-3` (thread-safety claim kept and deferred, see R16); every other grader 3/3. Artifacts PASS 3/3 |
| B02 `comment-guidance-review-only` | 1/3 | 1/3: `skill-fired` 1/3 (the natural-language prompt invoked `comment-cleanup` once); every rubric grader 3/3. Artifacts PASS 3/3 |
| B03 `comment-guidance-implementation` | 1/3 | 1/3 plus 2 unverified: two runs' only verification call (`python3 -m unittest ... > test_output.txt 2>&1; ...`) was denied and the run stopped (R17); the passing run ran the tests inside one `python3` heredoc and its tool result shows "Ran 10 tests ... OK". Every other grader 3/3. Artifacts: only `required_artifacts_present` fails, in the two unverified runs |
| B04 `comment-guidance-plan` | 0/3 | 3/3 unverified: each parent's one integrated-verification call was denied (`python`, `\| tee`, compound forms), so no `verification_output.txt` and no `plan-auditor` (R17). `bulk-implementer-instructed` and `no-worker-test-command` 3/3. `doc-contract-preserved`: one real FAIL (the doc adds aliasing and purity guarantees) and one ambiguous (votes PASS FAIL FAIL, recheck PASS; the doc calls `events` an iterable, wider than the ground truth's list). Artifacts: only `required_artifacts_present` fails |
| B05 `comment-guidance-change-review` | 1/3 | 1/3: two runs reviewed the diff without dispatching `security-reviewer`, and one of them reported a trailing blank line as a finding (`rubric-3`, real). Artifacts PASS 3/3 |
| B06 `comment-guidance-mechanical` | 3/3 | 3/3 with the narrowed hardware-sentence ground truth. Artifacts PASS 3/3 |
| B07 `comment-guidance-repair` | 3/3 | 3/3. Artifacts PASS 3/3 |
| B08 `comment-guidance-doc-plan` | 3/3 | 3/3. Artifacts PASS 3/3 |

Earlier rounds (superseded; all retained under `results/`). 2026-10-02, under previous graders
and grants: B01 0/3; B02 0/3 twice plus a single-run debug trial (0/1); B03 0/3 (3 unverified);
B04 0/3 then 0/3 (5 of 6 unverified; in the one verified run the parent skipped `plan-auditor`
after a green pass); B05 0/3 without the git grant (void), then 2/3 (the failing run also failed
the whole rubric); B06 3/3 under the whole rubric, although all three runs changed the hardware
sentence; B07 3/3; B08 3/3. 2026-10-03 00:09, before the B03, B06, and B07 grader fixes: B03 0/3
(3 unverified); B06 2/3, where two runs changed the hardware sentence and the split graders failed
only the run that kept it; B07 1/3 (1 unverified). 2026-10-03 00:09-00:44, after those fixes:
B01 0/3; B02 0/3; B03 0/3 (3 unverified); B04 0/3 (3 unverified); B05 2/3; B06 2/3 (one run changed
the hardware sentence, before its ground truth was narrowed); B07 2/3 (1 unverified); B08 3/3.
Targeted reruns on 2026-10-03 before that screen: B06 3/3 (narrowed ground truth), B04 0/3 (3 unverified; new worker
graders 3/3).

| Case | Result |
|---|---|
| I01 local `--plugin-dir` execution | 2026-10-03: pass in both arms (each loads its own plugin, 12 skills, 11 agents, SessionStart hook exit 0) |
| I02 marketplace/cache installation | 2026-10-03: pass on the candidate (`ci.sh --full`, including the official-marketplace install and the rules-file load) |
| I03 policy path fallback/installed/legacy/stale | 2026-10-03: pass in both arms (16/16 hook-contract checks each) |
| I04 supported-version and forked/direct-agent context | 2026-10-03: pass in both arms (version gate 3/3 each; each arm quoted its own `plan-auditor` text; the comment-guidance reference exists only in the candidate, which quoted it verbatim) |
