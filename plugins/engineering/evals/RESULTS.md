# Trigger eval results

Recorded from `claude plugin eval . --case 'prr-*' --runs 1 --ablation none --scaffold --trust-plugin -j 4` (2026-09-12 rows; the 2026-10-02 row records its own invocation).

| Run date (UTC) | Claude Code | Plugin | Cases | Passed | Cost (USD) | Notes |
|---|---|---|---:|---:|---:|---|
| 2026-10-02 | 2.1.288 | 2.10.0 | 20 | 19 | 14.57 | 3 runs per case, `--ablation with-without`, no scaffold, eval model the session default (not recorded in the result). With-plugin arm: positive prompts invoked the skill in 29/30 runs, negative prompts in 0/30; without-plugin arm: 0/30 positive. The one miss is prr-trigger-05 ("Judge this PR as a release candidate") on an empty workspace; its trace was not kept, so the cause, the 2.5.0 row's "nothing to review", is inferred. Run from the repository root as one 35-case invocation; its behaviour and comment-guidance results are void (empty workspaces, no tool grants) and are superseded by the 2026-10-02 rows below |
| 2026-09-12 | 2.1.269 | 2.7.1 + reworded descriptions (released as 2.7.2) | 20 | 20 | 9.36 | eval model claude-opus-5[1m]; run on the final tree after the description style change |
| 2026-09-12 | 2.1.269 | 2.7.1 | 20 | 20 | 9.54 | eval model claude-opus-5[1m]; scaffolded |
| 2026-09-12 | 2.1.269 | 2.5.1 (pre-release tree) | 20 | 20 | 8.75 | eval model claude-opus-5[1m]; each trigger case scaffolds the `fixture-service.sh` orders-api repository |
| 2026-09-12 | 2.1.269 | 2.5.0 | 20 | 17 | 4.51 | no scaffold: trigger-04, -08, -10 failed because the workspace was empty and the model answered "nothing to review" without invoking the skill |

Per-case (latest run, with-plugin arm, 3 runs): prr-trigger-05=0.67; every other prr-trigger and prr-no-trigger case=1.

What this does and does not show: in the 2026-09-12 rows every positive prompt invoked `production-readiness-review` and no negative prompt did, on one run each; the 2026-10-02 row, at three runs per case, missed one positive run in 30 and fired on no negative run. It does not measure report quality; that is measured by the outcome-graded `behaviour-prr-1`..`-7` and `behaviour-comment-cleanup` cases (results below). Rerun after changing the skill description or when Claude Code changes skill listing behaviour; three or more runs per case are needed before treating a single failure as a regression.

# Behaviour eval results

Recorded from `claude plugin eval . --case 'behaviour-prr-*' --runs 3 --scaffold --trust-plugin --ablation none --judge-model sonnet --allow-tools Read Grep Glob "Bash(python3 *)" --max-cost-usd 13` and the separate comment-cleanup invocation in `README.md` (2026-09-12 rows; the 2026-10-02/03 rows record their own invocation).

| Run date (UTC) | Claude Code | Plugin | Suite | Runs | Result | Cost (USD) | Notes |
|---|---|---|---:|---|---:|---|---|
| 2026-10-03 | 2.1.288 | 2.10.0 | `behaviour-prr-1`..`-7` (rubrics split per bullet, `repo-evidence` added; scenario 1's mechanical bullet now the `gate-lines`/`gate-evidence` regexes) | 7 × 3 | Latest run per scenario. Scenario 1: 3/3 (rerun at 00:43 after its G1-G12/E-level bullet became regex graders; in the 00:08 run the judge failed that bullet 2/3 although every report had 12 `GATE` lines and an E-level on all 12 gate-table rows). Scenario 2: 3/3. Scenario 3: 3/3 (rerun at 00:44 after `rubric-5` stated its gaps inline). Scenario 4: 0/3, but not a valid measurement: its fixture never wires in the kill switch the expected CONDITIONALLY READY depends on, and every report names that dead switch as the central blocker (R15). Scenario 5: 0/3, `rubric-4` (separate blockers from residual risk) 0/3, every other grader 3/3 (R18). Scenario 6: harness 2/3; the failed `rubric-5` (architecture claims at E1/E2, not E3/E4) is a judge error, since that report contains no E3 or E4 rating at all, so 3/3 on the evidence. Scenario 7: 3/3. `repo-evidence` passed in every run | 9.93 (00:08 run), 1.19 + 1.72 (reruns), judge included | `claude plugin eval . --tag behaviour-readiness` (and `--case behaviour-prr-1`, `--case behaviour-prr-3` for the reruns) `--scaffold --trust-plugin --ablation none --judge-model claude-sonnet-5-5 --allow-tools Read Grep Glob "Bash(python3 *)" --keep-temp --no-publish -j 3`; eval model claude-sonnet-5-5 (pinned by the cases). `repo_probe.py` ran in 2/21 runs of the 00:08 run (0/21 on 2026-10-02; see `README.md`) |
| 2026-10-03 | 2.1.288 | 2.10.0 | `behaviour-comment-cleanup` (current graders, rubric split) | 1 × 3 | 0/3: `directives-intact` 3/3, `skill-fired` 3/3, `rubric`/`-2`/`-4` 3/3, `rubric-3` (no thread-safety claim) 0/3: every run kept `# thread-safe` on `_cache_key`, which a text check of each file confirms, and listed it under Deferred; see R16. Artifacts PASS 3/3 | 0.73, incl. judge | from the `comment-guidance-write` invocation, so with that invocation's wider grant |
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

2026-10-03 candidate screen (Claude Code 2.1.288, plugin 2.10.0, subject and judge model
claude-sonnet-5-5, `--ablation none`, 3 runs per case, `--keep-temp`, the README's invocations:
one write invocation and one invocation per read case; artifacts checker run on every retained
workspace). This screens the current tree only: the baseline arm of the comparison in
`docs/change-eval/comment-guidance-2026-09.md` was not run, so none of these is a comparison
verdict. "Harness" is the eval's own pass count. "Verified" re-checks every failed grader against
the run's trace or file, deterministically where the criterion allows; an `llm` FAIL whose
criterion the evidence satisfies is a judge error. A run whose required command was denied and
that then stopped is unverified (README incomplete-run rule). Each row is the latest run of that
case (00:09-00:11 UTC, or the 00:43-00:44 reruns where marked). Cost: write 3.32, read
1.09 + 0.62 + 0.55, reruns 0.54 + 0.59 + 0.38 USD, judge included.

| Case | Harness | Verified |
|---|---|---|
| B01 `behaviour-comment-cleanup` (current grader version) | 0/3 | 0/3 fail on `rubric-3` (thread-safety claim kept and deferred, see R16); every other grader 3/3. Artifacts PASS 3/3 |
| B02 `comment-guidance-review-only` | 0/3 | 0/3: `skill-fired` 0/3 (the natural-language prompt never invoked `comment-cleanup`). `rubric-2` FAIL in one run is real: that report says the `thread-safe` claim "holds for the function". Other rubric graders, `no-edit`, `no-write` 3/3. Artifacts PASS 3/3 |
| B03 `comment-guidance-implementation` | 0/3 (00:44 rerun) | 3/3 unverified: each run's only verification call (`python3 -m unittest ... > test_output.txt 2>&1; ...`) was denied and the run stopped, so `test_output.txt` is absent. Every other grader 3/3, including `rubric-3` after its pre-change baseline was stated inline (in the 00:09 run, before that fix, it failed 2/3 on a criterion the judge could not decide from the file). `unittest-run` 3/3 counts the denied call. Artifacts: only `required_artifacts_present` fails |
| B04 `comment-guidance-plan` | 0/3 | 3/3 unverified: each parent's one integrated-verification call was denied (`python`, `\| tee`, compound forms), so no `verification_output.txt` and, as the skill requires a green pass first, no `plan-auditor`. `doc-contract-preserved` 3/3. `no-worker-test-execution` FAIL 3/3, unverified by its own rubric; every Bash call in the three traces is the parent's. Artifacts: only `required_artifacts_present` fails |
| B05 `comment-guidance-change-review` | 2/3 | 2/3: the failing run reviewed the diff itself instead of dispatching `security-reviewer` and reported a style-only finding (a trailing blank line), so its `rubric-3` FAIL is real. Artifacts PASS 3/3 |
| B06 `comment-guidance-mechanical` | 2/3 (00:43 rerun) | 2/3: the failing run renamed "our message buffer" to "our message queue" inside the UART hardware-register sentence, which `manifest.json` fact F-BUFFER-HARDWARE says must stay unchanged; the byte-exact `hardware-sentence-unchanged` regex and `prose-renamed` agree. Before the rubric carried that exception, 5 of the 6 earlier runs (all three on 2026-10-02 that the whole rubric passed) made the same change (R19). Artifacts PASS 3/3; the checker does not test semantic facts |
| B07 `comment-guidance-repair` | 2/3 (00:44 rerun) | 2/3 plus 1 unverified: in the third run the hard-repair subagent's two calls and the parent's call were all denied compound or redirect forms, so no `repair_output.txt`. The documentation bullet now names the module docstring; in the 00:09 run its old wording ("the docstring for `select_window`", which has none) drew 4 FAIL votes of 9 on three byte-identical files. Artifacts PASS 2/3, the third missing only that file |
| B08 `comment-guidance-doc-plan` | 3/3 | 3/3. Artifacts PASS 3/3 |

Earlier rounds (superseded; all retained under `results/`). 2026-10-02, under previous graders
and grants: B01 0/3; B02 0/3 twice plus a single-run debug trial (0/1); B03 0/3 (3 unverified);
B04 0/3 then 0/3 (5 of 6 unverified; in the one verified run the parent skipped `plan-auditor`
after a green pass); B05 0/3 without the git grant (void), then 2/3 (the failing run also failed
the whole rubric); B06 3/3 under the whole rubric, although all three runs changed the hardware
sentence; B07 3/3; B08 3/3. 2026-10-03 00:09, before the B03, B06, and B07 grader fixes: B03 0/3
(3 unverified); B06 2/3, where two runs changed the hardware sentence and the split graders failed
only the run that kept it; B07 1/3 (1 unverified).

| Case | Result |
|---|---|
| I01 local `--plugin-dir` execution | NOT_RUN |
| I02 marketplace/cache installation | NOT_RUN |
| I03 policy path fallback/installed/legacy/stale | NOT_RUN |
| I04 supported-version and forked/direct-agent context | NOT_RUN |
